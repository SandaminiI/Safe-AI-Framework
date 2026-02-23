"""
Language detection via:
  1. File extension  (highest confidence: 0.95)
  2. Keyword/pattern heuristics over the source text

Supported: java, python, typescript, javascript
"""
import re
from typing import Optional, Tuple

# ---------------------------------------------------------
# Extension map
# ---------------------------------------------------------
_EXT: dict[str, str] = {
    ".py": "python",
    ".java": "java",
    ".ts": "typescript",
    ".js": "javascript",
}

# ---------------------------------------------------------
# Java hints
# ---------------------------------------------------------
_JAVA_HINTS = [
    r"\bclass\s+\w+",                         # class declarations
    r"\binterface\s+\w+",                     # interface declarations
    r"\bpublic\b",                            # public modifier
    r"\bprivate\b",                           # private modifier
    r"\bprotected\b",                         # protected modifier
    r"\bpackage\s+\w+",                       # package statement
    r"\bimport\s+java\.",                     # Java imports
    r"\bvoid\s+\w+\s*\(",                     # void methods
    r"System\.out\.println",                  # print statements
    r"new\s+\w+\s*\(",                        # object creation
    r"\bpublic\s+static\s+void\s+main\s*\(",  # entry point
    r"\bSystem\.err\.println",                # error print
    r"@\w+",                                  # annotations
    r"\bextends\s+\w+",                       # inheritance
    r"\bimplements\s+\w+",                    # interfaces
    r"\bthrows\s+\w+",                        # exception handling
    r"\btry\s*\{",                            # try block
    r"\bcatch\s*\(",                          # catch block
    r"\bfinally\s*\{",                        # finally block
    r"<\w+>",                                 # generics syntax
    r"List<\w+>",                             # collections
    r"Map<\w+,\s*\w+>",                       # maps
]  

# ---------------------------------------------------------
# Python hints  (carefully tuned to avoid TypeScript overlap)
# ---------------------------------------------------------
_PY_HINTS = [
    r"\bdef\s+\w+\s*\(",                          # def func(
    r"\bself\b",                                   # self (Python-only)
    r"__init__\s*\(",                              # constructor
    r"__name__",                                   # entry point guard
    r":\s*\n\s+\S",                                # colon + indented block (Python indent)
    r"\bprint\s*\(",                               # print() call
    r"\bimport\s+\w+",                             # plain import
    r"\bfrom\s+\w[\w.]*\s+import\b",              # from x import y
    r"\bNone\b",                                   # None (Python-only keyword)
    r"\bTrue\b|\bFalse\b",                         # Python bool literals
    r"\bpass\b",                                   # Python-only
    r"\blamda\b|\blambda\s+",                      # lambda
    r"\basync\s+def\b",                            # async def
    r"\bawait\b",                                  # await keyword
    r"@\w+",                                       # decorators
    r"\btry\s*:\s*\n",                             # try: (Python syntax)
    r"\bexcept\b",                                 # except
    r"\bwith\s+\w+",                               # with statement
    r"f['\"]",                                     # f-strings
    r"\bself\.",                                   # self.x
    r"\blen\s*\(",                                 # built-in len()
    r"\bdict\s*\(|\blist\s*\(|\bset\s*\(",        # dict/list/set constructor
    r"#\s+.*$",                                    # Python single-line comments
    r"\bOptional\[",                               # typing.Optional
    r"\bList\[|\bDict\[|\bTuple\[|\bSet\[",        # typing generics
    r"\bdataclass\b",                              # @dataclass
    r"\bABC\b",                                    # Abstract base class
    r"__str__\s*\(|__repr__\s*\(",                 # dunder methods
]

# ---------------------------------------------------------
# TypeScript hints
# ---------------------------------------------------------
_TS_HINTS = [
    r"\binterface\s+\w+",
    r"\bimplements\b",
    r"\bexport\b",
    r"\bimport\s+\{?\w+",
    r"\bclass\s+\w+",
    r"\bextends\s+\w+",
    r"\bconstructor\s*\(",
    r"\bfunction\s+\w+",
    r"=>\s*\{",
    r"console\.log",
    r"\btype\s+\w+\s*=",
    r"\benum\s+\w+",
    r":\s*\w+",
    r"\bPromise<\w+>",
    r"@\w+",
    r"\breadonly\b",
    r"\bprivate\b",
    r"\bpublic\b",
    r"\bprotected\b",
    r"\bget\s+\w+",
    r"\bset\s+\w+",
    r"\bnamespace\s+\w+",
]

# ---------------------------------------------------------
# Scorer
# ---------------------------------------------------------
def _score(patterns: list[str], text: str) -> float:
    hits = sum(bool(re.search(p, text, re.M)) for p in patterns)
    if hits >= 10:
        return 1.0
    if hits >= 6:
        return round(0.6 + (hits - 6) * (0.4 / 4), 2)
    return round(hits * (0.6 / 6), 2)

# ---------------------------------------------------------
# Public API
# ---------------------------------------------------------
def detect_language(
    code: str,
    filename: Optional[str] = None,
) -> Tuple[str, float, str]:
    """
    Returns (language, confidence, reason).

    reason is one of: "extension" | "heuristic" | "none"
    """
    # 1) Extension takes precedence
    if filename:
        for ext, lang in _EXT.items():
            if filename.endswith(ext):
                return lang, 0.95, "extension"

    # 2) Heuristic scoring
    py   = _score(_PY_HINTS,   code)
    java = _score(_JAVA_HINTS, code)
    ts   = _score(_TS_HINTS,   code)

    lang, conf = max(
        (("python", py), ("java", java), ("typescript", ts)),
        key=lambda x: x[1],
    )

    if lang == "typescript" and py >= 0.5 and py >= ts * 0.8:
        lang, conf = "python", py

    if conf >= 0.6:
        return lang, conf, "heuristic"

    return "unknown", 0.0, "none"