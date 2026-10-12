"""Command-line entry point."""

from __future__ import annotations

import argparse
import io
import sys
import time
from pathlib import Path
from typing import List, Optional, Sequence

from agentguard import __version__, config
from agentguard.analyzer import analyze_project
from agentguard.crawler import crawl, too_broad
from agentguard.estimator import Assumptions, estimate
from agentguard.pricing import DEFAULT_MODEL, PriceTable
from agentguard.reporter import FORMATS, render, use_color
from agentguard.rules import RULES, SEVERITY_RANK

EXIT_OK, EXIT_FINDINGS, EXIT_ERROR, EXIT_INTERRUPTED = 0, 1, 2, 130


def _rule_list(text: str) -> List[str]:
    ids = [x.strip().upper() for x in text.split(",") if x.strip()]
    bad = [x for x in ids if x not in RULES]
    if bad:
        raise argparse.ArgumentTypeError(f"unknown rule(s): {', '.join(bad)} (see --list-rules)")
    return ids


def _token_range(text: str) -> tuple:
    lo, sep, hi = text.partition(":")
    try:
        a, b = int(lo), int(hi if sep else lo)
    except ValueError:
        raise argparse.ArgumentTypeError("expected MIN:MAX, e.g. 200:1000") from None
    if a < 0 or b < a:
        raise argparse.ArgumentTypeError("expected 0 <= MIN <= MAX")
    return a, b


def _depths(text: str) -> tuple:
    try:
        values = tuple(sorted({int(x) for x in text.split(",") if x.strip()}))
    except ValueError:
        raise argparse.ArgumentTypeError("expected comma-separated integers, e.g. 1,10,100") from None
    if not values or values[0] < 1:
        raise argparse.ArgumentTypeError("depths must be positive integers")
    return values


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="agentguard",
        description="Find LLM cost risks in Python agent code - unbounded agent loops, quadratic "
        "history growth, uncapped outputs - and estimate what a run costs.",
        epilog="Exit status: 0 no findings at or above --fail-on, 1 findings, 2 error.",
    )
    p.add_argument("paths", nargs="*", metavar="PATH", help="files or directories (default: .)")
    p.add_argument("--version", action="version", version=f"agentguard {__version__}")

    out = p.add_argument_group("output")
    out.add_argument("-f", "--format", choices=FORMATS, default="text")
    out.add_argument("-o", "--output", metavar="FILE", help="write the report to FILE instead of stdout")
    out.add_argument("--no-costs", action="store_true", help="findings only; skip the cost estimate")
    style = out.add_mutually_exclusive_group()
    style.add_argument(
        "--pretty",
        dest="pretty",
        action="store_true",
        default=None,
        help="banner-and-sections report (the default on a terminal)",
    )
    style.add_argument(
        "--plain",
        dest="pretty",
        action="store_false",
        help="one line per finding, file:line:col (the default when piped or in CI)",
    )
    out.add_argument("--color", dest="color", action="store_true", default=None)
    out.add_argument("--no-color", dest="color", action="store_false")

    rules = p.add_argument_group("rules")
    rules.add_argument("--select", type=_rule_list, metavar="IDS", help="only these rules, e.g. AG001,AG002")
    rules.add_argument("--ignore", type=_rule_list, metavar="IDS", help="skip these rules")
    rules.add_argument(
        "--fail-on",
        choices=["high", "medium", "low", "never"],
        help="exit 1 if any finding is at least this severe (default: high)",
    )
    rules.add_argument("--exclude", action="append", metavar="GLOB", help="skip matching paths (repeatable)")
    rules.add_argument(
        "--scan-anyway",
        action="store_true",
        help="allow scanning a home directory or a whole drive (refused by default)",
    )

    cost = p.add_argument_group("cost model")
    cost.add_argument(
        "-m", "--model", help=f"price calls whose model is not in the code as this (default: {DEFAULT_MODEL})"
    )
    cost.add_argument("--prices", metavar="FILE", help="extra/override prices: AgentGuard or LiteLLM JSON format")
    cost.add_argument("--system-tokens", type=int, metavar="N", help="static prompt tokens per call (default: 500)")
    cost.add_argument("--input-tokens", type=int, metavar="N", help="new input tokens per call (default: 500)")
    cost.add_argument(
        "--output-tokens", type=_token_range, metavar="MIN:MAX", help="output tokens per call (default: 200:1000)"
    )
    cost.add_argument(
        "--depths",
        type=_depths,
        metavar="N,N,...",
        help="iterations assumed for loops with no constant bound (default: 1,10,100)",
    )

    info = p.add_argument_group("info")
    info.add_argument("--list-models", action="store_true", help="print the price table and exit")
    info.add_argument("--list-rules", action="store_true", help="print the rules and exit")
    info.add_argument("--config", metavar="FILE", help="pyproject.toml to read [tool.agentguard] from")
    info.add_argument("--no-config", action="store_true", help="ignore pyproject.toml")

    # 0.2.x flags, kept so existing scripts keep working.
    legacy = p.add_argument_group("deprecated (0.2.x)")
    legacy.add_argument("--root_dir", help=argparse.SUPPRESS)
    legacy.add_argument("--json", action="store_true", help=argparse.SUPPRESS)
    legacy.add_argument("--json_out", help=argparse.SUPPRESS)
    legacy.add_argument("-q", "--quiet", action="store_true", help=argparse.SUPPRESS)
    legacy.add_argument("-i", "--input_tokens", dest="input_tokens", type=int, help=argparse.SUPPRESS)
    legacy.add_argument("--output_min", type=int, help=argparse.SUPPRESS)
    legacy.add_argument("--output_max", type=int, help=argparse.SUPPRESS)
    legacy.add_argument("--dag", action="store_true", help=argparse.SUPPRESS)
    return p


