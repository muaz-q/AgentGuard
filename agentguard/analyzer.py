"""Static Analyzer — inspects Python files for agentic patterns with alias + context tracking."""

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List


# ───────────────────────────────────────────────

HIGH_COMPLEXITY_NAMES = re.compile(
    r"(math|code|agent|reason|plan|search|tool|exec)", re.IGNORECASE
)

LOOP_LIMITER_PATTERN = re.compile(
    r"(max_iter|max_steps|max_loops|max_turns|iteration_limit|depth_limit|stop_after)",
    re.IGNORECASE,
)


# ───────────────────────────────────────────────

@dataclass
class FileAnalysis:
    path: Path
    language: str

    api_calls: int = 0
    calls_in_loops: int = 0
    loop_count: int = 0
    nested_loops: bool = False
    has_loop_limiter: bool = False

    recursion_risk: bool = False
    repeated_prompt_risk: bool = False
    large_static_prompt: bool = False
    high_complexity: bool = False

    context_growth: bool = False  # 🔥 critical

    raw_lines: int = 0
    errors: List[str] = field(default_factory=list)


# ───────────────────────────────────────────────

class _PythonVisitor(ast.NodeVisitor):
    def __init__(self, source: str):
        self.source = source

        # metrics
        self.api_calls = 0
        self.calls_in_loops = 0
        self.loop_count = 0
        self.nested_loops = False
        self.has_loop_limiter = False

        self.context_growth = False

        # tracking
        self._loop_depth = 0
        self._string_literals: List[str] = []

        # 🔥 existing tracking (UNCHANGED)
        self._growing_vars = set()
        self.llm_classes = set()
        self.llm_objects = set()

        # context_growth: helper to walk any AST node for growing var refs
        def _contains_growing_var(node, growing):
            """Recursively check if any Name in node matches a growing var."""
            if isinstance(node, ast.Name):
                return node.id in growing
            if isinstance(node, ast.Attribute):
                return _contains_growing_var(node.value, growing)
            if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
                return any(_contains_growing_var(e, growing) for e in node.elts)
            if isinstance(node, ast.Dict):
                return any(_contains_growing_var(v, growing) for v in node.values if v)
            if isinstance(node, ast.Call):
                return (
                    _contains_growing_var(node.func, growing)
                    or any(_contains_growing_var(a, growing) for a in node.args)
                    or any(_contains_growing_var(kw.value, growing) for kw in node.keywords)
                )
            if isinstance(node, (ast.Starred, ast.UnaryOp)):
                return _contains_growing_var(node.operand if hasattr(node, 'operand') else node.value, growing)
            if isinstance(node, ast.BinOp):
                return _contains_growing_var(node.left, growing) or _contains_growing_var(node.right, growing)
            if isinstance(node, ast.IfExp):
                return any(_contains_growing_var(n, growing) for n in (node.body, node.test, node.orelse))
            return False
        self._contains_growing_var = _contains_growing_var

    # ─────────────────────────────
    # IMPORT HANDLING (aliases)
    # ─────────────────────────────
    def visit_ImportFrom(self, node):
        if node.module in {"openai", "anthropic"}:
            for alias in node.names:
                self.llm_classes.add(alias.asname or alias.name)
        self.generic_visit(node)

    # ─────────────────────────────
    # ASSIGNMENT TRACKING
    # ─────────────────────────────
    def visit_Assign(self, node):
        if isinstance(node.value, ast.Call):
            if isinstance(node.value.func, ast.Name):
                if node.value.func.id in self.llm_classes:
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            self.llm_objects.add(target.id)

        self.generic_visit(node)

    # ─────────────────────────────
    # LOOP DETECTION
    # ─────────────────────────────
    def visit_For(self, node):
        self._enter_loop()
        self.generic_visit(node)
        self._exit_loop()

    def visit_While(self, node):
        self._enter_loop()
        self.generic_visit(node)
        self._exit_loop()

    def _enter_loop(self):
        self._loop_depth += 1
        self.loop_count += 1
        if self._loop_depth > 1:
            self.nested_loops = True

    def _exit_loop(self):
        self._loop_depth -= 1

    # ─────────────────────────────
    # LLM CALL DETECTION (SAFE EXTENSION)
    # ─────────────────────────────
    def _is_llm_call(self, node: ast.Call) -> bool:
        """
        EXTENDED detection WITHOUT breaking existing logic
        """

        if isinstance(node.func, ast.Attribute):
            base = node.func.value
            method = node.func.attr.lower()

            # ─────────────────────────────
            # 1. ORIGINAL LOGIC (UNCHANGED)
            # ─────────────────────────────
            if isinstance(base, ast.Attribute):
                if isinstance(base.value, ast.Name):
                    if base.value.id in self.llm_objects:
                        return True

            if isinstance(base, ast.Name):
                if base.id in self.llm_objects:
                    return True

            # ─────────────────────────────
            # 2. GEMINI SUPPORT
            # ─────────────────────────────
            if method == "generate_content":
                return True

            # ─────────────────────────────
            # 3. CLAUDE SUPPORT
            # ─────────────────────────────
            if method == "create":
                if isinstance(base, ast.Attribute):
                    if base.attr == "messages":
                        return True

            # ─────────────────────────────
            # 4. SAFE DYNAMIC DETECTION
            # ─────────────────────────────
            LLM_METHODS = {"create", "generate", "invoke", "complete", "run"}
            LLM_ARGS = {"model", "messages", "prompt", "input"}

            if method in LLM_METHODS:
                for kw in node.keywords:
                    if kw.arg in LLM_ARGS:
                        return True

        return False

    # ─────────────────────────────
    # CALL VISIT
    # ─────────────────────────────
    def visit_Call(self, node):
        # 🔥 LLM CALL DETECTION
        if self._is_llm_call(node):
            self.api_calls += 1
            if self._loop_depth > 0:
                self.calls_in_loops += 1

        # 🔥 CONTEXT GROWTH
        # Detect variable growth inside loop
        if isinstance(node.func, ast.Attribute):
            method = node.func.attr.lower()

            if method in {"append", "extend", "insert"}:
                if self._loop_depth > 0:
                    if isinstance(node.func.value, ast.Name):
                        self._growing_vars.add(node.func.value.id)

        # Detect if growing variable is passed into LLM call
        if self._is_llm_call(node) and self._growing_vars:
            # check all positional args
            for arg in node.args:
                if self._contains_growing_var(arg, self._growing_vars):
                    self.context_growth = True
                    break
            # check all keyword values
            if not self.context_growth:
                for kw in node.keywords:
                    if self._contains_growing_var(kw.value, self._growing_vars):
                        self.context_growth = True
                        break

        self.generic_visit(node)

    # ─────────────────────────────
    # STRING ANALYSIS
    # ─────────────────────────────
    def visit_Constant(self, node):
        if isinstance(node.value, str):
            self._string_literals.append(node.value)
        self.generic_visit(node)

    def finalize(self, source: str):
        if LOOP_LIMITER_PATTERN.search(source):
            self.has_loop_limiter = True

        counts = {}
        for s in self._string_literals:
            if len(s) > 50:
                counts[s] = counts.get(s, 0) + 1

        self.repeated_prompt_risk = any(v > 1 for v in counts.values())
        self.large_static_prompt = any(len(s) > 512 for s in self._string_literals)


