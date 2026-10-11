"""Static analysis: find LLM call sites and the loops, recursion and history growth around them.

Analysis runs in two passes over the project:

1. Each file is walked once to learn its imports, functions, and which functions make
   LLM calls directly. Functions that reach an LLM call through other functions - in the
   same file or an imported one - are then found by a fixpoint over the call graph.
2. Each file is walked again, now knowing which calls lead to an LLM, to record every
   call site with the loops that enclose it and to produce findings.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from agentguard.rules import RULES

# A static string at least this long (~1000 tokens at 4 chars/token) counts as a large prompt.
LARGE_PROMPT_CHARS = 4000
CHARS_PER_TOKEN = 4

_LLM_ROOTS = {"openai", "anthropic", "litellm", "ollama", "cohere", "mistralai", "groq", "together"}
_LLM_PREFIXES = ("google.generativeai", "google.genai", "langchain", "llama_index")

_PROVIDER_BY_MODULE = [
    ("openai", "openai"),
    ("langchain_openai", "openai"),
    ("anthropic", "anthropic"),
    ("langchain_anthropic", "anthropic"),
    ("google", "google"),
    ("langchain_google", "google"),
    ("ollama", "ollama"),
    ("langchain_ollama", "ollama"),
]

# Methods that send a request when called on a client/model/chain object.
_FRAMEWORK_METHODS = {
    "invoke",
    "ainvoke",
    "stream",
    "astream",
    "batch",
    "abatch",
    "predict",
    "apredict",
    "generate",
    "agenerate",
    "run",
    "arun",
    "chat",
    "achat",
    "complete",
    "acomplete",
    "send_message",
    "send_message_async",
}
# Methods that return a configured copy of an LLM object.
_WRAPPER_METHODS = {
    "bind_tools",
    "with_structured_output",
    "bind",
    "with_config",
    "with_retry",
    "with_fallbacks",
    "start_chat",
}
_GENERIC_METHODS = {"create", "acreate", "generate", "invoke", "complete", "chat", "completion", "acompletion"}
_GROW_METHODS = {"append", "extend", "insert", "add_message", "add_messages", "add_user_message", "add_ai_message"}
_SHRINK_METHODS = {"pop", "popleft", "clear", "remove"}
_LOOPS_AND_DEFS = (ast.For, ast.AsyncFor, ast.While, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
_PROMPT_CALLS = (
    "Prompt.ask",
    "Confirm.ask",
    "console.input",
    "session.prompt",
    "prompt_toolkit.prompt",
    "questionary.text",
)
_RETRY_ITERATORS = {"Retrying", "AsyncRetrying"}
_TRIM_CALL = re.compile(r"summar|trim|truncat|compact|window|prune|shorten", re.IGNORECASE)
_LITELLM_CALLS = {"litellm.completion", "litellm.acompletion", "litellm.responses", "litellm.aresponses"}
_MAX_TOKEN_KWARGS = {"max_tokens", "max_completion_tokens", "max_output_tokens"}
_LIMIT_WORDS = {
    "max",
    "limit",
    "limits",
    "cap",
    "budget",
    "depth",
    "step",
    "steps",
    "turn",
    "turns",
    "iter",
    "iters",
    "iteration",
    "iterations",
    "retry",
    "retries",
    "attempt",
    "attempts",
    "tries",
    "round",
    "rounds",
}
_DEPTH_PARAM = re.compile(r"depth|level|remaining|budget|^max_|limit", re.IGNORECASE)
_SUPPRESS = re.compile(r"#\s*agentguard:\s*ignore(?:\[([A-Z0-9,\s]+)\])?", re.IGNORECASE)
_SUPPRESS_FILE = re.compile(r"#\s*agentguard:\s*ignore-file", re.IGNORECASE)


# ─── Data model ───────────────────────────────────────────────────────────────


@dataclass
class Loop:
    line: int
    kind: str  # "fixed" | "capped" | "data" | "interactive" | "unbounded"
    count: Optional[int] = None  # iteration count when it is a known constant
    keyword: str = "for"


@dataclass
class CallSite:
    path: Path
    line: int
    col: int
    end_line: int
    end_col: int
    api: str  # e.g. "openai.chat", "anthropic.messages", "framework", "call"
    provider: str
    model: Optional[str]
    loops: List[Loop]
    function: str  # global key of the enclosing function, "<module>" for top level
    target: Optional[str] = None  # for api == "call": key of the LLM function it calls
    has_max_tokens: Optional[bool] = None  # None when the rule does not apply
    context_growth: bool = False
    system_tokens: Optional[int] = None  # size of a known large static prompt it sends
    cached: bool = False  # the file uses Anthropic prompt caching

    @property
    def in_loop(self) -> bool:
        return bool(self.loops)


@dataclass
class Finding:
    rule: str
    severity: str
    path: Path
    line: int
    col: int
    message: str
    end_line: int = 0
    end_col: int = 0

    @property
    def name(self) -> str:
        return RULES[self.rule].name

    @property
    def fix(self) -> str:
        return RULES[self.rule].fix


@dataclass
class FunctionInfo:
    key: str
    name: str
    cls: Optional[str]
    path: Path
    line: int
    params: List[str]
    calls: Set[str] = field(default_factory=set)
    direct_llm: bool = False
    mutated: Set[str] = field(default_factory=set)
    llm_refs: Set[str] = field(default_factory=set)
    fresh: Set[str] = field(default_factory=set)

    @property
    def grows_state(self) -> bool:
        """It appends to state it does not own and sends that state to the model."""
        return any(n in self.llm_refs and n not in self.fresh for n in self.mutated)


@dataclass
class FileResult:
    path: Path
    module: str
    sites: List[CallSite] = field(default_factory=list)
    findings: List[Finding] = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class ProjectAnalysis:
    root: Path
    files: List[FileResult]
    functions: Dict[str, FunctionInfo]
    llm_functions: Set[str]

    @property
    def sites(self) -> List[CallSite]:
        return [s for f in self.files for s in f.sites]

    @property
    def findings(self) -> List[Finding]:
        return [x for f in self.files for x in f.findings]


@dataclass
class _Module:
    path: Path
    module: str
    source: str
    tree: Optional[ast.Module]
    error: Optional[str] = None
    imports: Dict[str, str] = field(default_factory=dict)
    functions: Dict[str, FunctionInfo] = field(default_factory=dict)
    large_strings: Dict[str, int] = field(default_factory=dict)
    consts: Dict[str, object] = field(default_factory=dict)
    docstrings: Set[int] = field(default_factory=set)
    seq_lens: Dict[str, int] = field(default_factory=dict)  # module constants: LANGS = ("en", "ja")
    indexed: bool = False

    def index(self) -> None:
        """One walk for what both passes need: constants, large strings, docstring nodes."""
        if self.indexed or self.tree is None:
            return
        self.indexed = True
        assigned: Dict[str, int] = {}
        for node in ast.walk(self.tree):
            if isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
                for t in node.targets if isinstance(node, ast.Assign) else [node.target]:
                    if isinstance(t, ast.Name):
                        assigned[t.id] = assigned.get(t.id, 0) + 1
        for stmt in self.tree.body:
            if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
                name, value = stmt.targets[0].id, stmt.value
                n = len(value.keys) if isinstance(value, ast.Dict) else len(getattr(value, "elts", []))
                if isinstance(value, (ast.List, ast.Tuple, ast.Set, ast.Dict)) and n and assigned.get(name) == 1:
                    self.seq_lens[name] = n
        for node in ast.walk(self.tree):
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                first = node.body[0] if node.body else None
                if (
                    isinstance(first, ast.Expr)
                    and isinstance(first.value, ast.Constant)
                    and isinstance(first.value.value, str)
                ):
                    self.docstrings.add(id(first.value))
            elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                name, value = node.targets[0].id, node.value
                if isinstance(value, ast.Constant) and type(value.value) in (int, str):
                    self.consts[name] = value.value
                n = _static_text_len(value)
                if n >= LARGE_PROMPT_CHARS:
                    self.large_strings[name] = n // CHARS_PER_TOKEN


@dataclass
class _Client:
    provider: str
    model: Optional[str]


@dataclass
class _Frame:
    loop: Loop
    grown: Set[str] = field(default_factory=set)
    trimmed: Set[str] = field(default_factory=set)
    uses: List[Tuple[CallSite, Set[str]]] = field(default_factory=list)


# ─── Small AST helpers ────────────────────────────────────────────────────────


def _dotted(node: ast.AST) -> Optional[str]:
    """``a.b.c`` for a Name/Attribute chain, else None."""
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return ".".join(reversed(parts))
    return None


def _attr_chain(node: ast.AST) -> Tuple[ast.AST, List[str]]:
    """Split ``x.a.b.c`` into (x, ["a", "b", "c"]); x may be any expression."""
    names = []
    while isinstance(node, ast.Attribute):
        names.append(node.attr)
        node = node.value
    return node, list(reversed(names))


def _refs(node: ast.AST) -> Set[str]:
    """Every variable an expression reads, as dotted names (``x``, ``self.history``)."""
    out = set()
    for sub in ast.walk(node):
        if isinstance(sub, (ast.Name, ast.Attribute)):
            d = _dotted(sub)
            if d:
                out.add(d)
    return out


def _int_const(node: ast.AST) -> Optional[int]:
    if isinstance(node, ast.Constant) and type(node.value) is int:
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        v = _int_const(node.operand)
        return -v if v is not None else None
    return None


def _static_text_len(node: ast.AST) -> int:
    """Length of the static text in a string expression: literals, f-string text,
    concatenation, repetition, and wrappers such as textwrap.dedent()."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return len(node.value)
    if isinstance(node, ast.JoinedStr):
        return sum(len(v.value) for v in node.values if isinstance(v, ast.Constant) and isinstance(v.value, str))
    if isinstance(node, ast.BinOp):
        if isinstance(node.op, ast.Add):
            return _static_text_len(node.left) + _static_text_len(node.right)
        if isinstance(node.op, ast.Mult):
            for text, count in ((node.left, node.right), (node.right, node.left)):
                n = _int_const(count)
                if n is not None and n > 0:
                    return _static_text_len(text) * n
    if isinstance(node, ast.Call) and node.args:
        name = (_dotted(node.func) or "").rsplit(".", 1)[-1]
        if name in ("dedent", "strip", "lstrip", "rstrip", "cleandoc", "format"):
            target = node.func.value if name == "format" and isinstance(node.func, ast.Attribute) else node.args[0]
            return _static_text_len(target)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in ("strip", "format"):
        return _static_text_len(node.func.value)
    return 0


