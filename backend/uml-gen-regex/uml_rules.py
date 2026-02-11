from __future__ import annotations

import re
from typing import Dict, Any, List, Set


# Map CIR visibility to PlantUML symbols
VISIBILITY_MAP = {
    "public": "+",
    "private": "-",
    "protected": "#",
    "package": "~",
}


def _index_cir(cir: Dict[str, Any]):
    """
    Helper: index nodes and edges from CIR debug JSON.
    cir format:
    {
      "nodes": [ { "id": "...", "kind": "TypeDecl", "attrs": {...} }, ... ],
      "edges": [ { "src": "...", "dst": "...", "type": "HAS_FIELD" }, ... ]
      # optionally:
      # "edges": [ { "src": "...", "dst": "...", "type": "...", "attrs": {...} }, ... ]
    }
    """
    nodes_by_id: Dict[str, Dict[str, Any]] = {n["id"]: n for n in cir.get("nodes", [])}
    edges: List[Dict[str, Any]] = cir.get("edges", [])
    return nodes_by_id, edges


def _extract_types_and_members(
    nodes_by_id: Dict[str, Dict[str, Any]],
    edges: List[Dict[str, Any]],
):
    """
    Build convenient indexes:
      - type_nodes: only TypeDecl nodes
      - fields_by_type: type_id -> [field attrs]
      - methods_by_type: type_id -> [method attrs]

    NOTE: We keep the underlying node id in attrs as "_id" so we can
    join method nodes to PARAM_OF edges later (for parameter printing).
    """
    type_nodes: Dict[str, Dict[str, Any]] = {}
    fields_by_type: Dict[str, List[Dict[str, Any]]] = {}
    methods_by_type: Dict[str, List[Dict[str, Any]]] = {}

    # collect all TypeDecl nodes
    for nid, n in nodes_by_id.items():
        if n.get("kind") == "TypeDecl":
            type_nodes[nid] = n.get("attrs", {})
            fields_by_type.setdefault(nid, [])
            methods_by_type.setdefault(nid, [])

    # Using HAS_FIELD / HAS_METHOD edges, attach fields/methods to classes
    for e in edges:
        src = e.get("src")
        dst = e.get("dst")
        etype = e.get("type")

        if not src or not dst:
            continue

        if etype == "HAS_FIELD" and src in type_nodes and dst in nodes_by_id:
            field_node = nodes_by_id[dst]
            fa = dict(field_node.get("attrs", {}))
            fa["_id"] = dst
            fields_by_type[src].append(fa)

        if etype == "HAS_METHOD" and src in type_nodes and dst in nodes_by_id:
            method_node = nodes_by_id[dst]
            ma = dict(method_node.get("attrs", {}))
            ma["_id"] = dst
            methods_by_type[src].append(ma)

    return type_nodes, fields_by_type, methods_by_type


