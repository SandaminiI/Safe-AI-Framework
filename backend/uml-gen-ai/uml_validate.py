# backend/uml-gen-ai/uml_validate.py

import re
from typing import List, Tuple

ALLOWED_START = "@startuml"
ALLOWED_END = "@enduml"

DISALLOWED_DIRECTIVES = [
    r"^\s*!include",
    r"^\s*!includeurl",
    r"^\s*!pragma",
    r"^\s*!unquoted",
]

def validate_plantuml(text: str) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    if not text or not text.strip():
        return False, ["Empty PlantUML text"]

    if ALLOWED_START not in text:
        errors.append("Missing @startuml")
    if ALLOWED_END not in text:
        errors.append("Missing @enduml")

    # block risky directives
    for pat in DISALLOWED_DIRECTIVES:
        if re.search(pat, text, flags=re.IGNORECASE | re.MULTILINE):
            errors.append(f"Disallowed directive found: {pat}")

    # Basic sanity: avoid extremely huge payloads
    if len(text) > 200_000:
        errors.append("PlantUML text too large")

    return (len(errors) == 0), errors
