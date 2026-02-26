from __future__ import annotations

import re
from typing import Dict, Any, List, Set, Optional, Tuple

# Map CIR visibility to PlantUML symbols
VISIBILITY_MAP = {
    "public": "+",
    "private": "-",
    "protected": "#",
    "package": "~",
}

# ──────────────────────────────────────────────────────────────────────────────
#  Architecture layer ordering
#  Lower number = higher in the call stack (client-side / entry point)
# ──────────────────────────────────────────────────────────────────────────────
_LAYER_ORDER: Dict[str, int] = {
    "client":      5,
    "controller":  10,
    "resource":    10,
    "endpoint":    10,
    "rest":        10,
    "handler":     12,
    "api":         15,
    "service":     20,
    "manager":     22,
    "facade":      22,
    "business":    22,
    "interactor":  22,
    "usecase":     22,
    "repository":  30,
    "repo":        30,
    "dao":         30,
    "persistence": 32,
    "store":       32,
    "data":        35,
    "gateway":     38,
    "database":    40,
    "db":          40,
    "entity":      45,
    "model":       50,
    "domain":      50,
    "util":        60,
    "helper":      60,
    "config":      70,
    "security":    75,
    "filter":      74,
    "middleware":  73,
}


def _layer_order(type_name: str, package: str) -> int:
    """Return architectural layer order for a type. Lower = earlier caller."""
    combined = (type_name + " " + (package or "")).lower()
    best = 55  # default: middle
    for keyword, order in _LAYER_ORDER.items():
        if keyword in combined:
            if order < best:
                best = order
    return best


# ──────────────────────────────────────────────────────────────────────────────
#  Low-level CIR helpers
# ──────────────────────────────────────────────────────────────────────────────

def _index_cir(cir: Dict[str, Any]):
    nodes_by_id: Dict[str, Dict[str, Any]] = {
        n["id"]: n for n in cir.get("nodes", [])
    }
    edges: List[Dict[str, Any]] = cir.get("edges", [])
    return nodes_by_id, edges


def _extract_types_and_members(
    nodes_by_id: Dict[str, Dict[str, Any]],
    edges: List[Dict[str, Any]],
):
    type_nodes: Dict[str, Dict[str, Any]] = {}
    fields_by_type: Dict[str, List[Dict[str, Any]]] = {}
    methods_by_type: Dict[str, List[Dict[str, Any]]] = {}

    for nid, n in nodes_by_id.items():
        if n.get("kind") == "TypeDecl":
            type_nodes[nid] = n.get("attrs", {})
            fields_by_type.setdefault(nid, [])
            methods_by_type.setdefault(nid, [])

    for e in edges:
        src, dst, etype = e.get("src"), e.get("dst"), e.get("type")
        if not src or not dst:
            continue
        if etype == "HAS_FIELD" and src in type_nodes and dst in nodes_by_id:
            fa = dict(nodes_by_id[dst].get("attrs", {}))
            fa["_id"] = dst
            fields_by_type[src].append(fa)
        if etype == "HAS_METHOD" and src in type_nodes and dst in nodes_by_id:
            ma = dict(nodes_by_id[dst].get("attrs", {}))
            ma["_id"] = dst
            methods_by_type[src].append(ma)

    return type_nodes, fields_by_type, methods_by_type