def _index_params_by_method(
    nodes_by_id: Dict[str, Dict[str, Any]],
    edges: List[Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Returns: method_node_id -> list of Parameter attrs (stable order)
    Uses PARAM_OF edges: param -> method
    """
    method_to_params: Dict[str, List[Dict[str, Any]]] = {}

    for e in edges:
        if e.get("type") != "PARAM_OF":
            continue

        param_id = e.get("src")
        method_id = e.get("dst")
        if not param_id or not method_id:
            continue

        pnode = nodes_by_id.get(param_id)
        if not pnode or pnode.get("kind") != "Parameter":
            continue

        method_to_params.setdefault(method_id, []).append(pnode.get("attrs", {}))

    return method_to_params


def _clean_type_for_display(raw_type: str) -> str:
    """
    Regex-style helper:
      - Simplify generics: java.util.List<com.example.Item> -> List<>
      - Shorten fully qualified names: com.example.Person -> Person
    """
    if not raw_type:
        return "void"

    t = raw_type

    # remove generic content (keep base) -> List<Item> -> List<>
    t = re.sub(r"<.*?>", "<>", t)

    # shorten fully qualified names: com.example.Person -> Person
    if "." in t:
        t = t.split(".")[-1]

    return t


def _format_mods(obj: Dict[str, Any]) -> str:
    """
    Render modifiers in PlantUML-friendly form.
    Uses both tuple modifiers and boolean flags (is_static/is_abstract/is_final).
    """
    mods = obj.get("modifiers") or ()
    if isinstance(mods, str):
        mods = (mods,)
    if isinstance(mods, set):
        mods = tuple(mods)

    out: List[str] = []
    if "static" in mods or obj.get("is_static"):
        out.append("{static}")
    if "abstract" in mods or obj.get("is_abstract"):
        out.append("{abstract}")
    return " ".join(out)


# ======================================================================
#  CLASS DIAGRAM GENERATION
# ======================================================================

def generate_class_diagram(cir: Dict[str, Any]) -> str:
    """
    CIR JSON ({nodes, edges}) -> PlantUML class diagram text.
    Rule-based, deterministic, with light regex post-processing.
    """
    nodes_by_id, edges = _index_cir(cir)
    type_nodes, fields_by_type, methods_by_type = _extract_types_and_members(
        nodes_by_id, edges
    )
    params_by_method = _index_params_by_method(nodes_by_id, edges)

    lines: List[str] = []
    lines.append("@startuml")
    lines.append("skinparam classAttributeIconSize 0")
    lines.append("set namespaceSeparator .")

    # ---------- Class / interface / enum blocks ----------
    for type_id, t in type_nodes.items():
        name = t.get("name", "UnknownType")

        # use kind (class/interface/enum)
        kind = (t.get("kind") or "class").lower()
        if kind not in ("class", "interface", "enum"):
            kind = "class"

        # class modifiers
        class_mods = _format_mods(t)
        if class_mods:
            header = f"{kind} {name} {class_mods} {{"
        else:
            header = f"{kind} {name} {{"
        lines.append(header)

        # --- fields ---
        for f in fields_by_type.get(type_id, []):
            vis = f.get("visibility", "package")
            vis_symbol = VISIBILITY_MAP.get(vis, "~")

            field_name = f.get("name", "field")
            type_name = f.get("type_name") or f.get("raw_type") or "Object"
            raw_type = f.get("raw_type") or type_name
            multiplicity = f.get("multiplicity")

            # regex-style cleanup of raw type for display
            display_type = _clean_type_for_display(raw_type)

            # Oshow multiplicity near type for fields
            if multiplicity and multiplicity not in ("1", ""):
                display_type = f"{display_type} [{multiplicity}]"

            # field modifiers
            f_mods = _format_mods(f)
            mods_prefix = f"{f_mods} " if f_mods else ""

            lines.append(f"  {vis_symbol} {mods_prefix}{field_name} : {display_type}")

        # --- methods ---
        for m in methods_by_type.get(type_id, []):
            vis = m.get("visibility", "package")
            vis_symbol = VISIBILITY_MAP.get(vis, "~")

            method_name = m.get("name", "method")
            is_ctor = m.get("is_constructor", False)

            # method modifiers
            m_mods = _format_mods(m)
            mods_prefix = f"{m_mods} " if m_mods else ""

            # params via PARAM_OF edges (param -> method)
            method_node_id = m.get("_id")
            params = params_by_method.get(method_node_id, []) if method_node_id else []

            param_parts: List[str] = []
            for p in params:
                pname = p.get("name", "p")
                ptype = p.get("raw_type") or p.get("type_name") or "Object"
                param_parts.append(f"{pname}: {_clean_type_for_display(ptype)}")
            param_str = ", ".join(param_parts)

            # constructors should NOT show return type
            if is_ctor:
                continue   # lines.append(f"  {vis_symbol} {mods_prefix}<<create>> {method_name}({param_str})")
            else:
                return_type = m.get("return_type", "void")
                raw_ret = m.get("raw_return_type") or return_type
                display_ret = _clean_type_for_display(raw_ret)
                lines.append(f"  {vis_symbol} {mods_prefix}{method_name}({param_str}) : {display_ret}")

        lines.append("}")  # end type block

    # ---------- Relationships (class-level) ----------
    relation_lines: Set[str] = set()

    # Build a map: type_id -> display name
    type_name_by_id = {tid: attrs.get("name", tid) for tid, attrs in type_nodes.items()}

    for e in edges:
        src = e.get("src")
        dst = e.get("dst")
        etype = e.get("type")

        if not src or not dst or not etype:
            continue

        if src not in type_nodes or dst not in type_nodes:
            continue  # only class-to-class relationships

        src_name = type_name_by_id[src]
        dst_name = type_name_by_id[dst]

        if etype == "INHERITS":
            relation_lines.add(f"{src_name} --|> {dst_name}")

        elif etype == "IMPLEMENTS":
            relation_lines.add(f"{src_name} ..|> {dst_name}")

        elif etype == "ASSOCIATES":
            # print multiplicity if edge carries it
            attrs = e.get("attrs") or {}
            mult = attrs.get("multiplicity")

            if mult and mult not in ("1", ""):
                relation_lines.add(f'{src_name} --> "{mult}" {dst_name}')
            else:
                relation_lines.add(f"{src_name} --> {dst_name}")

        elif etype == "DEPENDS_ON":
            relation_lines.add(f"{src_name} ..> {dst_name}")

    for rel in sorted(relation_lines):
        lines.append(rel)

    lines.append("@enduml")
    return "\n".join(lines)


# Backwards-compatible wrapper (old name)
def generate_plantuml_from_cir(cir: Dict[str, Any]) -> str:
    """
    Default: class diagram (for backward compatibility).
    """
    return generate_class_diagram(cir)


# ======================================================================
#  PACKAGE DIAGRAM GENERATION
# ======================================================================

def generate_package_diagram(cir: Dict[str, Any]) -> str:
    """
    CIR JSON ({nodes, edges}) -> PlantUML package-based class diagram.
    Groups classes by package and shows them inside package blocks.
    Relationships remain at class level (arrows between classes).
    """
    nodes_by_id, edges = _index_cir(cir)

    # Collect type nodes
    type_nodes: Dict[str, Dict[str, Any]] = {}
    for nid, n in nodes_by_id.items():
        if n.get("kind") == "TypeDecl":
            type_nodes[nid] = n.get("attrs", {})

    # Group types by package
    package_to_types: Dict[str, List[Dict[str, Any]]] = {}
    for tid, attrs in type_nodes.items():
        pkg = attrs.get("package") or "(default)"
        package_to_types.setdefault(pkg, []).append(attrs)

    lines: List[str] = []
    lines.append("@startuml")
    lines.append("set namespaceSeparator .")

    # ---------- Package blocks ----------
    for pkg, types in package_to_types.items():
        if pkg == "(default)":
            for t in types:
                name = t.get("name", "UnknownType")
                # ✅ use kind here too (optional, but consistent)
                kind = (t.get("kind") or "class").lower()
                if kind not in ("class", "interface", "enum"):
                    kind = "class"
                lines.append(f"{kind} {name}")
        else:
            lines.append(f'package "{pkg}" {{')
            for t in types:
                name = t.get("name", "UnknownType")
                kind = (t.get("kind") or "class").lower()
                if kind not in ("class", "interface", "enum"):
                    kind = "class"
                lines.append(f"  {kind} {name}")
            lines.append("}")  # end package

    # ---------- Relationships (class-level) ----------
    relation_lines: Set[str] = set()
    type_name_by_id = {tid: attrs.get("name", tid) for tid, attrs in type_nodes.items()}

    for e in edges:
        src = e.get("src")
        dst = e.get("dst")
        etype = e.get("type")

        if not src or not dst or not etype:
            continue

        if src not in type_nodes or dst not in type_nodes:
            continue

        src_name = type_name_by_id[src]
        dst_name = type_name_by_id[dst]

        if etype == "INHERITS":
            relation_lines.add(f"{src_name} --|> {dst_name}")
        elif etype == "IMPLEMENTS":
            relation_lines.add(f"{src_name} ..|> {dst_name}")
        elif etype == "ASSOCIATES":
            attrs = e.get("attrs") or {}
            mult = attrs.get("multiplicity")
            if mult and mult not in ("1", ""):
                relation_lines.add(f'{src_name} --> "{mult}" {dst_name}')
            else:
                relation_lines.add(f"{src_name} --> {dst_name}")
        elif etype == "DEPENDS_ON":
            relation_lines.add(f"{src_name} ..> {dst_name}")

    for rel in sorted(relation_lines):
        lines.append(rel)

    lines.append("@enduml")
    return "\n".join(lines)


# ======================================================================
#  SEQUENCE DIAGRAM GENERATION
# ======================================================================

def generate_sequence_diagram(cir: Dict[str, Any]) -> str:
    """
    Very lightweight, static sequence diagram based on type-level
    associations/dependencies in CIR.

    It does NOT analyse real execution order or method bodies.
    It reads edges like:
       TypeA --(ASSOCIATES/DEPENDS_ON)--> TypeB
    and draws them as sequence "TypeA -> TypeB : uses".
    """
    nodes_by_id, edges = _index_cir(cir)

    # Build map: type_id -> name
    type_name_by_id: Dict[str, str] = {}
    for nid, n in nodes_by_id.items():
        if n.get("kind") == "TypeDecl":
            attrs = n.get("attrs", {})
            type_name_by_id[nid] = attrs.get("name", nid)

    participants: Set[str] = set()
    calls: List[tuple[str, str]] = []

    for e in edges:
        etype = e.get("type")
        if etype not in ("ASSOCIATES", "DEPENDS_ON"):
            continue

        src_id = e.get("src")
        dst_id = e.get("dst")
        if src_id not in type_name_by_id or dst_id not in type_name_by_id:
            continue

        src_name = type_name_by_id[src_id]
        dst_name = type_name_by_id[dst_id]
        if src_name == dst_name:
            continue

        participants.add(src_name)
        participants.add(dst_name)
        calls.append((src_name, dst_name))

    lines: List[str] = []
    lines.append("@startuml")
    lines.append("")

    if not participants:
        lines.append('note "No associations/dependencies found in CIR to build a sequence view." as N1')
        lines.append("@enduml")
        return "\n".join(lines)

    # Declare participants
    for name in sorted(participants):
        lines.append(f"participant {name}")

    lines.append("")

    # Draw one arrow per unique pair, in stable order
    seen: Set[tuple[str, str]] = set()
    for src, dst in calls:
        if (src, dst) in seen:
            continue
        seen.add((src, dst))
        lines.append(f"{src} -> {dst} : uses")

    lines.append("@enduml")
    return "\n".join(lines)


# ======================================================================
#  COMPONENT DIAGRAM GENERATION
# ======================================================================

def generate_component_diagram(cir: Dict[str, Any]) -> str:
    """
    CIR JSON -> PlantUML component diagram.

    - Each Java package becomes a UML component
    - If any relationship (ASSOCIATES / DEPENDS_ON / INHERITS / IMPLEMENTS)
      crosses package boundaries, we draw a dependency between components.
    """
    nodes_by_id, edges = _index_cir(cir)

    # 1) Collect type nodes + their packages
    type_nodes: Dict[str, Dict[str, Any]] = {}
    package_by_type: Dict[str, str] = {}

    for nid, n in nodes_by_id.items():
        if n.get("kind") != "TypeDecl":
            continue
        attrs = n.get("attrs", {})
        type_nodes[nid] = attrs
        pkg = attrs.get("package") or "(default)"
        package_by_type[nid] = pkg

    # 2) Build set of packages and give each an alias for PlantUML
    packages: Set[str] = set(package_by_type.values())
    pkg_alias: Dict[str, str] = {}
    for pkg in sorted(packages):
        alias = "comp_" + re.sub(r"[^a-zA-Z0-9_]", "_", pkg)
        pkg_alias[pkg] = alias

    lines: List[str] = []
    lines.append("@startuml")
    lines.append("skinparam componentStyle rectangle")

    # 3) Declare components
    for pkg in sorted(packages):
        alias = pkg_alias[pkg]
        if pkg == "(default)":
            lines.append(f'component "(default package)" as {alias}')
        else:
            lines.append(f'component "{pkg}" as {alias}')

    # 4) Compute inter-package dependencies based on edges between types
    dep_set: Set[tuple[str, str]] = set()

    for e in edges:
        src = e.get("src")
        dst = e.get("dst")
        etype = e.get("type")

        if not src or not dst or not etype:
            continue

        if src not in type_nodes or dst not in type_nodes:
            continue

        src_pkg = package_by_type.get(src, "(default)")
        dst_pkg = package_by_type.get(dst, "(default)")
        if src_pkg == dst_pkg:
            continue

        if etype in ("ASSOCIATES", "DEPENDS_ON", "INHERITS", "IMPLEMENTS"):
            dep_set.add((src_pkg, dst_pkg))

    # 5) Emit component dependency arrows
    for src_pkg, dst_pkg in sorted(dep_set):
        src_alias = pkg_alias[src_pkg]
        dst_alias = pkg_alias[dst_pkg]
        lines.append(f"{src_alias} ..> {dst_alias}")

    lines.append("@enduml")
    return "\n".join(lines)