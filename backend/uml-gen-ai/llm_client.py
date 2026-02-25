# backend/uml-gen-ai/llm_client.py
"""
Gemini LLM client for PlantUML generation.

All four diagram types are standardized to match the rule-based generator exactly:

CLASS     — skinparam classAttributeIconSize 0, set namespaceSeparator .,
            +/-/#/~ visibility, typed fields/methods, no constructors, flat layout
PACKAGE   — packageStyle folder, shadowing false, FontStyle Bold FontSize 12,
            full FQN package labels, class/interface inside, rels outside blocks
SEQUENCE  — sequenceArrowThickness 2, roundcorner 5, responseMessageBelowArrow,
            actor/boundary/control/database participant keywords, activate/deactivate,
            opt (boolean) / loop (list) boxes, ... dots
COMPONENT — componentStyle uml2, defaultTextAlignment center, shadowing false,
            left to right direction, [Component] brackets, () lollipop interfaces,
            <<Stereotype>> package labels, assembly connectors
"""
from __future__ import annotations

import os
from typing import Literal

from dotenv import load_dotenv # type: ignore
import google.generativeai as genai # type: ignore

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL   = (os.getenv("GEMINI_MODEL") or "").strip() or "gemini-2.5-flash"

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY is not set. Put it in .env for UML AI generator.")

genai.configure(api_key=GEMINI_API_KEY)

GEN_CFG = {
    "temperature":       0.2,
    "max_output_tokens": 4096,
    "top_p":  0.9,
    "top_k":  40,
}

# =============================================================================
#  SYSTEM INSTRUCTIONS
# =============================================================================

_BASE_SYSTEM = """
You are an assistant that generates **PlantUML** diagrams from provided context.
Hard rules:
- Output MUST be valid PlantUML between @startuml and @enduml.
- Do NOT explain anything in natural language.
- Do NOT wrap the result in ``` fences.
- No external includes or URLs (!include, !includeurl, !pragma, etc.).
""".strip()

_CLASS_SYSTEM = _BASE_SYSTEM + """

DIAGRAM TYPE: CLASS

MANDATORY HEADER — these two lines must appear immediately after @startuml:
  skinparam classAttributeIconSize 0
  set namespaceSeparator .

VISIBILITY SYMBOLS — mandatory on every single member:
  +  public     -  private     #  protected     ~  package-private

Field format:      <vis><name> : <Type>
  -logger : Logger      -balance : BigDecimal      +items : List<Product>

Method format:     <vis><name>(<param>: <Type>, ...) : <ReturnType>
  +charge(amount: BigDecimal, currency: String) : boolean
  +getAllStudents() : List<Student>
  +{abstract} validate() : boolean
  +{static} getInstance() : Manager

Modifiers {abstract} or {static} go immediately after the visibility symbol.

Class block format:
  class ClassName {
    -fieldName : FieldType
    +methodName(param: Type) : ReturnType
  }
  abstract class Name { ... }
  interface Name { ... }
  enum Name { ... }

Relationships (outside class blocks):
  Child --|> Parent          (inheritance)
  Concrete ..|> Interface   (implementation)
  ClassA --> ClassB         (association)
  ClassA ..> ClassB         (dependency)

CRITICAL DO-NOT:
  1. Do NOT include constructors.
  2. Do NOT use colored icons, stereotypes, or markers on members.
  3. Do NOT wrap classes in package {} or namespace {} blocks.
  4. Do NOT use fully-qualified names (use Foo not com.example.sms.Foo).
  5. Include ALL fields and methods from the context. Do NOT omit or invent any.
""".strip()