def _is_window(value: ast.AST, name: str) -> bool:
    """``x[-k:]``, ``x[:1] + x[-k:]``, ``[*x[:1], *x[-k:]]``: only slices of x (and literals)."""

    def is_slice(n: ast.AST) -> bool:
        return isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Slice) and _dotted(n.value) == name

    if is_slice(value):
        return True
    if isinstance(value, ast.BinOp) and isinstance(value.op, ast.Add):
        parts = [value.left, value.right]
    elif isinstance(value, (ast.List, ast.Tuple)):
        parts = [e.value if isinstance(e, ast.Starred) else e for e in value.elts]
    else:
        return False
    return all(is_slice(p) or _is_window(p, name) or name not in _refs(p) for p in parts)


def _words(name: str) -> List[str]:
    name = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    return [w for w in name.lower().split("_") if w]


def _is_limit_name(name: str) -> bool:
    return any(w in _LIMIT_WORDS for w in _words(name.rsplit(".", 1)[-1]))


def is_llm_module(dotted: str) -> bool:
    return dotted.split(".")[0] in _LLM_ROOTS or dotted.startswith(_LLM_PREFIXES)


def _provider_for(dotted: str) -> str:
    for prefix, provider in _PROVIDER_BY_MODULE:
        if dotted == prefix or dotted.startswith(prefix + ".") or dotted.startswith(prefix + "_"):
            return provider
    return "unknown"