# ───────────────────────────────────────────────

def _analyze_python(path: Path) -> FileAnalysis:
    result = FileAnalysis(path=path, language="python")

    try:
        source = path.read_text(encoding="utf-8", errors="replace")
        result.raw_lines = source.count("\n") + 1

        tree = ast.parse(source)
        visitor = _PythonVisitor(source)
        visitor.visit(tree)
        visitor.finalize(source)

        result.api_calls = visitor.api_calls
        result.calls_in_loops = visitor.calls_in_loops
        result.loop_count = visitor.loop_count
        result.nested_loops = visitor.nested_loops
        result.has_loop_limiter = visitor.has_loop_limiter

        result.context_growth = visitor.context_growth

        result.repeated_prompt_risk = visitor.repeated_prompt_risk
        result.large_static_prompt = visitor.large_static_prompt
        result.high_complexity = bool(HIGH_COMPLEXITY_NAMES.search(path.stem))

        # ─────────────────────────────
        # RISK CLASSIFICATION
        # ─────────────────────────────
        if result.calls_in_loops > 0 and result.context_growth:
            result.recursion_risk = True   # HIGH — quadratic growth path
        elif result.calls_in_loops > 0:
            result.recursion_risk = not result.has_loop_limiter  # MEDIUM
        else:
            result.recursion_risk = False  # LOW / NONE

    except Exception as e:
        result.errors.append(str(e))

    return result


# ───────────────────────────────────────────────

def analyze(path: Path) -> FileAnalysis:
    if path.suffix == ".py":
        return _analyze_python(path)
    else:
        return FileAnalysis(path=path, language="unknown")