import pytest
from conftest import write_project

from agentguard.crawler import crawl


def names(paths, root):
    return sorted(p.relative_to(root).as_posix() for p in paths)


def test_skips_environments_and_non_python(tmp_path):
    write_project(
        tmp_path,
        {
            "a.py": "",
            "pkg/b.py": "",
            "notes.md": "",
            "app.js": "",
            ".venv/lib/x.py": "",
            "node_modules/y.py": "",
            "build/z.py": "",
            "my.egg-info/w.py": "",
        },
    )
    assert names(crawl([str(tmp_path)]), tmp_path) == ["a.py", "pkg/b.py"]


def test_exclude_globs(tmp_path):
    write_project(tmp_path, {"a.py": "", "tests/t.py": "", "tests/fixtures/f.py": "", "src/s.py": ""})
    assert names(crawl([str(tmp_path)], exclude=["tests"]), tmp_path) == ["a.py", "src/s.py"]
    assert names(crawl([str(tmp_path)], exclude=["*/fixtures/*"]), tmp_path) == ["a.py", "src/s.py", "tests/t.py"]


def test_explicit_file(tmp_path):
    write_project(tmp_path, {"a.py": "", "b.py": ""})
    assert names(crawl([str(tmp_path / "b.py")]), tmp_path) == ["b.py"]


def test_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        crawl([str(tmp_path / "nope")])