_PACKAGE_SYSTEM = _BASE_SYSTEM + """

DIAGRAM TYPE: PACKAGE

MANDATORY HEADER — copy these lines EXACTLY after @startuml, preserving spacing:

  ' Package diagram — shows physical code organisation
  ' Folder-tab icon per package; C/I/E/A circle icons per class member

  skinparam packageStyle         folder
  skinparam classAttributeIconSize 0
  skinparam shadowing            false

  skinparam package {
    FontStyle        Bold
    FontSize         12
  }

PACKAGE BLOCKS — one block per package, full FQN label:
  package "com.example.sms.service" {
    class StudentService
    interface IStudentService
  }
  package "com.example.sms.dao" {
    class StudentDAO
    interface IStudentDAO
  }

TYPE KEYWORDS INSIDE — use ONLY the keyword + short name, NO curly braces, NO members:
  class ClassName
  interface InterfaceName
  abstract class AbstractClassName
  enum EnumName

RELATIONSHIP ARROWS — place ALL arrows AFTER all package blocks (never inside):
  StudentDAO --> DatabaseUtil
  StudentDAO ..|> IStudentDAO
  StudentService --> IStudentDAO
  StudentService ..> Student

Arrow types:
  --|>   inheritance (extends)
  ..|>   implementation (implements)
  -->    association (strong dependency)
  ..>    dependency (weak/uses)

CRITICAL DO-NOT:
  1. Do NOT add curly braces { } after type names inside packages.
  2. Do NOT add member bodies (fields, methods) inside packages.
  3. Do NOT use [BracketName] component syntax — ONLY class/interface/enum keywords.
  4. Do NOT put arrows inside package blocks.
  5. Do NOT use short package names — always use full FQN (com.example.app.service).
  6. Do NOT add colors or stereotypes.
  7. Include EVERY type from the context in its correct package.
""".strip()

_SEQUENCE_SYSTEM = _BASE_SYSTEM + """

DIAGRAM TYPE: SEQUENCE

MANDATORY HEADER — copy exactly after @startuml:

  skinparam sequenceArrowThickness 2
  skinparam roundcorner 5
  skinparam maxmessagesize 250
  skinparam responseMessageBelowArrow true
  skinparam shadowing false

PARTICIPANT SHAPE KEYWORDS:
  actor        — entry point / main app (nobody calls it)
  boundary     — controllers / REST endpoints / handlers
  control      — services / managers / facades / business logic
  database     — DAOs / repositories / DB utilities
  participant  — utilities / helpers / config / anything else

Declaration:   actor "AppName" as AppName
               control "ServiceName" as ServiceName
               database "DAOName" as DAOName

CALL PATTERN — always activate/deactivate the callee:
  Caller -> Callee : methodName(param: Type)
  activate Callee
  Callee --> Caller : ReturnType
  deactivate Callee

Boolean return — wrap in opt:
  opt if successful
    Caller -> Callee : methodName()
    activate Callee
    Callee --> Caller : boolean
    deactivate Callee
  end

List/collection return — wrap in loop:
  loop for each item
    Caller -> Callee : getAllItems()
    activate Callee
    Callee --> Caller : List
    deactivate Callee
  end

Use ... on its own line between call groups for spacing.
Call order: entry-point -> controller -> service -> DAO -> DB.

CRITICAL:
  - Every activate MUST have its matching deactivate. NEVER leave one open.
  - Do NOT include model/entity/DTO types as participants.
""".strip()

_COMPONENT_SYSTEM = _BASE_SYSTEM + """

DIAGRAM TYPE: COMPONENT

MANDATORY HEADER — copy these lines EXACTLY after @startuml, preserving spacing:

  ' Component diagram — shows architectural components and their interfaces
  ' Notched-rectangle icon = component   Circle (lollipop) = provided interface

  skinparam componentStyle      uml2
  skinparam defaultTextAlignment center
  skinparam shadowing           false
  left to right direction

  skinparam package {
    FontStyle        Bold
  }

STRUCTURE — root FQN package wrapping short-name sub-packages:

  package "com.example.sms" {
    [MainApp] as t_Main

    package "controller" <<Controller>> {
      [StudentController] as t_Ctrl
      () "StudentController" as I_t_Ctrl
      t_Ctrl - I_t_Ctrl
    }

    package "service" <<Service>> {
      [StudentService] as t_Svc
      () "StudentService" as I_t_Svc
      t_Svc - I_t_Svc
    }

    package "dao" <<Repository>> {
      [StudentDAO] as t_DAO
      () "StudentDAO" as I_t_DAO
      t_DAO - I_t_DAO
    }

    package "database" <<Database>> {
      [DatabaseUtil] as t_DB
      () "DatabaseUtil" as I_t_DB
      t_DB - I_t_DB
    }

    package "model" <<Model>> {
      [Student] as t_Student
      () "Student" as I_t_Student
      t_Student - I_t_Student
    }
  }

COMPONENT SYNTAX — THREE lines per component that is depended on:
  [ClassName] as alias          ← 1. notched-rectangle component
  () "ClassName" as I_alias     ← 2. lollipop interface  (ONLY if this component is called by another)
  alias - I_alias               ← 3. assembly connector  (MANDATORY with every lollipop, NO exceptions)

WITHOUT line 3 the diagram renders broken (giant circle, no connector).
Every () lollipop line MUST be immediately followed by its alias - I_alias line.

STEREOTYPE labels for sub-packages (pick best match):
  <<Controller>>   controllers / REST endpoints / handlers
  <<Service>>      services / managers / facades
  <<Repository>>   DAOs / repositories / stores
  <<Database>>     database utilities / connection pools
  <<Model>>        entity / model / domain / DTO classes
  <<Utility>>      utility / helper classes
  <<Config>>       configuration classes
  <<Security>>     security / auth classes

DEPENDENCY ARROWS — after the root package block, target the lollipop alias:
  t_Main  --> I_t_Ctrl    : uses
  t_Ctrl  --> I_t_Svc     : uses
  t_Svc   --> I_t_DAO     : delegates
  t_DAO   --> I_t_DB      : queries
  t_Ctrl  --> I_t_Student : maps
  t_Svc   --> I_t_Student : maps

Arrow labels: uses / delegates / queries / maps / implements

CRITICAL DO-NOT:
  1. Root package label = full FQN (com.example.sms).
  2. Sub-package labels = short last segment only (controller, service, dao).
  3. Every component that is targeted by an arrow MUST have a lollipop.
  4. Arrows MUST target I_alias (lollipop), NOT the component alias directly.
  5. Every lollipop MUST have an assembly connector:  alias - I_alias
  6. Do NOT add class body members (fields, methods) inside components.
  7. Do NOT add colors.
  8. Do NOT use ..|> or --|> inside a component diagram — use --> arrows with labels only.
""".strip()


