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
    """
    type_nodes: Dict[str, Dict[str, Any]] = {}
    fields_by_type: Dict[str, List[Dict[str, Any]]] = {}
    methods_by_type: Dict[str, List[Dict[str, Any]]] = {}

    # collect all TypeDecl nodes
    for nid, n in nodes_by_id.items():
        if n["kind"] == "TypeDecl":
            type_nodes[nid] = n["attrs"]
            fields_by_type.setdefault(nid, [])
            methods_by_type.setdefault(nid, [])

    # Using HAS_FIELD / HAS_METHOD edges, attach fields/methods to classes
    for e in edges:
        src = e["src"]
        dst = e["dst"]
        etype = e["type"]

        if etype == "HAS_FIELD" and src in type_nodes:
            field_node = nodes_by_id[dst]
            fields_by_type[src].append(field_node["attrs"])

        if etype == "HAS_METHOD" and src in type_nodes:
            method_node = nodes_by_id[dst]
            methods_by_type[src].append(method_node["attrs"])

    return type_nodes, fields_by_type, methods_by_type


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

    lines: List[str] = []
    lines.append("@startuml")
    lines.append("set namespaceSeparator .")

    # ---------- Class / interface / enum blocks ----------
    for type_id, t in type_nodes.items():
        name = t.get("name", "UnknownType")

        # For now we treat everything as 'class'. You can extend later using a 'kind' flag.
        header = f"class {name} {{"
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

            if multiplicity and multiplicity not in ("1", ""):
                display_type = f"{display_type} [{multiplicity}]"

            lines.append(f"  {vis_symbol} {field_name} : {display_type}")

        # --- methods ---
        for m in methods_by_type.get(type_id, []):
            vis = m.get("visibility", "package")
            vis_symbol = VISIBILITY_MAP.get(vis, "~")

            method_name = m.get("name", "method")
            is_ctor = m.get("is_constructor", False)

            # annotate constructors
            if is_ctor:
                display_name = f"<<create>> {method_name}"
            else:
                display_name = method_name

            return_type = m.get("return_type", "void")
            raw_ret = m.get("raw_return_type") or return_type
            display_ret = _clean_type_for_display(raw_ret)

            # (simple version – no param list for now)
            lines.append(f"  {vis_symbol} {display_name}() : {display_ret}")

        lines.append("}")  # end class

    # ---------- Relationships (class-level) ----------
    relation_set: Set[tuple[str, str, str]] = set()

    # Build a map: type_id -> display name
    type_name_by_id = {tid: attrs.get("name", tid) for tid, attrs in type_nodes.items()}

    for e in edges:
        src = e["src"]
        dst = e["dst"]
        etype = e["type"]

        if src not in type_nodes or dst not in type_nodes:
            continue  # only class-to-class relationships

        src_name = type_name_by_id[src]
        dst_name = type_name_by_id[dst]

        if etype == "INHERITS":
            relation_set.add((src_name, dst_name, "--|>"))
        elif etype == "IMPLEMENTS":
            relation_set.add((src_name, dst_name, "..|>"))
        elif etype == "ASSOCIATES":
            relation_set.add((src_name, dst_name, "-->"))
        elif etype == "DEPENDS_ON":
            relation_set.add((src_name, dst_name, "..>"))

    for src_name, dst_name, arrow in sorted(relation_set):
        lines.append(f"{src_name} {arrow} {dst_name}")

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
        if n["kind"] == "TypeDecl":
            type_nodes[nid] = n["attrs"]

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
        # Use quotes in case package name has dots
        if pkg == "(default)":
            # optional: don't wrap default package in a block, or do a generic one
            for t in types:
                name = t.get("name", "UnknownType")
                lines.append(f"class {name}")
        else:
            lines.append(f'package "{pkg}" {{')
            for t in types:
                name = t.get("name", "UnknownType")
                lines.append(f"  class {name}")
            lines.append("}")  # end package

    # ---------- Relationships (class-level) ----------
    relation_set: Set[tuple[str, str, str]] = set()
    type_name_by_id = {tid: attrs.get("name", tid) for tid, attrs in type_nodes.items()}

    for e in edges:
        src = e["src"]
        dst = e["dst"]
        etype = e["type"]

        if src not in type_nodes or dst not in type_nodes:
            continue

        src_name = type_name_by_id[src]
        dst_name = type_name_by_id[dst]

        if etype == "INHERITS":
            relation_set.add((src_name, dst_name, "--|>"))
        elif etype == "IMPLEMENTS":
            relation_set.add((src_name, dst_name, "..|>"))
        elif etype == "ASSOCIATES":
            relation_set.add((src_name, dst_name, "-->"))
        elif etype == "DEPENDS_ON":
            relation_set.add((src_name, dst_name, "..>"))

    for src_name, dst_name, arrow in sorted(relation_set):
        lines.append(f"{src_name} {arrow} {dst_name}")

    lines.append("@enduml")
    return "\n".join(lines)


# ======================================================================
#  SEQUENCE DIAGRAM GENERATION (NEW)
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
        lines.append("note \"No associations/dependencies found in CIR to build a sequence view.\" as N1")
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
