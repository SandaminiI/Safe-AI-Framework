# backend/uml-gen-ai/summarize_cir.py
"""
CIR  →  deterministic LLM context string.

Supports the node schema produced by python_adapter.py and JavaAdapter:

  TypeDecl  attrs: name, kind, package, visibility, is_abstract, is_final, modifiers
  Field     attrs: name, type_name, raw_type, visibility, multiplicity, modifiers
  Method    attrs: name, return_type, raw_return_type, visibility,
                   is_constructor, is_static, is_abstract, modifiers
  Parameter attrs: name, type_name, raw_type

Edges used:
  HAS_FIELD     TypeDecl → Field
  HAS_METHOD    TypeDecl → Method
  PARAM_OF      Parameter → Method      (reverse: method is dst)
  INHERITS      TypeDecl → TypeDecl
  IMPLEMENTS    TypeDecl → TypeDecl
  ASSOCIATES    TypeDecl → TypeDecl
  DEPENDS_ON    TypeDecl → TypeDecl
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, DefaultDict, Dict, List, Optional, Set, Tuple

# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _s(x: Any) -> str:
    """Safe stringify, collapse whitespace."""
    if x is None:
        return ""
    return re.sub(r"\s+", " ", str(x)).strip()


def _bool(x: Any) -> bool:
    if isinstance(x, bool):
        return x
    if isinstance(x, str):
        return x.lower() in ("true", "1", "yes")
    return bool(x)


_VIS_SYMBOL: Dict[str, str] = {
    "public":    "+",
    "protected": "#",
    "private":   "-",
    "package":   "~",
    "":          "+",          # default to public
}


def _vis_symbol(vis: str) -> str:
    return _VIS_SYMBOL.get(vis.lower().strip(), "+")


def _is_dunder(name: str) -> bool:
    return name.startswith("__") and name.endswith("__")


def _is_trivial_getter_setter(name: str) -> bool:
    if not name:
        return False
    return (
        (name.startswith("get") and len(name) > 3)
        or (name.startswith("set") and len(name) > 3)
        or (name.startswith("is")  and len(name) > 2)
    )


def _clean_type(raw: str) -> str:
    """Strip leading module path, e.g. 'java.util.List<String>' → 'List<String>'."""
    if not raw:
        return "void"
    # keep generics but trim FQN prefix of the outermost type
    base = raw.split("[")[0].split("<")[0]
    if "." in base:
        short = base.rsplit(".", 1)[1]
        raw = raw[len(base) - len(short):]
    return raw


# ─────────────────────────────────────────────────────────────────────────────
#  Edge map builder
# ─────────────────────────────────────────────────────────────────────────────

def _build_edge_maps(
    edges: List[Dict[str, Any]],
) -> Tuple[DefaultDict[str, List[Tuple[str, str]]], DefaultDict[str, List[Tuple[str, str]]]]:
    outgoing: DefaultDict[str, List[Tuple[str, str]]] = defaultdict(list)
    incoming: DefaultDict[str, List[Tuple[str, str]]] = defaultdict(list)
    for e in edges or []:
        src   = _s(e.get("src"))
        dst   = _s(e.get("dst"))
        etype = _s(e.get("type"))
        if src and dst and etype:
            outgoing[src].append((etype, dst))
            incoming[dst].append((etype, src))
    return outgoing, incoming


# ─────────────────────────────────────────────────────────────────────────────
#  Attribute reader  (handles both top-level and nested-attrs schemas)
# ─────────────────────────────────────────────────────────────────────────────

def _get(node: Dict[str, Any], *keys: str, default: str = "") -> str:
    """
    Try each key first at top-level, then inside node['attrs'].
    Returns the first non-empty match.
    """
    attrs = node.get("attrs") or {}
    for k in keys:
        v = node.get(k) or attrs.get(k)
        if v is not None:
            s = _s(v)
            if s:
                return s
    return default


def _get_bool(node: Dict[str, Any], *keys: str) -> bool:
    attrs = node.get("attrs") or {}
    for k in keys:
        v = node.get(k)
        if v is None:
            v = attrs.get(k)
        if v is not None:
            return _bool(v)
    return False


def _get_mods(node: Dict[str, Any]) -> Tuple[str, ...]:
    attrs = node.get("attrs") or {}
    for k in ("modifiers",):
        v = node.get(k) or attrs.get(k)
        if v:
            if isinstance(v, (list, tuple)):
                return tuple(_s(m) for m in v if _s(m))
            if isinstance(v, str) and v.strip():
                return (v.strip(),)
    return ()


# ─────────────────────────────────────────────────────────────────────────────
#  Main public function
# ─────────────────────────────────────────────────────────────────────────────

def _summarize_package(
    type_info: Dict[str, Any],
    type_names: Dict[str, str],
    edges: List[Dict[str, Any]],
) -> str:
    """
    Context for PACKAGE diagram — matches rule-based output exactly:
    - Full FQN package labels with class/interface keywords inside (no bodies)
    - Type-level arrows placed after all package blocks (not package-level arrows)
    """
    from collections import defaultdict as _dd
    lines = ["PACKAGE DIAGRAM CONTEXT", ""]

    pkg_to_types: Dict[str, list] = _dd(list)
    for type_id, tnode in type_info.items():
        tname = type_names[type_id]
        pkg   = _get(tnode, "package", default="(default)")
        # kind lives in attrs, not at the top-level node (which has kind="TypeDecl")
        attrs = tnode.get("attrs") or tnode
        kind  = (attrs.get("kind") or "class").lower()
        pkg_to_types[pkg].append((tname, kind))

    lines.append("PACKAGES (full FQN label, type keyword + name only, NO bodies, NO brackets):")
    lines.append("")
    for pkg in sorted(pkg_to_types.keys()):
        label = "(default)" if pkg == "(default)" else pkg
        lines.append(f'package "{label}" {{')
        for tname, kind in sorted(pkg_to_types[pkg], key=lambda x: x[0]):
            if kind == "interface":
                lines.append(f"  interface {tname}")
            elif kind in ("abstract class", "abstract"):
                lines.append(f"  abstract class {tname}")
            elif kind == "enum":
                lines.append(f"  enum {tname}")
            else:
                lines.append(f"  class {tname}")
        lines.append("}")
        lines.append("")

    lines.append("RELATIONSHIP ARROWS (ALL go after all package blocks, never inside):")
    lines.append("  --|>  inheritance    ..|>  implementation    -->  association    ..>  dependency")
    lines.append("")

    seen: set = set()
    type_name_map = {tid: type_names[tid] for tid in type_info}
    for e in edges:
        etype = _s(e.get("type"))
        src   = _s(e.get("src"))
        dst   = _s(e.get("dst"))
        if src not in type_info or dst not in type_info:
            continue
        sn, dn = type_name_map[src], type_name_map[dst]
        key = (sn, dn, etype)
        if key in seen:
            continue
        seen.add(key)
        if etype == "INHERITS":
            lines.append(f"{sn} --|> {dn}")
        elif etype == "IMPLEMENTS":
            lines.append(f"{sn} ..|> {dn}")
        elif etype == "ASSOCIATES":
            lines.append(f"{sn} --> {dn}")
        elif etype == "DEPENDS_ON":
            lines.append(f"{sn} ..> {dn}")

    return "\n".join(lines)


def _summarize_component(
    type_info: Dict[str, Any],
    type_names: Dict[str, str],
    edges: List[Dict[str, Any]],
    outgoing: Any,
    nodes_by_id: Dict[str, Any],
) -> str:
    """
    Context for COMPONENT diagram — matches rule-based output exactly:
    - Individual classes become [Component] as alias inside package blocks
    - Depended-on components get () lollipop + assembly connector
    - Arrows target lollipop aliases (I_alias), not component aliases
    - Root package = full FQN; sub-packages = short last segment + <<Stereotype>>
    """
    import re as _re
    from collections import defaultdict as _dd

    _STEREO_MAP = [
        ("controller", "<<Controller>>"), ("resource",   "<<Controller>>"),
        ("endpoint",   "<<Controller>>"), ("rest",       "<<Controller>>"),
        ("handler",    "<<Controller>>"), ("service",    "<<Service>>"),
        ("manager",    "<<Service>>"),    ("facade",     "<<Service>>"),
        ("repository", "<<Repository>>"), ("dao",        "<<Repository>>"),
        ("repo",       "<<Repository>>"), ("database",   "<<Database>>"),
        ("db",         "<<Database>>"),   ("model",      "<<Model>>"),
        ("entity",     "<<Model>>"),      ("domain",     "<<Model>>"),
        ("dto",        "<<DTO>>"),        ("util",       "<<Utility>>"),
        ("helper",     "<<Utility>>"),    ("config",     "<<Config>>"),
        ("security",   "<<Security>>"),   ("filter",     "<<Security>>"),
    ]

    def _stereo(pkg: str, name: str) -> str:
        combined = (pkg + " " + name).lower()
        for kw, s in _STEREO_MAP:
            if kw in combined:
                return s
        return ""

    def _arrow_label(dst_pkg: str, dst_name: str) -> str:
        combined = (dst_pkg + " " + dst_name).lower()
        if "database" in combined or "db" in combined:
            return "queries"
        if "model" in combined or "entity" in combined or "dto" in combined:
            return "maps"
        if "dao" in combined or "repository" in combined or "repo" in combined:
            return "delegates"
        return "uses"

    def _alias(tid: str) -> str:
        return "t_" + _re.sub(r"[^a-zA-Z0-9]", "_", type_names.get(tid, tid))

    def _ialias(tid: str) -> str:
        return "I_t_" + _re.sub(r"[^a-zA-Z0-9]", "_", type_names.get(tid, tid))

    # Compute which types are depended-on (need lollipop)
    called: set = set()
    dep_edges = []
    for e in edges:
        etype = _s(e.get("type"))
        src   = _s(e.get("src"))
        dst   = _s(e.get("dst"))
        if src in type_info and dst in type_info and src != dst:
            if etype in ("ASSOCIATES", "DEPENDS_ON"):
                dep_edges.append((src, dst))
                called.add(dst)

    # Find common root prefix
    all_pkgs = list({
        _get(t, "package", default="(default)")
        for t in type_info.values()
        if _get(t, "package", default="(default)") != "(default)"
    })
    root = ""
    if len(all_pkgs) > 1:
        parts = [p.split(".") for p in all_pkgs]
        common = []
        for segs in zip(*parts):
            if len(set(segs)) == 1:
                common.append(segs[0])
            else:
                break
        root = ".".join(common)

    def _short(pkg: str) -> str:
        if pkg == "(default)":
            return "(root)"
        if root and pkg.startswith(root):
            rel = pkg[len(root):].lstrip(".")
            return rel if rel else "(root)"
        return pkg.rsplit(".", 1)[-1]

    # Group by package
    pkg_to_tids: Dict[str, list] = _dd(list)
    for tid in type_info:
        pkg = _get(type_info[tid], "package", default="(default)")
        pkg_to_tids[pkg].append(tid)

    lines = ["COMPONENT DIAGRAM CONTEXT", ""]
    lines.append(f"ROOT PACKAGE (full FQN): {root or '(default)'}")
    lines.append("")
    lines.append("COMPONENTS — each class becomes [ClassName] as alias:")
    lines.append("  - Components depended-on by others get a lollipop: () 'ClassName' as I_alias + alias - I_alias")
    lines.append("")

    if root:
        lines.append(f'package "{root}" {{')
    for pkg in sorted(pkg_to_tids.keys()):
        short = _short(pkg)
        tids = sorted(pkg_to_tids[pkg], key=lambda t: type_names.get(t, t))
        is_root_level = short in ("(root)", "(default)")
        indent = "  " if root else ""
        stereos = [_stereo(pkg, type_names.get(t, "")) for t in tids if _stereo(pkg, type_names.get(t, ""))]
        pkg_stereo = stereos[0] if stereos else ""
        if not is_root_level:
            stereo_str = f" {pkg_stereo}" if pkg_stereo else ""
            lines.append(f'{indent}package "{short}"{stereo_str} {{')
            inner = indent + "  "
        else:
            inner = indent
        for tid in tids:
            nm = type_names[tid]
            a  = _alias(tid)
            ia = _ialias(tid)
            lines.append(f"{inner}[{nm}] as {a}")
            if tid in called:
                lines.append(f'{inner}() "{nm}" as {ia}')
                lines.append(f"{inner}{a} - {ia}")
        if not is_root_level:
            lines.append(f"{indent}}}")
        lines.append("")
    if root:
        lines.append("}")
        lines.append("")

    lines.append("DEPENDENCY ARROWS (after closing root package }, target lollipop alias I_alias):")
    seen: set = set()
    for src, dst in dep_edges:
        pair = (_alias(src), _ialias(dst) if dst in called else _alias(dst))
        if pair in seen:
            continue
        seen.add(pair)
        dst_pkg  = _get(type_info[dst], "package", default="")
        dst_name = type_names[dst]
        label = _arrow_label(dst_pkg, dst_name)
        lines.append(f"{_alias(src)} --> {_ialias(dst) if dst in called else _alias(dst)} : {label}")

    return "\n".join(lines)


def summarize_cir_for_llm(cir: Dict[str, Any], diagram_type: str) -> str:
    """
    Converts a CIR dict into a rich, deterministic text context for the LLM.

    For CLASS diagrams, each class gets a full member listing with:
      - Visibility symbols  (+  -  #  ~)
      - Field names and their full raw types  (e.g. items: List[Product])
      - Method signatures with typed parameters and return type
        (e.g. checkout(amount: float, currency: str) : bool)
      - {abstract} / {static} modifiers
      - Multiplicity hints on fields (1..*, 0..1, etc.)

    Example output for a single class:

        - CreditCard (kind: class, package: shop)
          FIELDS:
          - +card_number : str
          - +holder_name : str
          - -__expiry : str
          - #_balance : float
          METHODS:
          - +charge(amount: float, currency: str) : bool
          - +refund(transaction_id: str) : bool
          - +get_balance() : float
    """
    nodes: List[Dict[str, Any]] = cir.get("nodes", []) or []
    edges: List[Dict[str, Any]] = cir.get("edges", []) or []

    nodes_by_id: Dict[str, Dict[str, Any]] = {
        _s(n.get("id")): n for n in nodes if _s(n.get("id"))
    }

    outgoing, incoming = _build_edge_maps(edges)

    # ── 1. Index TypeDecl nodes ───────────────────────────────────────────────
    type_info:  Dict[str, Dict[str, Any]] = {}   # type_id → attrs
    type_names: Dict[str, str]            = {}   # type_id → short name

    for n in nodes:
        if n.get("kind") != "TypeDecl":
            continue
        nid = _s(n.get("id"))
        if not nid:
            continue
        type_info[nid]  = n
        type_names[nid] = _get(n, "name") or nid

    dt = diagram_type.lower().strip()
    is_class_diagram     = dt in ("class", "class diagram", "class_diagram")
    is_package_diagram   = dt in ("package", "package diagram")
    is_component_diagram = dt in ("component", "component diagram")

    # ── Package diagram: type-level context matching rule-based standard ───────
    if is_package_diagram:
        return _summarize_package(type_info, type_names, edges)

    # ── Component diagram: individual-class context with alias notation ────────
    if is_component_diagram:
        return _summarize_component(type_info, type_names, edges, outgoing, nodes_by_id)

    # ── 2. For class diagrams: collect fields and methods per type ────────────
    # We resolve ownership strictly via HAS_FIELD / HAS_METHOD edges
    # (the python_adapter always emits these; no guessing needed).

    fields_by_type:  DefaultDict[str, List[str]] = defaultdict(list)
    methods_by_type: DefaultDict[str, List[str]] = defaultdict(list)

    # Build method_id → params lookup from PARAM_OF edges
    # PARAM_OF: param_node --PARAM_OF--> method_node  (param is src, method is dst)
    params_for_method: DefaultDict[str, List[Dict[str, Any]]] = defaultdict(list)
    if is_class_diagram:
        for n in nodes:
            if n.get("kind") != "Parameter":
                continue
            nid = _s(n.get("id"))
            if not nid:
                continue
            # find outgoing PARAM_OF edges from this param node
            for etype, dst in outgoing.get(nid, []):
                if etype == "PARAM_OF":
                    params_for_method[dst].append(n)

    if is_class_diagram:
        for type_id in type_info:
            # ── Fields ──────────────────────────────────────────────────────
            for etype, field_id in outgoing.get(type_id, []):
                if etype != "HAS_FIELD":
                    continue
                fn = nodes_by_id.get(field_id)
                if not fn:
                    continue

                fname      = _get(fn, "name")
                raw_type   = _get(fn, "raw_type", "type_name", default="Any")
                vis        = _get(fn, "visibility", default="public")
                mult       = _get(fn, "multiplicity")
                mods       = _get_mods(fn)
                is_static  = _get_bool(fn, "is_static") or "static" in mods

                if not fname:
                    continue

                sym = _vis_symbol(vis)

                # Build modifier prefix
                mod_parts: List[str] = []
                if is_static:
                    mod_parts.append("{static}")

                mod_prefix = " ".join(mod_parts)
                if mod_prefix:
                    mod_prefix += " "

                display_type = _clean_type(raw_type) or "Any"

                # Append multiplicity hint if non-trivial
                mult_suffix = ""
                if mult and mult not in ("1", ""):
                    mult_suffix = f"  [{mult}]"

                fields_by_type[type_id].append(
                    f"{sym}{mod_prefix}{fname} : {display_type}{mult_suffix}"
                )

            # ── Methods ─────────────────────────────────────────────────────
            for etype, method_id in outgoing.get(type_id, []):
                if etype != "HAS_METHOD":
                    continue
                mn = nodes_by_id.get(method_id)
                if not mn:
                    continue

                mname       = _get(mn, "name")
                return_type = _get(mn, "raw_return_type", "return_type", default="void")
                vis         = _get(mn, "visibility", default="public")
                is_ctor     = _get_bool(mn, "is_constructor")
                is_static   = _get_bool(mn, "is_static")
                is_abstract = _get_bool(mn, "is_abstract")
                mods        = _get_mods(mn)

                if not mname:
                    continue
                # Skip constructors from the method list
                if is_ctor:
                    continue

                # Build method signature
                sym = _vis_symbol(vis)

                mod_parts = []
                if is_abstract or "abstract" in mods:
                    mod_parts.append("{abstract}")
                if is_static or "static" in mods:
                    mod_parts.append("{static}")
                mod_prefix = " ".join(mod_parts)
                if mod_prefix:
                    mod_prefix += " "

                # Collect parameters from PARAM_OF edges
                param_nodes = params_for_method.get(method_id, [])
                param_strs: List[str] = []
                for pn in param_nodes:
                    pname = _get(pn, "name")
                    ptype = _get(pn, "raw_type", "type_name", default="Any")
                    if pname and ptype:
                        param_strs.append(f"{pname}: {_clean_type(ptype)}")
                    elif pname:
                        param_strs.append(pname)

                param_sig = ", ".join(param_strs)
                ret_display = _clean_type(return_type) or "void"

                methods_by_type[type_id].append(
                    f"{sym}{mod_prefix}{mname}({param_sig}) : {ret_display}"
                )

    MAX_FIELDS   = 15
    MAX_METHODS  = 18

    # ── 3. Relationship edges between TypeDecl nodes ──────────────────────────
    rels: List[str] = []
    for e in edges:
        src   = _s(e.get("src"))
        dst   = _s(e.get("dst"))
        etype = _s(e.get("type"))
        if not src or not dst or not etype:
            continue
        if src not in type_names or dst not in type_names:
            continue
        rels.append(f"- {etype}: {type_names[src]} -> {type_names[dst]}")

    # ── 4. Compose the summary ────────────────────────────────────────────────
    lines: List[str] = []
    lines.append("CIR SUMMARY")
    lines.append(f"DIAGRAM_TYPE: {diagram_type}")
    lines.append("")
    lines.append("TYPES:")

    sorted_types = sorted(
        type_info.items(),
        key=lambda kv: (
            _get(kv[1], "package", default=""),
            type_names.get(kv[0], kv[0]),
        ),
    )

    for type_id, tnode in sorted_types:
        tname    = type_names[type_id]
        pkg      = _get(tnode, "package", default="(default)")
        kind     = _get(tnode, "kind", default="class").lower()
        is_abs   = _get_bool(tnode, "is_abstract")
        is_final = _get_bool(tnode, "is_final")

        modifiers: List[str] = []
        if is_abs:
            modifiers.append("abstract")
        if is_final:
            modifiers.append("final")
        mod_str = f" [{', '.join(modifiers)}]" if modifiers else ""

        lines.append(f"- {tname} (kind: {kind}{mod_str}, package: {pkg})")

        if is_class_diagram:
            flds  = fields_by_type.get(type_id,  [])[:MAX_FIELDS]
            mths  = methods_by_type.get(type_id, [])[:MAX_METHODS]

            if flds:
                lines.append("  FIELDS:")
                for f in flds:
                    lines.append(f"    - {f}")

            if mths:
                lines.append("  METHODS:")
                for m in mths:
                    lines.append(f"    - {m}")

    lines.append("")
    lines.append("RELATIONSHIPS (etype: A -> B):")
    for r in rels[:250]:
        lines.append(r)

    return "\n".join(lines)