def _system_for(diagram_type: str) -> str:
    dt = (diagram_type or "class").lower().strip()
    return {"package": _PACKAGE_SYSTEM,
            "sequence": _SEQUENCE_SYSTEM,
            "component": _COMPONENT_SYSTEM}.get(dt, _CLASS_SYSTEM)


# =============================================================================
#  REMINDER BLOCKS (injected into user prompt)
# =============================================================================

_CLASS_REMINDER = """
[CLASS DIAGRAM REMINDER]
Output MUST begin:
  @startuml
  skinparam classAttributeIconSize 0
  set namespaceSeparator .

- Every member needs a visibility symbol (+/-/#/~).
- NO constructors. NO package/namespace blocks. SHORT names only.
- Include ALL fields and methods from the FIELDS/METHODS sections.
""".strip()

_PACKAGE_REMINDER = """
[PACKAGE DIAGRAM REMINDER]
Output MUST begin with these lines exactly:

  @startuml

  ' Package diagram — shows physical code organisation
  ' Folder-tab icon per package; C/I/E/A circle icons per class member

  skinparam packageStyle         folder
  skinparam classAttributeIconSize 0
  skinparam shadowing            false

  skinparam package {
    FontStyle        Bold
    FontSize         12
  }

RULES (violations = wrong diagram):
- Full FQN for every package label:  package "com.example.app.service" { ... }
- Inside packages: ONLY keyword + name, no braces, no members:
    class ClassName
    interface InterfaceName
- NOT this:  class ClassName { }   (no body allowed)
- NOT this:  [ClassName]           (no bracket syntax — that is component style)
- ALL arrows go AFTER all package blocks, never inside.
- Arrow types:  --|>  ..|>  -->  ..>
""".strip()

_SEQUENCE_REMINDER = """
[SEQUENCE DIAGRAM REMINDER]
Output MUST begin:
  @startuml
  
  skinparam sequenceArrowThickness 2
  skinparam roundcorner 5
  skinparam maxmessagesize 250
  skinparam responseMessageBelowArrow true
  skinparam shadowing false

- Use actor/boundary/control/database/participant keywords.
- Every -> needs: activate Callee after it, deactivate Callee after the return -->.
- Boolean returns -> opt box. List returns -> loop box.
- ... between groups. NEVER leave an activate without deactivate.
""".strip()

_COMPONENT_REMINDER = """
[COMPONENT DIAGRAM REMINDER]
Output MUST begin with these lines exactly:

  @startuml

  ' Component diagram — shows architectural components and their interfaces
  ' Notched-rectangle icon = component   Circle (lollipop) = provided interface

  skinparam componentStyle      uml2
  skinparam defaultTextAlignment center
  skinparam shadowing           false
  left to right direction

  skinparam package {
    FontStyle        Bold
  }

RULES (violations = wrong diagram):
- Root package = full FQN:  package "com.example.sms" { ... }
- Sub-packages = short name + stereotype:  package "service" <<Service>> { ... }
- Every class → [ClassName] as alias
- Every depended-on component → three consecutive lines:
    () "ClassName" as I_alias
    alias - I_alias            ← MANDATORY — omitting this causes broken rendering
- Arrows target lollipop alias, NOT component alias:  t_Ctrl --> I_t_Svc : uses
- All arrows go AFTER the closing } of the root package.
- NO ..|> or --|> arrows — only --> with a label.
""".strip()