def _is_constructor(dotted: str) -> bool:
    """Does calling this imported name build an LLM client or chat model?"""
    if not is_llm_module(dotted) or ".types." in dotted or ".errors" in dotted:
        return False
    last = dotted.rsplit(".", 1)[-1]
    if last == "init_chat_model":
        return True
    if not last[:1].isupper():
        return False
    if dotted.startswith("langchain"):
        return last.startswith("Chat") or last in {"OpenAI", "Anthropic", "Ollama", "VertexAI", "GoogleGenerativeAI"}
    if dotted.startswith("llama_index"):
        return ".llms." in dotted
    return "Error" not in last and "Exception" not in last


# ─── The visitor ──────────────────────────────────────────────────────────────

# resolve(ref, cls) -> (function key, info) when ``ref`` called from class ``cls`` is an LLM function.
Resolver = Callable[[str, Optional[str]], Optional[Tuple[str, FunctionInfo]]]


class _Visitor(ast.NodeVisitor):
    def __init__(
        self, mod: _Module, resolve: Optional[Resolver] = None, imported_strings: Optional[Dict[str, int]] = None
    ):
        self.mod = mod
        self.resolve = resolve
        mod.index()
        self.consts: Dict[str, object] = mod.consts
        self.large_strings: Dict[str, int] = {**mod.large_strings, **(imported_strings or {})}
        self.clients: Dict[str, _Client] = {}
        self.instances: Dict[str, str] = {}  # variable -> class name it was built from
        self.imports: Dict[str, str] = {}
        self.functions: Dict[str, FunctionInfo] = {}
        self.sites: List[CallSite] = []
        self._fn_stack: List[FunctionInfo] = []
        self._cls_stack: List[str] = []
        self._frames: List[_Frame] = []
        self._uses_cache = "cache_control" in mod.source
        assert mod.tree is not None
        self._docstrings = mod.docstrings
        self._module_fn = FunctionInfo(
            key=f"{mod.module}:<module>", name="<module>", cls=None, path=mod.path, line=1, params=[]
        )

    @property
    def _fn(self) -> FunctionInfo:
        return self._fn_stack[-1] if self._fn_stack else self._module_fn

    # Leaves: nothing below them to visit.
    def visit_Constant(self, node: ast.Constant) -> None:
        pass

    def visit_Name(self, node: ast.Name) -> None:
        pass

    # ── imports ──
    def _absolute(self, module: Optional[str], level: int) -> str:
        if level == 0:
            return module or ""
        base = self.mod.module.split(".")
        if self.mod.path.name != "__init__.py":
            base = base[:-1]
        base = base[: len(base) - (level - 1)] if level > 1 else base
        return ".".join([*base, module] if module else base)

    def visit_Import(self, node: ast.Import) -> None:
        for a in node.names:
            if a.asname:
                self.imports[a.asname] = a.name
            else:
                root = a.name.split(".")[0]
                self.imports[root] = root

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        base = self._absolute(node.module, node.level)
        for a in node.names:
            self.imports[a.asname or a.name] = f"{base}.{a.name}" if base else a.name

    def _abs_name(self, node: ast.AST) -> Optional[str]:
        """Fully qualified name of a Name/Attribute chain whose root is an import."""
        d = _dotted(node)
        if not d:
            return None
        root, _, rest = d.partition(".")
        if root in self.imports:
            return self.imports[root] + ("." + rest if rest else "")
        return None

    # ── scopes ──
    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._cls_stack.append(node.name)
        self.generic_visit(node)
        self._cls_stack.pop()

    def _visit_function(self, node) -> None:
        cls = self._cls_stack[-1] if self._cls_stack else None
        parent = self._fn_stack[-1].key.split(":", 1)[1] + "." if self._fn_stack else (f"{cls}." if cls else "")
        qual = parent + node.name
        a = node.args
        params = [p.arg for p in [*a.posonlyargs, *a.args, *a.kwonlyargs]]
        info = FunctionInfo(
            key=f"{self.mod.module}:{qual}",
            name=node.name,
            cls=cls,
            path=self.mod.path,
            line=node.lineno,
            params=params,
        )
        self.functions[qual] = info
        # A function body runs in its own invocation; enclosing loops do not apply to it.
        saved = self._frames
        self._frames = []
        self._fn_stack.append(info)
        for d in node.decorator_list:
            self.visit(d)
        for stmt in node.body:
            self.visit(stmt)
        self._fn_stack.pop()
        self._frames = saved

    visit_FunctionDef = _visit_function
    visit_AsyncFunctionDef = _visit_function

    # ── assignments: client tracking, history growth/trimming ──
    def _client_from(self, value: ast.AST) -> Optional[_Client]:
        if isinstance(value, ast.Call):
            absn = self._abs_name(value.func)
            if absn and _is_constructor(absn):
                return _Client(_provider_for(absn), self._model_kwarg(value, positional=True))
            _, chain = _attr_chain(value.func)
            receiver = self._tracked_receiver(value.func)
            if (
                receiver is not None
                and chain
                and (chain[-1] in _WRAPPER_METHODS or ".".join(chain).endswith("chats.create"))
            ):
                model = self._model_kwarg(value) or receiver.model
                return _Client(receiver.provider, model)
        if isinstance(value, ast.BinOp) and isinstance(value.op, ast.BitOr):
            for side in (value.left, value.right):
                c = self._client_from(side) or self.clients.get(_dotted(side) or "")
                if c:
                    return c
        d = _dotted(value)
        if d and d in self.clients:
            return self.clients[d]
        return None

    def _track_targets(self, targets: Iterable[ast.AST], value: ast.AST) -> None:
        client = self._client_from(value)
        cls = None
        if isinstance(value, ast.Call) and isinstance(value.func, ast.Name) and value.func.id[:1].isupper():
            cls = value.func.id
        for t in targets:
            d = _dotted(t)
            if not d:
                continue
            if client:
                self.clients[d] = client
            elif cls:
                self.instances[d] = cls
            self._note_assignment(d, value)

    def _note_assignment(self, name: str, value: ast.AST) -> None:
        used = _refs(value)
        if name in used:
            if _is_window(value, name):
                self._trim(name)  # x = x[-k:], x = x[:1] + x[-k:]
            elif isinstance(value, ast.Call) and _TRIM_CALL.search(_dotted(value.func) or ""):
                self._trim(name)  # x = summarize(x)
            else:
                self._grow(name)  # x = x + [...], x = [*x, ...]
        else:
            self._fn.fresh.add(name)
            if self._frames:
                self._trim(name)  # rebinding inside the loop resets it

    def visit_Assign(self, node: ast.Assign) -> None:
        self.visit(node.value)
        self._track_targets(node.targets, node.value)
        for t in node.targets:
            if isinstance(t, ast.Subscript):
                self.visit(t)
                if isinstance(t.slice, ast.Slice):
                    d = _dotted(t.value)
                    if d:
                        self._trim(d)  # x[:] = ...

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if node.value is not None:
            self.visit(node.value)
            self._track_targets([node.target], node.value)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        self.visit(node.value)
        d = _dotted(node.target)
        numeric = isinstance(node.value, ast.Constant) and isinstance(node.value.value, (int, float))
        if d and isinstance(node.op, ast.Add) and not numeric and _int_const(node.value) is None:
            self._grow(d)

    def visit_Delete(self, node: ast.Delete) -> None:
        for t in node.targets:
            if isinstance(t, ast.Subscript):
                d = _dotted(t.value)
                if d:
                    self._trim(d)
        self.generic_visit(node)

    def _visit_with(self, node) -> None:
        for item in node.items:
            self.visit(item.context_expr)
            if item.optional_vars is not None:
                self._track_targets([item.optional_vars], item.context_expr)
        for stmt in node.body:
            self.visit(stmt)

    visit_With = _visit_with
    visit_AsyncWith = _visit_with

    def _grow(self, name: str) -> None:
        self._fn.mutated.add(name)
        for f in self._frames:
            f.grown.add(name)

    def _trim(self, name: str) -> None:
        for f in self._frames:
            f.trimmed.add(name)

    # ── loops ──
    def _limit(self, node: ast.AST) -> Tuple[bool, Optional[int]]:
        v = _int_const(node)
        if v is None and isinstance(node, ast.Name) and type(self.consts.get(node.id)) is int:
            v = self.consts[node.id]  # type: ignore[assignment]
        if v is not None:
            return v > 1, v
        d = _dotted(node)
        if d and _is_limit_name(d):
            return True, None
        return False, None

    def _cap(self, test: ast.AST) -> Tuple[bool, Optional[int]]:
        for node in ast.walk(test):
            if not isinstance(node, ast.Compare):
                continue
            if any(isinstance(op, (ast.In, ast.NotIn, ast.Is, ast.IsNot)) for op in node.ops):
                continue
            for side in [node.left, *node.comparators]:
                ok, val = self._limit(side)
                if ok:
                    return True, val
        if isinstance(test, (ast.Name, ast.Attribute)) and _is_limit_name(_dotted(test) or ""):
            return True, None  # e.g. `if budget_exhausted: break`
        return False, None

    def _capped_by_break(self, body: Sequence[ast.stmt]) -> Tuple[bool, Optional[int]]:
        """Does a counter check in this loop body stop the loop, or stop the calls in it?

        Recognised: `if <cap>: break/return/raise/continue`, a countdown (`n -= 1` ...
        `if n <= 0: ...`), and a cap that sets a flag tested elsewhere
        (`if delay > TIMEOUT: retry = False` ... `if not retry: return`).
        """
        ifs: List[ast.If] = []
        countdown: Set[str] = set()
        stack = list(body)
        while stack:
            stmt = stack.pop()
            if isinstance(stmt, _LOOPS_AND_DEFS):
                continue
            if isinstance(stmt, ast.AugAssign) and isinstance(stmt.op, ast.Sub):
                d = _dotted(stmt.target)
                if d:
                    countdown.add(d)
            elif isinstance(stmt, ast.If):
                ifs.append(stmt)
                stack.extend(stmt.body)
                stack.extend(stmt.orelse)
            elif isinstance(stmt, (ast.With, ast.AsyncWith, ast.Try)):
                stack.extend(stmt.body)
                for h in getattr(stmt, "handlers", []):
                    stack.extend(h.body)
                stack.extend(getattr(stmt, "orelse", []))

        def exits(stmts: Sequence[ast.stmt]) -> bool:
            return any(isinstance(x, (ast.Break, ast.Return, ast.Raise, ast.Continue)) for x in stmts)

        flags: Set[str] = set()
        for node in ifs:
            ok, val = self._cap(node.test)
            if not ok and self._countdown_check(node.test, countdown):
                ok, val = True, None
            if not ok:
                continue
            if exits(node.body):
                return True, val
            for x in node.body:
                if isinstance(x, ast.Assign):
                    flags |= {d for t in x.targets if (d := _dotted(t))}
        for node in ifs:
            if exits(node.body) and _refs(node.test) & flags:
                return True, None
        return False, None

    def _countdown_check(self, test: ast.AST, countdown: Set[str]) -> bool:
        for node in ast.walk(test):
            if isinstance(node, ast.Compare):
                sides = [node.left, *node.comparators]
                if any(_dotted(x) in countdown for x in sides) and any(_int_const(x) is not None for x in sides):
                    return True
        return False

    def _interactive(self, body: Sequence[ast.stmt]) -> bool:
        """Does each iteration wait for a person (input(), a prompt)? Then it is human-paced."""
        stack: List[ast.AST] = list(body)
        while stack:
            node = stack.pop()
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
                continue
            if isinstance(node, ast.Call):
                d = _dotted(node.func) or ""
                if d in ("input", "raw_input") or d.endswith(_PROMPT_CALLS):
                    return True
            stack.extend(ast.iter_child_nodes(node))
        return False

    def _for_loop(self, iterable: ast.AST, line: int, keyword: str) -> Loop:
        if isinstance(iterable, ast.Call):
            name = _dotted(iterable.func) or ""
            if name.rsplit(".", 1)[-1] in {"count", "cycle", "repeat"} and not (
                name.endswith("repeat") and len(iterable.args) > 1
            ):
                return Loop(line, "unbounded", keyword=keyword)
            if name.rsplit(".", 1)[-1] in _RETRY_ITERATORS:  # tenacity: one attempt per iteration
                return Loop(line, "capped", keyword="retry")
            if name == "range":
                vals = [self._limit(a)[1] if _int_const(a) is None else _int_const(a) for a in iterable.args]
                if vals and all(v is not None for v in vals):
                    return Loop(line, "fixed", len(range(*vals)), keyword)  # type: ignore[arg-type]
                return Loop(line, "capped", keyword=keyword)
        if isinstance(iterable, (ast.List, ast.Tuple, ast.Set)):
            return Loop(line, "fixed", len(iterable.elts), keyword)
        if isinstance(iterable, ast.Name) and iterable.id in self.mod.seq_lens:
            return Loop(line, "fixed", self.mod.seq_lens[iterable.id], keyword)
        return Loop(line, "data", keyword=keyword)

    def _run_loop(self, loop: Loop, body: Sequence[ast.AST]) -> None:
        frame = _Frame(loop)
        self._frames.append(frame)
        for stmt in body:
            self.visit(stmt)
        self._frames.pop()
        live = frame.grown - frame.trimmed
        for site, refs in frame.uses:
            if refs & live:
                site.context_growth = True

    def visit_For(self, node) -> None:
        self.visit(node.iter)
        loop = self._for_loop(node.iter, node.lineno, "async for" if isinstance(node, ast.AsyncFor) else "for")
        if loop.kind in ("data", "unbounded") and self._interactive(node.body):
            loop = Loop(node.lineno, "interactive", keyword=loop.keyword)
        self._run_loop(loop, node.body)
        for stmt in node.orelse:
            self.visit(stmt)

    visit_AsyncFor = visit_For

    def visit_While(self, node: ast.While) -> None:
        self.visit(node.test)
        test = node.test
        always = isinstance(test, ast.Constant) and bool(test.value)
        loop: Loop
        if (
            not always
            and any(isinstance(n, ast.Call) and _dotted(n.func) == "len" for n in ast.walk(test))
            and not self._cap(test)[0]
        ):
            loop = Loop(node.lineno, "data", keyword="while")
        else:
            ok, val = (False, None) if always else self._cap(test)
            if not ok:
                ok, val = self._capped_by_break(node.body)
            if ok:
                loop = Loop(node.lineno, "fixed" if val else "capped", val, "while")
            elif self._interactive(node.body):
                loop = Loop(node.lineno, "interactive", keyword="while")
            else:
                loop = Loop(node.lineno, "unbounded", keyword="while")
        self._run_loop(loop, node.body)
        for stmt in node.orelse:
            self.visit(stmt)

    def _visit_comp(self, node) -> None:
        loops = []
        for gen in node.generators:
            self.visit(gen.iter)
            loops.append(self._for_loop(gen.iter, node.lineno, "comprehension"))
        elts = [node.key, node.value] if isinstance(node, ast.DictComp) else [node.elt]
        ifs = [i for g in node.generators for i in g.ifs]
        frames = [_Frame(lp) for lp in loops]
        self._frames.extend(frames)
        for e in [*ifs, *elts]:
            self.visit(e)
        del self._frames[len(self._frames) - len(frames) :]
        for frame in frames:
            live = frame.grown - frame.trimmed
            for site, refs in frame.uses:
                if refs & live:
                    site.context_growth = True

    visit_ListComp = visit_SetComp = visit_DictComp = visit_GeneratorExp = _visit_comp

    # ── calls ──
    def _model_kwarg(self, call: ast.Call, positional: bool = False) -> Optional[str]:
        for kw in call.keywords:
            if kw.arg in ("model", "model_name"):
                return self._str_value(kw.value)
        if positional and call.args:
            return self._str_value(call.args[0])
        return None

    def _str_value(self, node: ast.AST) -> Optional[str]:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.Name) and isinstance(self.consts.get(node.id), str):
            return self.consts[node.id]  # type: ignore[return-value]
        return None

    def _tracked_receiver(self, func: ast.AST) -> Optional[_Client]:
        """The tracked client this attribute call is made on, if any (longest prefix wins)."""
        d = _dotted(func.value) if isinstance(func, ast.Attribute) else None
        while d:
            if d in self.clients:
                return self.clients[d]
            d = d.rpartition(".")[0]
        return None

    def _classify(self, call: ast.Call) -> Optional[Tuple[str, str, Optional[str]]]:
        """(api, provider, model) if this call sends a request to an LLM."""
        func = call.func
        _, chain = _attr_chain(func)
        joined = ".".join(chain)
        model = self._model_kwarg(call)
        receiver = self._tracked_receiver(func)
        absn = self._abs_name(func) or ""

        def prov(default: str) -> str:
            return receiver.provider if receiver and receiver.provider != "unknown" else default

        if joined.endswith(("chat.completions.create", "chat.completions.parse", "chat.completions.stream")):
            return "openai.chat", prov("openai"), model
        if joined.endswith(("responses.create", "responses.parse", "responses.stream")):
            return "openai.responses", prov("openai"), model
        if joined.endswith(("ChatCompletion.create", "ChatCompletion.acreate")) and absn.startswith("openai"):
            return "openai.chat", "openai", model
        if joined.endswith(("messages.create", "messages.stream", "messages.parse")) and "batches" not in joined:
            return "anthropic.messages", prov("anthropic"), model
        if chain and chain[-1] in ("generate_content", "generate_content_async", "generate_content_stream"):
            return "google.generate_content", "google", model or (receiver.model if receiver else None)
        written = _dotted(func) or ""
        if absn in _LITELLM_CALLS or written in _LITELLM_CALLS:  # also `from wrapper import litellm`
            return "litellm", "unknown", model
        if absn in ("ollama.chat", "ollama.generate", "ollama.AsyncClient.chat"):
            return "ollama", "ollama", model
        if receiver is not None and chain and chain[-1] in _FRAMEWORK_METHODS:
            return "framework", receiver.provider, model or receiver.model
        d = _dotted(func)
        if d and d in self.clients:  # llm(prompt), the legacy LangChain __call__
            c = self.clients[d]
            return "framework", c.provider, c.model
        if chain and chain[-1] in _GENERIC_METHODS and any(kw.arg == "messages" for kw in call.keywords):
            return "generic", "unknown", model
        return None

    def _call_ref(self, func: ast.AST) -> Optional[str]:
        if isinstance(func, ast.Name):
            return func.id
        if isinstance(func, ast.Attribute):
            owner = _dotted(func.value)
            if owner in self.instances:
                return f"{self.instances[owner]}.{func.attr}"
            if isinstance(func.value, ast.Name):
                return f"{func.value.id}.{func.attr}"
        return None

    def _args_refs(self, call: ast.Call) -> Tuple[Set[str], int]:
        refs: Set[str] = set()
        inline = 0
        for a in [*call.args, *(kw.value for kw in call.keywords)]:
            for sub in ast.walk(a):
                if isinstance(sub, (ast.Name, ast.Attribute)):
                    d = _dotted(sub)
                    if d:
                        refs.add(d)
                elif isinstance(sub, (ast.Constant, ast.JoinedStr)) and id(sub) not in self._docstrings:
                    inline = max(inline, _static_text_len(sub) // CHARS_PER_TOKEN)
        return refs, inline

    def _new_site(
        self, call: ast.Call, api: str, provider: str, model: Optional[str], refs: Set[str], inline: int
    ) -> CallSite:
        loops = [f.loop for f in self._frames]
        system = max([inline] + [self.large_strings.get(r, 0) for r in refs]) or None
        if system is not None and system * CHARS_PER_TOKEN < LARGE_PROMPT_CHARS:
            system = None
        site = CallSite(
            path=self.mod.path,
            line=call.lineno,
            col=call.col_offset + 1,
            end_line=getattr(call, "end_lineno", call.lineno) or call.lineno,
            end_col=(getattr(call, "end_col_offset", call.col_offset) or call.col_offset) + 1,
            api=api,
            provider=provider,
            model=model,
            loops=loops,
            function=self._fn.key,
            system_tokens=system,
            cached=self._uses_cache,
        )
        for f in self._frames:
            f.uses.append((site, refs))
        self.sites.append(site)
        return site

    def visit_Call(self, node: ast.Call) -> None:
        fn = self._fn
        ref = self._call_ref(node.func)
        if ref:
            fn.calls.add(ref)

        if isinstance(node.func, ast.Attribute):
            d = _dotted(node.func.value)
            if d and node.func.attr in _GROW_METHODS:
                self._grow(d)
            elif d and node.func.attr in _SHRINK_METHODS:
                self._trim(d)

        kind = self._classify(node)
        if kind:
            api, provider, model = kind
            refs, inline = self._args_refs(node)
            fn.direct_llm = True
            fn.llm_refs |= refs
            site = self._new_site(node, api, provider, model, refs, inline)
            if api.startswith("openai") or api == "litellm":
                kwargs = {kw.arg for kw in node.keywords}
                site.has_max_tokens = None in kwargs or bool(kwargs & _MAX_TOKEN_KWARGS)
        elif ref and self.resolve:
            hit = self.resolve(ref, self._cls_stack[-1] if self._cls_stack else None)
            if hit:
                key, info = hit
                refs, inline = self._args_refs(node)
                fn.llm_refs |= refs
                site = self._new_site(node, "call", "unknown", None, refs, inline)
                site.target = key
                if self._frames and info.grows_state:
                    site.context_growth = True
        self.generic_visit(node)


# ─── Project-level analysis ───────────────────────────────────────────────────


def _module_name(path: Path, root: Path) -> str:
    try:
        rel = path.resolve().relative_to(root.resolve())
    except ValueError:
        rel = Path(path.name)
    parts = list(rel.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts) or path.stem


def _load(path: Path, root: Path) -> _Module:
    module = _module_name(path, root)
    try:
        source = path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError as e:
        return _Module(path, module, "", None, error=f"could not read file: {e}")
    try:
        tree = ast.parse(source, filename=str(path))
    except (SyntaxError, ValueError) as e:
        return _Module(path, module, source, None, error=f"syntax error: {e}")
    return _Module(path, module, source, tree)


def analyze_project(files: Sequence[Path], root: Path) -> ProjectAnalysis:
    mods = [_load(p, root) for p in files]
    by_name: Dict[str, _Module] = {m.module: m for m in mods}

    # Pass 1: imports, functions, direct LLM use.
    for m in mods:
        if m.tree is None:
            continue
        v = _Visitor(m)
        v.visit(m.tree)
        m.imports, m.functions = v.imports, v.functions
        m.functions["<module>"] = v._module_fn

    # The scan root may sit above the package root (e.g. a src/ layout), so a module
    # can also be found by a unique dotted suffix of its name.
    by_suffix: Dict[str, List[_Module]] = {}
    for name, mod in by_name.items():
        parts = name.split(".")
        for i in range(1, len(parts)):
            by_suffix.setdefault(".".join(parts[i:]), []).append(mod)

    def find_module(dotted: str) -> Optional[_Module]:
        if dotted in by_name:
            return by_name[dotted]
        hits = by_suffix.get(dotted, [])
        return hits[0] if len(hits) == 1 else None

    def lookup(m: _Module, ref: str, cls: Optional[str]) -> Optional[FunctionInfo]:
        head, _, tail = ref.partition(".")
        if head == "self" and tail and cls:
            return m.functions.get(f"{cls}.{tail}")
        if not tail:
            if ref in m.functions:
                return m.functions[ref]
            target = m.imports.get(ref)
            if target:
                mod_name, _, fn_name = target.rpartition(".")
                other = find_module(mod_name)
                return other.functions.get(fn_name) if other else None
            return None
        if ref in m.functions:  # Class.method, local class
            return m.functions[ref]
        target = m.imports.get(head)
        if target:
            other = find_module(target)
            if other:  # module.function
                return other.functions.get(tail)
            mod_name, _, cls_name = target.rpartition(".")
            other = find_module(mod_name)  # imported Class.method
            return other.functions.get(f"{cls_name}.{tail}") if other else None
        return None

    functions = {f.key: f for m in mods for f in m.functions.values()}
    edges: Dict[str, Set[str]] = {}
    for m in mods:
        for f in m.functions.values():
            outs = set()
            for ref in f.calls:
                hit = lookup(m, ref, f.cls)
                if hit and hit.name != "<module>":
                    outs.add(hit.key)
            edges[f.key] = outs

    llm = {k for k, f in functions.items() if f.direct_llm and f.name != "<module>"}
    changed = True
    while changed:
        changed = False
        for k, outs in edges.items():
            if k not in llm and functions[k].name != "<module>" and outs & llm:
                llm.add(k)
                changed = True

    # Pass 2: call sites in loop context, then findings.
    results = []
    for m in mods:
        result = FileResult(m.path, m.module, error=m.error)
        results.append(result)
        if m.tree is None:
            continue
        # Only files that call a model, directly or through a function, can have call sites.
        if not any(f.direct_llm or edges.get(f.key, set()) & llm for f in m.functions.values()):
            continue

        def resolve(ref: str, cls: Optional[str], m: _Module = m) -> Optional[Tuple[str, FunctionInfo]]:
            hit = lookup(m, ref, cls)
            return (hit.key, hit) if hit and hit.key in llm else None

        imported = {}
        for local, target in m.imports.items():
            mod_name, _, attr = target.rpartition(".")
            other = find_module(mod_name)
            if other and attr in other.large_strings:
                imported[local] = other.large_strings[attr]

        v = _Visitor(m, resolve, imported)
        v.visit(m.tree)
        result.sites = v.sites
        result.findings = _site_findings(v.sites)

    for key in sorted(llm):
        f = functions[key]
        if _reaches(key, key, edges) and not any(_DEPTH_PARAM.search(p) for p in f.params):
            owner = next((r for r in results if r.path == f.path), None)
            if owner is not None:
                owner.findings.append(
                    Finding(
                        "AG005",
                        "high",
                        f.path,
                        f.line,
                        1,
                        f"`{f.name}` makes LLM calls and calls itself, with no depth parameter to stop it",
                    )
                )

    for r, m in zip(results, mods):
        r.findings = sorted(_suppress(r.findings, m.source), key=lambda x: (x.line, x.col, x.rule))
    return ProjectAnalysis(root, results, functions, llm)


def _reaches(start: str, goal: str, edges: Dict[str, Set[str]]) -> bool:
    seen: Set[str] = set()
    stack = list(edges.get(start, ()))
    while stack:
        k = stack.pop()
        if k == goal:
            return True
        if k not in seen:
            seen.add(k)
            stack.extend(edges.get(k, ()))
    return False


def _describe(site: CallSite) -> str:
    return f"call to `{site.target.split(':', 1)[1]}`" if site.target else f"LLM call ({site.api})"


def _site_findings(sites: List[CallSite]) -> List[Finding]:
    out = []
    for s in sites:

        def add(rule: str, msg: str, severity: Optional[str] = None, s: CallSite = s) -> None:
            out.append(
                Finding(rule, severity or RULES[rule].severity, s.path, s.line, s.col, msg, s.end_line, s.end_col)
            )

        what = _describe(s)
        unbounded = [lp for lp in s.loops if lp.kind == "unbounded"]
        open_loops = [lp for lp in s.loops if lp.kind != "fixed"]
        if unbounded:
            lp = unbounded[-1]
            add("AG001", f"{what} inside `{lp.keyword}` loop (line {lp.line}) with no iteration cap")
        if s.context_growth:
            big = bool(open_loops) or any((lp.count or 0) > 20 for lp in s.loops)
            add(
                "AG002",
                f"{what} re-sends a history that grows every iteration; input tokens grow quadratically",
                "high" if big else "medium",
            )
        if len(open_loops) >= 2:
            lines = ", ".join(str(lp.line) for lp in open_loops)
            add("AG003", f"{what} inside {len(open_loops)} nested loops (lines {lines}); calls multiply")
        elif not unbounded and any(lp.kind == "data" for lp in s.loops):
            add("AG004", f"{what} runs once per item of a collection")
        if s.has_max_tokens is False:
            add("AG006", f"{what} sets no output-token cap")
        if s.in_loop and s.system_tokens and s.provider == "anthropic" and not s.cached:
            add("AG007", f"~{s.system_tokens:,}-token static prompt re-sent each iteration with no `cache_control`")
    return out


def _suppress(findings: List[Finding], source: str) -> List[Finding]:
    if _SUPPRESS_FILE.search(source):
        return []
    lines = source.splitlines()
    kept = []
    for f in findings:
        text = lines[f.line - 1] if 0 < f.line <= len(lines) else ""
        m = _SUPPRESS.search(text)
        if m and (not m.group(1) or f.rule in {c.strip().upper() for c in m.group(1).split(",")}):
            continue
        kept.append(f)
    return kept
