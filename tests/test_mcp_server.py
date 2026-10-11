import json
import os
import sys

import pytest
from conftest import write_project

pytest.importorskip("mcp.server.mcpserver")

from mcp import Client, StdioServerParameters

from agentguard.mcp_server import server

AGENT = """
from openai import OpenAI
client = OpenAI()
messages = []
while True:
    r = client.chat.completions.create(model="gpt-4o", messages=messages, max_tokens=10)
    messages.append(r.choices[0].message)
"""


def payload(result):
    assert not result.is_error, result
    if result.structured_content is not None:
        data = result.structured_content
        return data.get("result", data)
    return json.loads(result.content[0].text)


async def test_tools_are_listed_and_read_only():
    async with Client(server) as client:
        tools = {t.name: t for t in (await client.list_tools()).tools}
    assert set(tools) == {"scan", "explain_rule"}
    assert all(t.annotations.read_only_hint for t in tools.values())


async def test_scan(tmp_path):
    write_project(tmp_path, {"agent.py": AGENT})
    async with Client(server) as client:
        report = payload(await client.call_tool("scan", {"path": str(tmp_path)}))
    assert sorted(f["rule"] for f in report["findings"]) == ["AG001", "AG002"]
    assert report["summary"]["call_sites"] == 1


async def test_scan_ignore_and_bad_path(tmp_path):
    write_project(tmp_path, {"agent.py": AGENT})
    async with Client(server) as client:
        report = payload(await client.call_tool("scan", {"path": str(tmp_path), "ignore": ["AG001"]}))
        missing = await client.call_tool("scan", {"path": str(tmp_path / "nope")})
    assert [f["rule"] for f in report["findings"]] == ["AG002"]
    assert missing.is_error


async def test_explain_rule():
    async with Client(server) as client:
        info = payload(await client.call_tool("explain_rule", {"rule_id": "ag002"}))
        bad = await client.call_tool("explain_rule", {"rule_id": "AG999"})
    assert info["name"] == "unbounded-context-growth"
    assert bad.is_error


async def test_stdio_end_to_end(tmp_path):
    # The real transport: start the server as a subprocess, as an editor would.
    write_project(tmp_path, {"agent.py": AGENT})
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "agentguard.mcp_server"], env={**os.environ, "PYTHONIOENCODING": "utf-8"}
    )
    async with Client(params) as client:
        report = payload(await client.call_tool("scan", {"path": str(tmp_path / "agent.py")}))
    assert {f["rule"] for f in report["findings"]} == {"AG001", "AG002"}