_REMINDERS = {
    "class":     _CLASS_REMINDER,
    "package":   _PACKAGE_REMINDER,
    "sequence":  _SEQUENCE_REMINDER,
    "component": _COMPONENT_REMINDER,
}


def _build_prompt(context: str, diagram_type: str) -> str:
    dt = (diagram_type or "class").lower().strip()
    if dt not in _REMINDERS:
        dt = "class"
    return f"""[TASK]
Generate a {dt} UML diagram in valid PlantUML from the context below.

{_REMINDERS[dt]}

[CONTEXT]
\"\"\"
{context}
\"\"\"

[OUTPUT]
Return ONLY valid PlantUML text (nothing else):

@startuml
...
@enduml""".strip()


# =============================================================================
#  POST-PROCESSORS — enforce mandatory headers deterministically
# =============================================================================

def _inject_after_startuml(plantuml: str, lines_to_inject: list) -> str:
    result = []
    injected = False
    for line in plantuml.splitlines():
        result.append(line)
        if not injected and line.strip().lower().startswith("@startuml"):
            for inject_line in lines_to_inject:
                if inject_line not in plantuml:
                    result.append(inject_line)
            injected = True
    return "\n".join(result)


def _fix_component_assembly_connectors(plantuml: str) -> str:
    """
    Deterministically enforce assembly connectors in component diagrams.

    The rule-based generator always writes:
        [ComponentName] as alias
        () "ComponentName" as I_alias
        alias - I_alias          ← THIS line is what Gemini frequently omits

    Without the 'alias - I_alias' line PlantUML renders the lollipop as a
    giant standalone interface symbol (as seen in Image 2) instead of a small
    circle attached to the component.

    Strategy: scan every () lollipop declaration, find its matching [Name]
    component alias, then inject the assembly connector on the very next line
    if it is absent anywhere in the diagram.
    """
    import re as _re

    # Build name → component-alias map from all [Name] as alias lines
    comp_aliases: dict = {}
    for line in plantuml.splitlines():
        m = _re.search(r'\[([^\]]+)\]\s+as\s+(\w+)', line)
        if m:
            comp_aliases[m.group(1)] = m.group(2)

    result = []
    for line in plantuml.splitlines():
        result.append(line)
        m = _re.search(r'\(\)\s+"([^"]+)"\s+as\s+(\w+)', line)
        if m:
            name   = m.group(1)
            ialias = m.group(2)
            comp_alias = comp_aliases.get(name)
            if comp_alias:
                connector = f"{comp_alias} - {ialias}"
                if connector not in plantuml:
                    # Inject with same indentation as the lollipop line
                    indent = len(line) - len(line.lstrip())
                    result.append(" " * indent + connector)

    return "\n".join(result)


def _post_process(plantuml: str, diagram_type: str) -> str:
    dt = (diagram_type or "class").lower().strip()

    if dt == "class":
        if "classAttributeIconSize" not in plantuml:
            plantuml = _inject_after_startuml(plantuml, ["skinparam classAttributeIconSize 0"])
        if "namespaceSeparator" not in plantuml:
            plantuml = _inject_after_startuml(plantuml, ["set namespaceSeparator ."])

    elif dt == "package":
        needed = []
        if "packageStyle" not in plantuml:
            needed.append("skinparam packageStyle         folder")
        if "classAttributeIconSize" not in plantuml:
            needed.append("skinparam classAttributeIconSize 0")
        if "shadowing" not in plantuml:
            needed.append("skinparam shadowing            false")
        if needed:
            plantuml = _inject_after_startuml(plantuml, needed)

    elif dt == "sequence":
        needed = []
        if "sequenceArrowThickness" not in plantuml:
            needed.append("skinparam sequenceArrowThickness 2")
        if "roundcorner" not in plantuml:
            needed.append("skinparam roundcorner 5")
        if "responseMessageBelowArrow" not in plantuml:
            needed.append("skinparam responseMessageBelowArrow true")
        if "shadowing" not in plantuml:
            needed.append("skinparam shadowing false")
        if needed:
            plantuml = _inject_after_startuml(plantuml, needed)

    elif dt == "component":
        needed = []
        if "componentStyle" not in plantuml:
            needed.append("skinparam componentStyle      uml2")
        if "defaultTextAlignment" not in plantuml:
            needed.append("skinparam defaultTextAlignment center")
        if "shadowing" not in plantuml:
            needed.append("skinparam shadowing           false")
        if "left to right direction" not in plantuml:
            needed.append("left to right direction")
        if needed:
            plantuml = _inject_after_startuml(plantuml, needed)
        # Always enforce assembly connectors — Gemini frequently omits alias - I_alias
        plantuml = _fix_component_assembly_connectors(plantuml)

    return plantuml