def _utf8_streams() -> None:
    """Never crash on a narrow console encoding (cp1252 on Windows); emit UTF-8 when piped."""
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            if stream.isatty():
                stream.reconfigure(errors="replace")
            else:
                stream.reconfigure(encoding="utf-8", errors="replace")


class _Progress:
    """A single self-overwriting status line on stderr, shown only on a terminal and only
    once a scan has run long enough to need one."""

    def __init__(self, stream=None, enabled: Optional[bool] = None, delay: float = 0.3):
        self.stream = stream or sys.stderr
        self.enabled = (hasattr(self.stream, "isatty") and self.stream.isatty()) if enabled is None else enabled
        self.start = time.monotonic()
        self.delay = delay
        self.last = 0.0
        self.shown = False

    def update(self, text: str) -> None:
        now = time.monotonic()
        if not self.enabled or now - self.start < self.delay or now - self.last < 0.1:
            return
        self.last = now
        self.stream.write("\r  " + text.ljust(60)[:60])
        self.stream.flush()
        self.shown = True

    def clear(self) -> None:
        if self.shown:
            self.stream.write("\r" + " " * 64 + "\r")
            self.stream.flush()
            self.shown = False


def _err(msg: str) -> None:
    print(f"agentguard: {msg}", file=sys.stderr)


