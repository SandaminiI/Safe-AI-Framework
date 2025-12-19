import re
from typing import List, Dict

# Lightweight detectors for prompt-injection / jailbreak cues.
SUSPECT_PATTERNS: Dict[str, re.Pattern] = {
    "ignore-rules": re.compile(r"\bignore (all|previous|above) instructions\b", re.I),
    "reveal-system-prompt": re.compile(r"\breveal (the )?(system|hidden) prompt\b", re.I),
    "bypass-guardrails": re.compile(r"\bbypass (safety|guardrails|filters)\b", re.I),
    "do-anything-now": re.compile(r"\bdo anything now\b|\bDAN\b", re.I),
    "base64-blob": re.compile(r"(?:[A-Za-z0-9+/]{24,}={0,2})(?:\s|$)"),
    "zero-width": re.compile(r"\u200b|\u200c|\u200d"),  # zero width chars
    "tool-request": re.compile(r"\b(call|invoke|use)\s+(tool|plugin|api)\b", re.I),
    "emoji-noise": re.compile(r"[\U0001F300-\U0001FAFF]{2,}"),
    "adversarial-suffix": re.compile(r"(~~|::|#|%|\$){5,}"),
}

def detect_prompt_injection(text: str) -> List[str]:
    hits = []
    src = text or ""
    for name, rx in SUSPECT_PATTERNS.items():
        if rx.search(src):
            hits.append(name)
    return hits

def sanitize_prompt(text: str) -> str:
    # Minimal sanitation: strip zero-width, keep the rest
    return SUSPECT_PATTERNS["zero-width"].sub("", text or "")