# =============================================================================
#  STRIP PACKAGE BLOCKS — for class diagrams only
# =============================================================================

def _strip_package_blocks(plantuml: str) -> str:
    """
    Remove package/namespace wrapper blocks (brace-counting, handles nesting).
    Keeps class/interface/abstract/enum definitions intact.
    Only called for CLASS diagrams — package diagrams need the blocks.
    """
    import re as _re

    def _remove_wrappers(text: str) -> str:
        result = []
        i = 0
        n = len(text)
        while i < n:
            m = _re.match(
                r'^([ \t]*)(package|namespace)([ \t]+(?:"[^"]*"|[^\s{]+))?[ \t]*\{',
                text[i:],
                _re.IGNORECASE,
            )
            if m:
                start = i + m.end()
                depth = 1
                j = start
                while j < n and depth > 0:
                    if text[j] == "{":
                        depth += 1
                    elif text[j] == "}":
                        depth -= 1
                    j += 1
                inner = text[start: j - 1]
                inner_stripped = _remove_wrappers(inner)
                dedented = _re.sub(r"^  ", "", inner_stripped, flags=_re.MULTILINE)
                result.append(dedented)
                i = j
                if i < n and text[i] == "\n":
                    i += 1
            else:
                end = text.find("\n", i)
                if end == -1:
                    result.append(text[i:])
                    break
                result.append(text[i: end + 1])
                i = end + 1
        return "".join(result)

    return _remove_wrappers(plantuml)


# =============================================================================
#  PlantUML EXTRACTOR
# =============================================================================

def _extract_plantuml(text: str) -> str:
    import re as _re

    if not text:
        raise RuntimeError("Empty response from Gemini.")

    lower     = text.lower()
    start_idx = lower.find("@startuml")
    end_idx   = lower.rfind("@enduml")

    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        return text[start_idx: end_idx + len("@enduml")].strip()

    fence_match = _re.search(
        r"```(?:plantuml|uml|puml)?\s*\n(.*?)\n```",
        text,
        flags=_re.DOTALL | _re.IGNORECASE,
    )
    if fence_match:
        inner = fence_match.group(1).strip()
        if inner:
            return f"@startuml\n{inner}\n@enduml"

    return text.strip()


# =============================================================================
#  PUBLIC ENTRY POINT
# =============================================================================

def generate_plantuml_from_context(
    context: str,
    diagram_type: Literal["class", "package", "sequence", "component"] = "class",
) -> str:
    if not context or not context.strip():
        raise RuntimeError("No context provided for AI UML generation.")

    dt     = (diagram_type or "class").lower().strip()
    prompt = _build_prompt(context, dt)

    model = genai.GenerativeModel(
        GEMINI_MODEL,
        generation_config=GEN_CFG,
        system_instruction=_system_for(dt),
    )

    try:
        resp = model.generate_content(prompt)
    except Exception as e:
        raise RuntimeError(f"Gemini call failed: {type(e).__name__}: {e}") from e

    parts_text = ""
    if hasattr(resp, "candidates") and resp.candidates:
        for cand in resp.candidates:
            content = getattr(cand, "content", None)
            if content and getattr(content, "parts", None):
                for p in content.parts:
                    parts_text += (getattr(p, "text", "") or "")
    else:
        parts_text = getattr(resp, "text", "") or ""

    plantuml = _extract_plantuml(parts_text)

    if "@startuml" not in plantuml.lower() or "@enduml" not in plantuml.lower():
        if parts_text.strip():
            plantuml = f"@startuml\n{parts_text.strip()}\n@enduml"
        else:
            raise RuntimeError(
                "Gemini returned an empty or unrecognisable response "
                "(no @startuml/@enduml block found)."
            )

    # Class diagrams: strip any package/namespace wrappers Gemini emits
    if dt == "class":
        plantuml = _strip_package_blocks(plantuml)

    # All diagrams: enforce mandatory skinparam headers
    plantuml = _post_process(plantuml, dt)

    return plantuml