def main(argv: Optional[Sequence[str]] = None) -> int:
    _utf8_streams()
    args = build_parser().parse_args(argv)

    if args.list_rules:
        for r in RULES.values():
            print(f"{r.id}  {r.severity:<6}  {r.name}\n        {r.summary}\n        fix: {r.fix}")
        return EXIT_OK

    paths = list(args.paths) or ([args.root_dir] if args.root_dir else ["."])
    try:
        cfg_path = (
            None if args.no_config else (Path(args.config) if args.config else config.find_pyproject(Path(paths[0])))
        )
        cfg = config.load(cfg_path)
        prices = PriceTable.load(args.prices or cfg.get("prices"))
    except (OSError, ValueError) as e:
        _err(str(e))
        return EXIT_ERROR

    if args.list_models:
        print(
            f"{'model':<24} {'input':>8} {'output':>8} {'cache read':>11}   (USD per 1M tokens, as of {prices.as_of})"
        )
        for name, pr in sorted(prices.models.items()):
            cr = f"{pr.cache_read:.3f}" if pr.cache_read is not None else "-"
            print(f"{name:<24} {pr.input:>8.3f} {pr.output:>8.3f} {cr:>11}")
        return EXIT_OK

    # Legacy flag mapping.
    fmt = "json" if args.json and args.format == "text" else args.format
    output = args.output or args.json_out
    if args.dag:
        _err("--dag was removed in 0.3.0 and is ignored")
    out_range = args.output_tokens or (_token_range(cfg["output_tokens"]) if "output_tokens" in cfg else None)
    if out_range is None and (args.output_min is not None or args.output_max is not None):
        out_range = (args.output_min or 200, args.output_max or max(args.output_min or 200, 1000))

    defaults = Assumptions()
    assumptions = Assumptions(
        system_tokens=args.system_tokens or cfg.get("system_tokens", defaults.system_tokens),
        input_tokens=args.input_tokens or cfg.get("input_tokens", defaults.input_tokens),
        output_min=(out_range or (defaults.output_min, 0))[0],
        output_max=(out_range or (0, defaults.output_max))[1],
        depths=args.depths or tuple(cfg.get("depths", defaults.depths)),
        model=args.model or cfg.get("model", DEFAULT_MODEL),
    )

    broad = [p for p in paths if Path(p).is_dir() and too_broad(p)]
    if broad and not args.scan_anyway:
        where = Path(broad[0]).resolve()
        _err(
            f"refusing to scan {where}: that is your home directory or a whole drive, which is never a "
            "single project.\n  Run it on a project folder, e.g.  agentguard path\\to\\project  "
            "(or pass --scan-anyway)."
        )
        return EXIT_ERROR

    progress = _Progress()
    try:
        files = crawl(
            paths,
            exclude=(args.exclude or []) + list(cfg.get("exclude", [])),
            on_file=lambda n: progress.update(f"finding Python files... {n:,}"),
        )
    except (FileNotFoundError, RuntimeError) as e:
        progress.clear()
        _err(str(e))
        return EXIT_ERROR

    root = Path(paths[0]).resolve()
    root = root if root.is_dir() else root.parent
    analysis = analyze_project(files, root, progress=lambda i, n: progress.update(f"analysing {i:,} / {n:,} files"))
    progress.clear()

    select = set(args.select or cfg.get("select") or RULES)
    ignore = set(args.ignore or cfg.get("ignore") or [])
    for fr in analysis.files:
        fr.findings = [f for f in fr.findings if f.rule in select and f.rule not in ignore]

    try:
        est = estimate(analysis, prices, assumptions)
    except ValueError as e:
        _err(f"{e}")
        return EXIT_ERROR

    show_costs = not args.no_costs and not args.quiet
    if output:
        with open(output, "w", encoding="utf-8", newline="\n") as f:
            render(fmt, analysis, est, f, color=False, show_costs=show_costs, pretty=bool(args.pretty))
        print(f"agentguard: wrote {fmt} report to {output}", file=sys.stderr)
    else:
        pretty = args.pretty if args.pretty is not None else (sys.stdout.isatty() and not args.quiet)
        render(
            fmt,
            analysis,
            est,
            sys.stdout,
            color=use_color(sys.stdout, args.color),
            show_costs=show_costs,
            pretty=pretty,
        )

    fail_on = args.fail_on or cfg.get("fail_on", "high")
    if fail_on != "never" and any(SEVERITY_RANK[f.severity] >= SEVERITY_RANK[fail_on] for f in analysis.findings):
        return EXIT_FINDINGS
    return EXIT_OK


def entry() -> None:
    try:
        code = main()
    except KeyboardInterrupt:
        print("\nagentguard: interrupted", file=sys.stderr)
        code = EXIT_INTERRUPTED
    sys.exit(code)


if __name__ == "__main__":
    entry()