def _index_params_by_method(
    nodes_by_id: Dict[str, Dict[str, Any]],
    edges: List[Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    method_to_params: Dict[str, List[Dict[str, Any]]] = {}
    for e in edges:
        if e.get("type") != "PARAM_OF":
            continue
        param_id, method_id = e.get("src"), e.get("dst")
        if not param_id or not method_id:
            continue
        pnode = nodes_by_id.get(param_id)
        if pnode and pnode.get("kind") == "Parameter":
            method_to_params.setdefault(method_id, []).append(
                pnode.get("attrs", {})
            )
    return method_to_params


def _clean_type_for_display(raw_type: str) -> str:
    if not raw_type:
        return "void"
    t = re.sub(r"<.*?>", "<>", raw_type)
    if "." in t:
        t = t.split(".")[-1]
    return t


def _clean_type_short(raw_type: str) -> str:
    """Strip generics entirely, just keep base name."""
    if not raw_type:
        return ""
    t = re.sub(r"<.*?>", "", raw_type)
    if "." in t:
        t = t.rsplit(".", 1)[1]
    return t.strip()


def _format_mods(obj: Dict[str, Any]) -> str:
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


def _is_dunder(name: str) -> bool:
    return bool(name) and name.startswith("__") and name.endswith("__")


def _safe_sequence_label(method_name: str) -> str:
    if method_name == "__init__":
        return "<<create>>"
    if _is_dunder(method_name):
        safe = method_name.replace("__", "~__", 1)
        safe = safe[::-1].replace("__", "~__", 1)[::-1]
        return f"{safe}()"
    return f"{method_name}()"


# ──────────────────────────────────────────────────────────────────────────────
#  Infrastructure-noise filter
#
#  The following class categories are excluded from Sequence and Component
#  diagrams because they represent cross-cutting infrastructure rather than
#  meaningful architectural participants or deployable components:
#
#    Exceptions / Errors  — control-flow throwables, not participants.
#    Loggers              — cross-cutting logging utilities.
#    Utils / Helpers      — stateless utility classes with no interaction role.
#    Config classes       — Spring/framework @Configuration holders.
#    Filters              — servlet/security filters (e.g. JwtAuthFilter).
#    Framework classes    — framework bootstrap / adapter classes.
#    Application / Main   — app entry-point bootstrappers.
#
#  Detection uses three complementary strategies so that both explicit suffixes
#  (e.g. "JwtTokenFilter") and package-based placements (e.g. com.app.filter)
#  are caught:
#    1. Name-SUFFIX match  — exact word at end of class name (case-insensitive)
#    2. Name-CONTAINS match — substring anywhere in class name
#    3. Package-SEGMENT match — keyword appears as a dot-delimited segment
#                               in the fully-qualified package name
#
#  This filter is applied in generate_sequence_diagram (lifeline exclusion)
#  and generate_component_diagram (component node exclusion).
# ──────────────────────────────────────────────────────────────────────────────

# Words that, when found at the END of a class name, mark it as noise.
_NOISE_NAME_SUFFIXES: Tuple[str, ...] = (
    "exception", "error",            # Throwables
    "logger",                        # Logging classes
    "util", "utils",                 # Utility classes
    "helper", "helpers",             # Helper classes
    "config", "configuration",       # Configuration holders
    "filter",                        # Servlet / security filters
    "framework",                     # Framework adapter/bootstrap classes
    "application", "main",           # App entry points
)

# Words that, when found ANYWHERE in a class name, mark it as noise.
# Kept narrower than suffixes to avoid false positives (e.g. "Configurable").
_NOISE_NAME_CONTAINS: Tuple[str, ...] = (
    "logger",      # e.g. AppLogger, LoggerFactory
    "logutil",     # e.g. LogUtil
    "filterchain", # e.g. FilterChainProxy
)

# Package path SEGMENTS that mark every class in that package as noise.
# Matched as dot-delimited segments so "config" does not accidentally match
# "reconfigurable" or similar names.
_NOISE_PKG_SEGMENTS: Tuple[str, ...] = (
    "exception", "exceptions",
    "error",     "errors",
    "util",      "utils",
    "helper",    "helpers",
    "log",       "logger",   "logging",
    "config",    "configuration",
    "filter",    "filters",
    "framework",
)


def _is_infrastructure_noise(name: str, package: str) -> bool:
    """
    Return True if this type should be excluded from Sequence and Component
    diagrams because it represents cross-cutting infrastructure rather than
    a meaningful architectural participant or deployable component.
    """
    nm   = (name    or "").lower()
    pkg  = (package or "").lower()
    segs = set(pkg.replace("-", ".").split("."))   # dot-delimited segments

    # 1. Name-suffix check  (e.g. JwtTokenFilter, SecurityConfig, LoggerUtil)
    if any(nm.endswith(sfx) for sfx in _NOISE_NAME_SUFFIXES):
        return True

    # 2. Name-contains check  (e.g. AppLogger, FilterChainProxy)
    if any(kw in nm for kw in _NOISE_NAME_CONTAINS):
        return True

    # 3. Package-segment check  (e.g. com.app.filter, com.app.config.security)
    if segs & set(_NOISE_PKG_SEGMENTS):
        return True

    return False


# ══════════════════════════════════════════════════════════════════════════════
#  CLASS DIAGRAM
#
#  Shows: classifiers (class/interface/enum), attribute compartment,
#         operation compartment, visibility, modifiers, and relationships
#         (INHERITS, IMPLEMENTS, ASSOCIATES, DEPENDS_ON).
#  Does NOT show: package grouping, runtime call sequences, components.
# ══════════════════════════════════════════════════════════════════════════════

def generate_class_diagram(cir: Dict[str, Any]) -> str:
    nodes_by_id, edges = _index_cir(cir)
    type_nodes, fields_by_type, methods_by_type = _extract_types_and_members(
        nodes_by_id, edges
    )
    params_by_method = _index_params_by_method(nodes_by_id, edges)

    lines: List[str] = ["@startuml",
                        "skinparam classAttributeIconSize 0",
                        "set namespaceSeparator ."]

    for type_id, t in type_nodes.items():
        name = t.get("name", "UnknownType")
        kind = (t.get("kind") or "class").lower()
        if kind not in ("class", "interface", "enum"):
            kind = "class"

        class_mods = _format_mods(t)
        header = f"{kind} {name} {class_mods} {{" if class_mods else f"{kind} {name} {{"
        lines.append(header)

        # Attribute compartment
        for f in fields_by_type.get(type_id, []):
            vis_symbol = VISIBILITY_MAP.get(f.get("visibility", "package"), "~")
            field_name = f.get("name", "field")
            raw_type = f.get("raw_type") or f.get("type_name") or "Object"
            display_type = _clean_type_for_display(raw_type)
            multiplicity = f.get("multiplicity")
            if multiplicity and multiplicity not in ("1", ""):
                display_type = f"{display_type} [{multiplicity}]"
            f_mods = _format_mods(f)
            mods_prefix = f"{f_mods} " if f_mods else ""
            lines.append(f"  {vis_symbol} {mods_prefix}{field_name} : {display_type}")

        # Operation compartment — constructors are intentionally excluded
        # (they add noise without adding structural information to a class overview)
        for m in methods_by_type.get(type_id, []):
            if m.get("is_constructor"):
                continue
            vis_symbol = VISIBILITY_MAP.get(m.get("visibility", "package"), "~")
            method_name = m.get("name", "method")
            m_mods = _format_mods(m)
            mods_prefix = f"{m_mods} " if m_mods else ""
            method_node_id = m.get("_id")
            params = params_by_method.get(method_node_id, []) if method_node_id else []
            param_parts = [
                f"{p.get('name','p')}: {_clean_type_for_display(p.get('raw_type') or p.get('type_name') or 'Object')}"
                for p in params
            ]
            param_str = ", ".join(param_parts)
            raw_ret = m.get("raw_return_type") or m.get("return_type", "void")
            display_ret = _clean_type_for_display(raw_ret)
            lines.append(f"  {vis_symbol} {mods_prefix}{method_name}({param_str}) : {display_ret}")

        lines.append("}")

    # Classifier relationships
    relation_lines: Set[str] = set()
    type_name_by_id = {tid: attrs.get("name", tid) for tid, attrs in type_nodes.items()}

    for e in edges:
        src, dst, etype = e.get("src"), e.get("dst"), e.get("type")
        if not src or not dst or not etype:
            continue
        if src not in type_nodes or dst not in type_nodes:
            continue
        sn, dn = type_name_by_id[src], type_name_by_id[dst]
        if etype == "INHERITS":
            relation_lines.add(f"{sn} --|> {dn}")
        elif etype == "IMPLEMENTS":
            relation_lines.add(f"{sn} ..|> {dn}")
        elif etype == "ASSOCIATES":
            mult = (e.get("attrs") or {}).get("multiplicity")
            if mult and mult not in ("1", ""):
                relation_lines.add(f'{sn} --> "{mult}" {dn}')
            else:
                relation_lines.add(f"{sn} --> {dn}")
        elif etype == "DEPENDS_ON":
            relation_lines.add(f"{sn} ..> {dn}")

    for rel in sorted(relation_lines):
        lines.append(rel)

    lines.append("@enduml")
    return "\n".join(lines)


def generate_plantuml_from_cir(cir: Dict[str, Any]) -> str:
    return generate_class_diagram(cir)


# ══════════════════════════════════════════════════════════════════════════════
#  PACKAGE DIAGRAM
#
#  Shows: packages as folder-tab rectangles, classifier NAMES (only) inside
#         each package, and inter-PACKAGE dependency arrows aggregated from
#         cross-package type relationships.
#
#  Does NOT show:
#    - Classifier kind keywords (class/interface/enum) — those belong in the
#      Class Diagram. The Package Diagram is about physical namespace layout,
#      not type classification.
#    - Individual type-to-type relationship arrows — arrows here represent
#      package-level dependencies, not per-type relationships. If two types
#      in the same package relate, no arrow is drawn (they are co-located).
#    - Attributes or operations — these belong exclusively in the Class Diagram.
# ══════════════════════════════════════════════════════════════════════════════

def generate_package_diagram(cir: Dict[str, Any]) -> str:
    nodes_by_id, edges = _index_cir(cir)

    # Collect TypeDecl nodes
    type_nodes: Dict[str, Dict[str, Any]] = {}
    for nid, n in nodes_by_id.items():
        if n.get("kind") == "TypeDecl":
            type_nodes[nid] = n.get("attrs", {})

    # Group classifiers by package
    package_to_types: Dict[str, List[Tuple[str, Dict[str, Any]]]] = {}
    for tid, attrs in type_nodes.items():
        pkg = attrs.get("package") or "(default)"
        package_to_types.setdefault(pkg, []).append((tid, attrs))

    # Map type id → package for dependency aggregation
    type_to_package: Dict[str, str] = {
        tid: (attrs.get("package") or "(default)")
        for tid, attrs in type_nodes.items()
    }

    # Build PlantUML
    out: List[str] = [
        "@startuml",
        "",
        "' Package diagram — shows physical namespace organisation",
        "' Classifier names only inside packages (no kind keywords, no members)",
        "' Arrows represent inter-package dependencies aggregated from type relationships",
        "",
        "skinparam packageStyle         folder",
        "skinparam classAttributeIconSize 0",
        "skinparam shadowing            false",
        "",
        "skinparam package {",
        "  FontStyle        Bold",
        "  FontSize         12",
        "}",
        "",
    ]

    # Sort packages: default first, then alphabetically
    sorted_pkgs = sorted(
        package_to_types.keys(),
        key=lambda p: (0 if p == "(default)" else 1, p)
    )

    type_name_by_id: Dict[str, str] = {}

    for pkg in sorted_pkgs:
        members = sorted(package_to_types[pkg], key=lambda x: x[1].get("name", ""))
        label = "(default)" if pkg == "(default)" else pkg

        out.append(f'package "{label}" {{')
        for tid, attrs in members:
            name = attrs.get("name", "UnknownType")
            type_name_by_id[tid] = name
            # FIX: write classifier name only — no "class"/"interface"/"enum" keyword.
            # Classifier kind is irrelevant to package organisation.
            out.append(f'  [{name}]')
        out.append("}")
        out.append("")

    # FIX: Aggregate type-level relationships into inter-PACKAGE dependency arrows.
    # Only draw an arrow when the source and destination are in DIFFERENT packages.
    # Multiple type relationships between the same two packages collapse to one arrow.
    # INHERITS and IMPLEMENTS are classifier relationships — they are not meaningful
    # as package-level dependencies and are therefore excluded here.
    package_deps: Set[Tuple[str, str]] = set()

    for e in edges:
        src, dst, etype = e.get("src"), e.get("dst"), e.get("type")
        if not src or not dst or not etype:
            continue
        if src not in type_nodes or dst not in type_nodes:
            continue
        if etype not in ("ASSOCIATES", "DEPENDS_ON"):
            continue
        src_pkg = type_to_package.get(src)
        dst_pkg = type_to_package.get(dst)
        if src_pkg and dst_pkg and src_pkg != dst_pkg:
            package_deps.add((src_pkg, dst_pkg))

    if package_deps:
        out.append("' Inter-package dependencies")
        for src_pkg, dst_pkg in sorted(package_deps):
            src_label = "(default)" if src_pkg == "(default)" else src_pkg
            dst_label = "(default)" if dst_pkg == "(default)" else dst_pkg
            out.append(f'"{src_label}" ..> "{dst_label}"')

    out.append("")
    out.append("@enduml")
    return "\n".join(out)


# ══════════════════════════════════════════════════════════════════════════════
#  SEQUENCE DIAGRAM
#
#  Shows: lifelines (participants with UML stereotype shapes), synchronous
#         call messages (->), return messages (-->), combined fragments
#         (opt for boolean returns, loop for collection returns).
#
#  Message source priority:
#    1. PRIMARY — CALLS edges: represent actual runtime method invocations.
#       When CALLS data is present, all messages are derived from it exclusively.
#    2. FALLBACK — ASSOCIATES/DEPENDS_ON edges + useful_methods() heuristic:
#       used only when no CALLS edges exist in the CIR. In this mode a note
#       is emitted on the diagram to indicate that messages are inferred from
#       structural associations, not from observed call chains.
#
#  Does NOT show: class attributes, fields, inheritance, package grouping,
#                 or component interfaces.
# ══════════════════════════════════════════════════════════════════════════════

def generate_sequence_diagram(cir: Dict[str, Any]) -> str:
    nodes_by_id, edges = _index_cir(cir)

    # 1. Index type nodes
    type_attrs: Dict[str, Dict[str, Any]] = {}
    for nid, n in nodes_by_id.items():
        if n.get("kind") == "TypeDecl":
            type_attrs[nid] = n.get("attrs", {})

    if not type_attrs:
        return '@startuml\nnote "No types found in CIR." as N1\n@enduml'

    # 2. Methods per type
    methods_by_type: Dict[str, List[Dict[str, Any]]] = {t: [] for t in type_attrs}
    method_owner: Dict[str, str] = {}
    for e in edges:
        if e.get("type") == "HAS_METHOD":
            src, dst = e.get("src"), e.get("dst")
            if src in type_attrs and dst in nodes_by_id:
                ma = dict(nodes_by_id[dst].get("attrs", {}))
                ma["_id"] = dst
                methods_by_type[src].append(ma)
                method_owner[dst] = src

    # 3. Parameters per method
    params_by_method: Dict[str, List[Dict[str, Any]]] = {}
    for e in edges:
        if e.get("type") == "PARAM_OF":
            pid, mid = e.get("src"), e.get("dst")
            if pid and mid:
                pnode = nodes_by_id.get(pid)
                if pnode and pnode.get("kind") == "Parameter":
                    params_by_method.setdefault(mid, []).append(pnode.get("attrs", {}))

    # 4. Index method names and CALLS edges
    method_name_by_id: Dict[str, str] = {}
    for nid, n in nodes_by_id.items():
        if n.get("kind") == "Method":
            method_name_by_id[nid] = n.get("attrs", {}).get("name", "")

    # Build calls_by_src from CALLS edges — this is the PRIMARY message source
    calls_by_src: Dict[str, List[Dict[str, Any]]] = {}
    for e in edges:
        if e.get("type") != "CALLS":
            continue
        src_m, dst_m = e.get("src"), e.get("dst")
        if not src_m or not dst_m:
            continue
        if _is_dunder(method_name_by_id.get(dst_m, "")):
            continue
        order = (e.get("attrs") or {}).get("order", 0)
        calls_by_src.setdefault(src_m, []).append({"dst": dst_m, "order": order})

    # 5. Association graph (used ONLY as fallback when no CALLS data exists)
    associates: Dict[str, List[str]] = {t: [] for t in type_attrs}
    for e in edges:
        if e.get("type") not in ("ASSOCIATES", "DEPENDS_ON"):
            continue
        src, dst = e.get("src"), e.get("dst")
        if src in type_attrs and dst in type_attrs and src != dst:
            if dst not in associates[src]:
                associates[src].append(dst)

    # 6. Model/POJO detection — exclude pure data-holders from sequence lifelines
    _MODEL_PKG_KW  = {"model", "entity", "domain", "dto", "vo", "bean", "pojo"}
    _TRIVIAL_PFXS  = ("get", "set", "is", "has")
    _TRIVIAL_NAMES = {"tostring", "hashcode", "equals", "clone", "compareto"}

    def _is_model(tid: str) -> bool:
        a   = type_attrs[tid]
        pkg = (a.get("package") or "").lower()
        nm  = (a.get("name")    or "").lower()
        if any(kw in pkg or kw in nm for kw in _MODEL_PKG_KW):
            return True
        ms = [m for m in methods_by_type.get(tid, [])
              if not m.get("is_constructor") and not _is_dunder(m.get("name", ""))]
        if not ms:
            return False
        non_trivial = [m for m in ms
                       if not any(m.get("name", "").startswith(p) for p in _TRIVIAL_PFXS)
                       and m.get("name", "").lower() not in _TRIVIAL_NAMES]
        return len(non_trivial) == 0

    model_types: Set[str] = {t for t in type_attrs if _is_model(t)}

    # Also exclude infrastructure-noise types (exceptions, loggers, config,
    # app entry points) — they are not meaningful sequence diagram participants.
    noise_types: Set[str] = {
        t for t in type_attrs
        if _is_infrastructure_noise(
            type_attrs[t].get("name", ""),
            type_attrs[t].get("package", ""),
        )
    }
    excluded_types: Set[str] = model_types | noise_types

    # 7. Participant ordering by architectural layer
    def layer(tid: str) -> int:
        a = type_attrs[tid]
        return _layer_order(a.get("name", ""), a.get("package", ""))

    incoming: Dict[str, int] = {t: 0 for t in type_attrs}
    for deps in associates.values():
        for d in deps:
            incoming[d] = incoming.get(d, 0) + 1

    def build_chain(start: str, visited: Set[str]) -> List[str]:
        chain = [start]
        visited = visited | {start}
        hops = sorted(
            [d for d in associates.get(start, []) if d not in visited and d not in excluded_types],
            key=layer,
        )
        for hop in hops:
            chain.extend(build_chain(hop, visited | {hop}))
        return chain

    non_model    = [t for t in type_attrs if t not in excluded_types]
    sorted_types = sorted(non_model, key=lambda t: (incoming.get(t, 0), layer(t), type_attrs[t].get("name", "")))

    covered: Set[str] = set()
    chains:  List[List[str]] = []
    for candidate in sorted_types:
        if candidate in covered:
            continue
        chain = build_chain(candidate, set())
        if chain:
            chains.append(chain)
            covered.update(chain)

    seen: Set[str] = set()
    ordered: List[str] = []
    for chain in sorted(chains, key=lambda c: layer(c[0]) if c else 99):
        for tid in chain:
            if tid not in seen:
                seen.add(tid)
                ordered.append(tid)
    for tid in sorted(non_model, key=layer):
        if tid not in seen:
            ordered.append(tid)

    # 8. Participant shape keyword derived from architectural layer.
    #
    #  UML rule: "actor" (stick figure) represents an EXTERNAL entity that
    #  initiates or participates in a use case from OUTSIDE the system boundary
    #  — e.g. a human user, an external system, or a device.
    #  Controllers, services, and repositories are INTERNAL system components;
    #  they must never be rendered as actors regardless of their position in the
    #  call chain. The correct shapes for internal components are:
    #    boundary   → circle-on-line  — system boundary (controllers, REST handlers)
    #    control    → circle-arrow    — logic coordinators (services, managers)
    #    database   → cylinder        — data stores (DAOs, repositories)
    #    participant → rectangle      — all other internal components
    #
    #  A synthetic "Client" actor IS added automatically at the leftmost position
    #  to represent the external caller that triggers the entry-point controllers.
    #  This is required by UML: every sequence must have an initiating entity.
    def _participant_keyword(tid: str) -> str:
        a   = type_attrs[tid]
        nm  = (a.get("name")    or "").lower()
        pkg = (a.get("package") or "").lower()
        combined = nm + " " + pkg
        # Controllers and REST boundary components
        if any(k in combined for k in ("controller", "resource", "endpoint", "rest", "handler", "boundary", "api")):
            return "boundary"
        # Services, managers, business logic components
        if any(k in combined for k in ("service", "manager", "interactor", "usecase", "business", "facade")):
            return "control"
        # Data access and persistence components
        if any(k in combined for k in ("dao", "repository", "repo", "database", "db", "persistence", "store", "gateway")):
            return "database"
        # All other internal components (utils, config, security filters, etc.)
        return "participant"

    # Identify entry-point controllers: boundary-shaped participants that have
    # no incoming calls from any other system participant (i.e. the first
    # component to receive a request from outside the system boundary).
    # These are the targets for the initial "Client" actor arrow.
    entry_controllers: List[str] = []
    for tid in ordered:
        if _participant_keyword(tid) == "boundary":
            # Check if any other non-excluded participant calls into this one
            is_called_internally = any(
                method_owner.get(e.get("dst")) == tid
                for e in edges
                if e.get("type") == "CALLS"
                and method_owner.get(e.get("src")) != tid
                and method_owner.get(e.get("src")) in seen
                and method_owner.get(e.get("src")) not in excluded_types
            )
            if not is_called_internally:
                entry_controllers.append(tid)

    # 9. Method helpers
    _SKIP_PFXS = ("get", "set", "is", "has")

    def useful_methods(type_id: str, max_count: int = 4) -> List[Dict[str, Any]]:
        result = []
        for m in methods_by_type.get(type_id, []):
            n = m.get("name", "")
            if _is_dunder(n) or m.get("is_constructor"):
                continue
            if m.get("visibility", "public") == "private":
                continue
            if any(n.startswith(p) for p in _SKIP_PFXS) and len(n) <= 12:
                continue
            if n.lower() in _TRIVIAL_NAMES:
                continue
            result.append(m)
        if not result:
            for m in methods_by_type.get(type_id, []):
                n = m.get("name", "")
                if not m.get("is_constructor") and not _is_dunder(n):
                    if m.get("visibility", "public") != "private":
                        result.append(m)
                        if len(result) >= 2:
                            break
        return result[:max_count]

    def _safe_type(raw: str) -> str:
        t = _clean_type_short(raw or "")
        return t.replace("[]", "").strip()

    def fmt_call(method: Dict[str, Any]) -> str:
        name   = method.get("name", "call")
        mid    = method.get("_id", "")
        params = params_by_method.get(mid, [])[:3]
        parts  = []
        for p in params:
            pn = p.get("name", "")
            pt = _safe_type(p.get("raw_type") or p.get("type_name") or "")
            if pn and pt:
                parts.append(pn + ": " + pt)
            elif pn:
                parts.append(pn)
        suffix = ", ..." if len(params_by_method.get(mid, [])) > 3 else ""
        return name + "(" + ", ".join(parts) + suffix + ")"

    def fmt_ret(method: Dict[str, Any]) -> Optional[str]:
        rt = _safe_type(method.get("raw_return_type") or method.get("return_type") or "")
        if not rt or rt.lower() in ("void", "none", "unit"):
            return None
        if rt == "ResponseEntity":
            return "HTTP Response"
        if rt.lower() in ("boolean", "bool"):
            return "boolean"
        if rt.lower() in ("string", "str"):
            return "String"
        return rt

    def _is_list_return(method: Dict[str, Any]) -> bool:
        rt = (method.get("raw_return_type") or method.get("return_type") or "").lower()
        return any(k in rt for k in ("list", "collection", "set", "iterable", "[]", "array"))

    def _is_bool_return(method: Dict[str, Any]) -> bool:
        rt = _safe_type(method.get("raw_return_type") or method.get("return_type") or "")
        return rt.lower() in ("boolean", "bool")

    # 10. Build PlantUML
    out: List[str] = [
        "@startuml",
        "",
        "skinparam sequenceArrowThickness 2",
        "skinparam roundcorner 5",
        "skinparam maxmessagesize 250",
        "skinparam responseMessageBelowArrow true",
        "skinparam shadowing false",
        "",
        "autoactivate on",
        "",
    ]

    if not ordered:
        out.append('note "No architectural participants found in CIR." as N1')
        out.append("@enduml")
        return "\n".join(out)

    # Identify boundary (controller) participants — these receive the initial
    # HTTP request from the external Client actor.
    boundary_names: List[str] = [
        type_attrs[tid].get("name", tid)
        for tid in ordered
        if _participant_keyword(tid) == "boundary"
    ]

    # Declare participants — Client actor always first (leftmost lifeline),
    # followed by all internal participants in architectural layer order.
    out.append('actor "Client" as Client')
    for tid in ordered:
        nm      = type_attrs[tid].get("name", tid)
        keyword = _participant_keyword(tid)
        out.append(f'{keyword} "{nm}" as {nm}')
    out.append("")

    # Emit Client -> Controller trigger arrows for each entry-point controller.
    # With autoactivate on, every -> must have a matching --> to close the bar.
    for ctrl_name in boundary_names:
        out.append(f"Client -> {ctrl_name} : HTTP Request")
        out.append(f"{ctrl_name} --> Client : HTTP Response")
    if boundary_names:
        out.append("")

    # ── FIX: PRIMARY path — derive messages exclusively from CALLS edges ──────
    # CALLS edges represent actual runtime method invocations and are the only
    # correct source of messages in a Sequence Diagram.
    has_arrows   = False
    shown:       Set[Tuple[str, str, str]] = set()
    using_calls  = bool(calls_by_src)

    if using_calls:
        # Collect all call triples in order
        call_triples: List[Tuple[int, str, str, Dict[str, Any]]] = []
        for src_m, call_list in calls_by_src.items():
            s_tid = method_owner.get(src_m)
            if not s_tid or s_tid in excluded_types or s_tid not in seen:
                continue
            s_name = type_attrs[s_tid].get("name", s_tid)
            for call in call_list:
                dst_m = call.get("dst")
                if not dst_m:
                    continue
                d_tid = method_owner.get(dst_m)
                if not d_tid or d_tid in excluded_types or d_tid not in seen:
                    continue
                d_name = type_attrs[d_tid].get("name", d_tid)
                dst_nm = method_name_by_id.get(dst_m, "")
                if not dst_nm or _is_dunder(dst_nm) or s_name == d_name:
                    continue
                mn = nodes_by_id.get(dst_m)
                if mn:
                    dummy        = dict(mn.get("attrs", {}))
                    dummy["_id"] = dst_m
                else:
                    dummy = {"name": dst_nm, "_id": dst_m}
                order = call.get("order", 0)
                call_triples.append((order, s_name, d_name, dummy))

        # Emit in call order
        call_triples.sort(key=lambda x: x[0])
        for _, s_name, d_name, dummy in call_triples:
            dst_nm = dummy.get("name", "call")
            key = (s_name, d_name, dst_nm)
            if key in shown:
                continue
            shown.add(key)
            cl      = fmt_call(dummy)
            rl      = fmt_ret(dummy)
            is_list = _is_list_return(dummy)
            is_bool = _is_bool_return(dummy)
            has_arrows = True

            if is_list:
                out.append("loop for each item")
                out.append("  " + s_name + " -> " + d_name + " : " + cl)
                # autoactivate on requires a return to close the activation bar
                out.append("  " + d_name + " --> " + s_name + " : " + (rl or "void"))
                out.append("end")
            elif is_bool:
                out.append("opt if successful")
                out.append("  " + s_name + " -> " + d_name + " : " + cl)
                out.append("  " + d_name + " --> " + s_name + " : boolean")
                out.append("end")
            else:
                out.append(s_name + " -> " + d_name + " : " + cl)
                # autoactivate on requires a return to close the activation bar
                out.append(d_name + " --> " + s_name + " : " + (rl or "void"))
        if has_arrows:
            out.append("")

    else:
        # ── FALLBACK — no CALLS data in CIR ───────────────────────────────────
        # Infer messages from structural ASSOCIATES/DEPENDS_ON edges.
        # FIX: note text uses \n (single backslash) for PlantUML line break,
        #      not \\n which produces a literal backslash-n in the rendered note.
        # FIX: note over references the first DECLARED participant (boundary first,
        #      then ordered[0]) to avoid referencing an undeclared lifeline.
        first_declared = (
            type_attrs[ordered[0]].get("name", ordered[0]) if ordered else ""
        )
        if first_declared:
            out.append(f'note over {first_declared}')
            out.append('  Messages inferred from class associations')
            out.append('  (no CALLS data in CIR — diagram is approximate)')
            out.append('end note')
            out.append("")

        assoc_pairs: Set[Tuple[str, str]] = set()
        for src, dests in associates.items():
            for dst in dests:
                if src not in excluded_types and dst not in excluded_types:
                    assoc_pairs.add((src, dst))

        emitted: Set[Tuple[str, str]] = set()
        for i in range(len(ordered) - 1):
            c_tid  = ordered[i]
            c_name = type_attrs[c_tid].get("name", c_tid)
            callees = [
                tid for tid in ordered[i + 1:]
                if (c_tid, tid) in assoc_pairs and (c_tid, tid) not in emitted
            ]
            if not callees:
                continue

            for e_tid in callees:
                e_name  = type_attrs[e_tid].get("name", e_tid)
                emitted.add((c_tid, e_tid))
                methods = useful_methods(e_tid, max_count=4)

                if not methods:
                    out.append(c_name + " -> " + e_name + " : request()")
                    out.append(e_name + " --> " + c_name + " : void")
                    has_arrows = True
                    # FIX: '...' sequence divider is INVALID with autoactivate on —
                    # it interrupts open activation bars and causes a 500 render crash.
                    # Removed entirely; blank line provides sufficient visual spacing.
                    out.append("")
                    continue

                has_arrows = True
                for m in methods:
                    cl      = fmt_call(m)
                    rl      = fmt_ret(m)
                    is_list = _is_list_return(m)
                    is_bool = _is_bool_return(m)
                    shown.add((c_name, e_name, m.get("name", "")))

                    if is_list:
                        out.append("loop for each item")
                        out.append("  " + c_name + " -> " + e_name + " : " + cl)
                        # autoactivate on requires a return to close the activation bar
                        out.append("  " + e_name + " --> " + c_name + " : " + (rl or "void"))
                        out.append("end")
                    elif is_bool:
                        out.append("opt if successful")
                        out.append("  " + c_name + " -> " + e_name + " : " + cl)
                        out.append("  " + e_name + " --> " + c_name + " : boolean")
                        out.append("end")
                    else:
                        out.append(c_name + " -> " + e_name + " : " + cl)
                        # autoactivate on requires a return to close the activation bar
                        out.append(e_name + " --> " + c_name + " : " + (rl or "void"))

                # FIX: '...' removed — invalid with autoactivate on (causes 500 render error)
                out.append("")

    if not has_arrows:
        first_p = type_attrs[ordered[0]].get("name", ordered[0]) if ordered else "Client"
        out.append(f"note over {first_p}")
        out.append("  No direct method call chains detected.")
        out.append("end note")

    out.append("@enduml")
    return "\n".join(out)


# ══════════════════════════════════════════════════════════════════════════════
#  COMPONENT DIAGRAM
#
#  Shows: components (notched rectangles), provided interfaces (lollipops),
#         component dependencies (uses arrows), package/subsystem grouping,
#         and architectural stereotype labels.
#
#  Does NOT show:
#    - INHERITS (--|>) — generalization is a classifier relationship that
#      belongs in the Class Diagram, not in a Component Diagram.
#    - IMPLEMENTS (..|>) — realization is also a classifier relationship.
#      When a class implements an interface, the interface appears as a
#      lollipop on the component; a realization arrow between classifiers
#      is not a component-level construct.
#    - Class attributes, operations, or field-level detail.
# ══════════════════════════════════════════════════════════════════════════════

def generate_component_diagram(cir: Dict[str, Any]) -> str:
    nodes_by_id, edges = _index_cir(cir)

    # Collect types — excluding infrastructure-noise classes (exceptions, loggers,
    # config holders, app entry points) which are not deployable components.
    type_nodes:  Dict[str, Dict[str, Any]] = {}
    package_of:  Dict[str, str] = {}

    for nid, n in nodes_by_id.items():
        if n.get("kind") != "TypeDecl":
            continue
        attrs = n.get("attrs", {})
        nm  = attrs.get("name",    "") or ""
        pkg = attrs.get("package", "") or ""
        if _is_infrastructure_noise(nm, pkg):
            continue
        type_nodes[nid] = attrs
        package_of[nid] = pkg or "(default)"

    # FIX: Only include component-level dependency edge types.
    # INHERITS and IMPLEMENTS are classifier relationships (Class Diagram concerns)
    # and must not appear in a Component Diagram.
    dep_edges: List[Tuple[str, str, str]] = []
    for e in edges:
        src, dst, etype = e.get("src"), e.get("dst"), e.get("type")
        if src and dst and etype and src != dst:
            if src in type_nodes and dst in type_nodes:
                if etype in ("ASSOCIATES", "DEPENDS_ON"):   # INHERITS and IMPLEMENTS removed
                    dep_edges.append((src, dst, etype))

    # Layer stereotype labels for packages and components
    _LAYERS: List[Tuple[str, str]] = [
        ("controller", "<<Controller>>"),
        ("resource",   "<<Controller>>"),
        ("endpoint",   "<<Controller>>"),
        ("rest",       "<<Controller>>"),
        ("handler",    "<<Controller>>"),
        ("service",    "<<Service>>"),
        ("manager",    "<<Service>>"),
        ("facade",     "<<Service>>"),
        ("repository", "<<Repository>>"),
        ("dao",        "<<Repository>>"),
        ("repo",       "<<Repository>>"),
        ("database",   "<<Database>>"),
        ("db",         "<<Database>>"),
        ("model",      "<<Model>>"),
        ("entity",     "<<Model>>"),
        ("domain",     "<<Model>>"),
        ("dto",        "<<DTO>>"),
        ("util",       "<<Utility>>"),
        ("helper",     "<<Utility>>"),
        ("config",     "<<Config>>"),
        ("security",   "<<Security>>"),
        ("filter",     "<<Security>>"),
        ("middleware", "<<Middleware>>"),
    ]

    def _layer_stereo(pkg: str, name: str) -> Optional[str]:
        combined = (pkg + " " + name).lower()
        for kw, stereo in _LAYERS:
            if kw in combined:
                return stereo
        return None

    def _arrow_label(dst_pkg: str, dst_name: str) -> str:
        combined = (dst_pkg + " " + dst_name).lower()
        if "database" in combined or "db" in combined:     return "queries"
        if "model" in combined or "entity" in combined:    return "maps"
        if "dao" in combined or "repository" in combined or "repo" in combined: return "delegates"
        if "util" in combined or "helper" in combined:     return "uses"
        return "uses"

    def _alias(tid: str) -> str:
        return re.sub(r"[^a-zA-Z0-9_]", "_", tid)

    def _iface_alias(tid: str) -> str:
        return "I_" + re.sub(r"[^a-zA-Z0-9_]", "_", tid)

    # Group types by package
    pkg_to_types: Dict[str, List[str]] = {}
    for tid in type_nodes:
        pkg = package_of[tid]
        pkg_to_types.setdefault(pkg, []).append(tid)

    # Common root prefix (for display shortening)
    all_pkgs = [p for p in pkg_to_types if p != "(default)"]
    root_prefix = ""
    if len(all_pkgs) > 1:
        parts_list = [p.split(".") for p in all_pkgs]
        common: List[str] = []
        for segs in zip(*parts_list):
            if len(set(segs)) == 1:
                common.append(segs[0])
            else:
                break
        root_prefix = ".".join(common)

    def _short_pkg(pkg: str) -> str:
        if pkg == "(default)":
            return "(default)"
        if root_prefix and pkg.startswith(root_prefix):
            rel = pkg[len(root_prefix):].lstrip(".")
            return rel if rel else "(root)"
        return pkg.rsplit(".", 1)[-1]

    # Types that are called (will get a provided-interface lollipop)
    called_types: Set[str] = set()
    for src, dst, _ in dep_edges:
        called_types.add(dst)

    # Build PlantUML
    out: List[str] = [
        "@startuml",
        "",
        "' Component diagram — shows architectural components and their interfaces",
        "' Notched-rectangle = component   Circle (lollipop) = provided interface",
        "' Only ASSOCIATES and DEPENDS_ON edges are shown (no classifier relationships)",
        "",
        "skinparam componentStyle      uml2",
        "skinparam defaultTextAlignment center",
        "skinparam shadowing           false",
        "left to right direction",
        "",
        "skinparam package {",
        "  FontStyle        Bold",
        "}",
        "",
    ]

    # Root frame
    use_root = bool(root_prefix) and len(all_pkgs) > 1
    indent = ""
    if use_root:
        out.append(f'package "{root_prefix}" {{')
        indent = "  "

    def _pkg_sort(pkg: str) -> Tuple[int, str]:
        s = _short_pkg(pkg)
        if s in ("(root)", "(default)"):
            return (0, "")
        return (1 + _layer_order("", s), s)

    for pkg in sorted(pkg_to_types.keys(), key=_pkg_sort):
        tids  = sorted(pkg_to_types[pkg], key=lambda t: type_nodes[t].get("name", ""))
        short = _short_pkg(pkg)

        stereo_counts: Dict[str, int] = {}
        for tid in tids:
            s = _layer_stereo(pkg, type_nodes[tid].get("name", ""))
            if s:
                stereo_counts[s] = stereo_counts.get(s, 0) + 1
        pkg_stereo = max(stereo_counts, key=stereo_counts.get) if stereo_counts else None

        is_root_level = short in ("(root)", "(default)")

        if not is_root_level:
            s_str = f" {pkg_stereo}" if pkg_stereo else ""
            out.append(f'{indent}package "{short}"{s_str} {{')
            inner = indent + "  "
        else:
            inner = indent

        for tid in tids:
            attrs  = type_nodes[tid]
            nm     = attrs.get("name", "UnknownType")
            alias  = _alias(tid)
            ialias = _iface_alias(tid)

            # Component with notch icon
            out.append(f'{inner}[{nm}] as {alias}')

            # Provided interface lollipop — only for components that are called
            if tid in called_types:
                out.append(f'{inner}() "{nm}" as {ialias}')
                out.append(f'{inner}{alias} - {ialias}')

        if not is_root_level:
            out.append(f'{indent}}}')
        out.append("")

    if use_root:
        out.append("}")
        out.append("")

    # Component dependency arrows — caller to callee's provided interface
    # FIX: Only "uses" arrows (from ASSOCIATES / DEPENDS_ON).
    # INHERITS and IMPLEMENTS have already been excluded from dep_edges above.
    arrow_set: Set[Tuple[str, str]] = set()
    for src_id, dst_id, etype in dep_edges:
        src_alias = _alias(src_id)
        dst_alias = _iface_alias(dst_id) if dst_id in called_types else _alias(dst_id)
        pair = (src_alias, dst_alias)
        if pair in arrow_set:
            continue
        arrow_set.add(pair)
        label = _arrow_label(package_of[dst_id], type_nodes[dst_id].get("name", ""))
        out.append(f"{src_alias} --> {dst_alias} : {label}")

    out.append("")
    out.append("@enduml")
    return "\n".join(out)