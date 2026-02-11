import os
import javalang # type: ignore
from typing import Dict, Any, List, Tuple
from cir.model import TypeDecl, Field, Method, Parameter
from cir.graph import CIRGraph

class JavaAdapter:
    """
    Java → CIRGraph builder.
    Parses one or more Java compilation units, creates nodes for
    classes/fields/methods/parameters, and edges for:
      - HAS_FIELD, HAS_METHOD, PARAM_OF
      - INHERITS, IMPLEMENTS
      - ASSOCIATES, DEPENDS_ON
    Includes:
      - Multi-file (project-level) support
      - Generics & collections (multiplicity heuristics)
      - Constructor detection
      - Modifier flags (static/abstract/final)
    """
    language = "java"

    # ---------------- Helpers ----------------

    COLLECTION_TYPES = {"List", "Set", "Collection", "Map"}

    def _visibility_from_mods(self, mods: set[str] | None) -> str:
        mods = mods or set()
        if "public" in mods:
            return "public"
        if "private" in mods:
            return "private"
        if "protected" in mods:
            return "protected"
        return "package"

    def _flags_from_mods(self, mods: set[str] | None) -> Tuple[bool, bool, bool]:
        """
        Returns (is_static, is_abstract, is_final)
        """
        mods = mods or set()
        return (
            "static" in mods,
            "abstract" in mods,
            "final" in mods,
        )

    def _resolve_type_name_and_multiplicity(self, t) -> Tuple[str, str, None | str]:
        """
        From a javalang Type node, derive:
          - logical_type (e.g. "Item")
          - raw_type (e.g. "List<Item>")
          - multiplicity (e.g. "1", "1..*", "0..*")
        We use simple heuristics for generics and arrays.
        """
        if t is None:
            return "void", "void", None

        base_name = getattr(t, "name", "Object")
        raw_type = base_name
        multiplicity: None | str = None
        logical_type = base_name

        # generics: List<Item>, Set<Order>, Map<K,V>
        args = getattr(t, "arguments", None)
        if args:
            try:
                # javalang's type arguments often wrap a .type
                first_arg = args[0]
                inner_type = getattr(first_arg, "type", first_arg)
                inner_name = getattr(inner_type, "name", None)
                if inner_name:
                    logical_type = inner_name
                    raw_type = f"{base_name}<{inner_name}>"
                    multiplicity = "1..*"  # one-to-many
            except Exception:
                # fall back if something unexpected
                logical_type = base_name
                raw_type = base_name

        # arrays: Type[]
        dims = getattr(t, "dimensions", None)
        if dims:
            # treat as many
            multiplicity = multiplicity or "0..*"
            raw_type = f"{raw_type}[]"

        # if it's a known collection type but we didn't see generic args
        if base_name in self.COLLECTION_TYPES and multiplicity is None:
            multiplicity = "0..*"

        # default multiplicity for single values
        if multiplicity is None and logical_type not in self.COLLECTION_TYPES:
            multiplicity = "1"

        return logical_type, raw_type, multiplicity

    # ---------------- Parsing entry points ----------------

    def parse_to_ast(self, code: str):
        try:
            return javalang.parse.parse(code)
        except javalang.parser.JavaSyntaxError as e:
            raise ValueError(f"Java syntax error: {e}")
        except Exception as e:
            raise ValueError(f"Failed to parse Java code: {e}")

    # def build_cir_graph_for_code(self, code: str, filename: str | None = None) -> CIRGraph:
    #     """
    #     Single-compilation-unit helper (for /parse).
    #     """
    #     graph = CIRGraph()
    #     self._process_compilation_unit(code, graph, type_nodes={}, units=[])
    #     return graph

    def build_cir_graph_for_code(self, code: str, filename: str | None = None) -> CIRGraph:
        graph = CIRGraph()
        type_nodes: Dict[str, str] = {}
        units: List[Dict[str, Any]] = []

        # fill graph + collect type/field/method info
        self._process_compilation_unit(
            code,
            graph,
            type_nodes,
            units,
            source_file=filename,
        )

        # now add INHERITS / IMPLEMENTS / ASSOCIATES / DEPENDS_ON edges
        self._add_relationship_edges(graph, type_nodes, units)
        return graph


    def build_cir_graph_for_files(self, files: List[str]) -> CIRGraph:
        """
        Multi-file/project-level CIRGraph builder.
        'files' is a list of .java file paths.
        """
        graph = CIRGraph()
        type_nodes: Dict[str, str] = {}
        units: List[Dict[str, Any]] = []

        for path in files:
            with open(path, "r", encoding="utf-8") as f:
                code = f.read()
            self._process_compilation_unit(code, graph, type_nodes, units, source_file=path)

        # once all types are known, add inheritance + associations/depends
        self._add_relationship_edges(graph, type_nodes, units)
        return graph

    # ---------------- Core processing ----------------

    def _process_compilation_unit(
        self,
        code: str,
        graph: CIRGraph,
        type_nodes: Dict[str, str],
        units: List[Dict[str, Any]],
        source_file: str | None = None,
    ) -> None:
        """
        Process one compilation unit (one .java file), add nodes and basic edges.
        'type_nodes' and 'units' are shared across files for project-level graphs.
        """
        tree = self.parse_to_ast(code)
        package_name = getattr(getattr(tree, "package", None), "name", None)

        for t in tree.types:
            # fully-qualified name if package exists
            short_name = t.name
            full_name = f"{package_name}.{short_name}" if package_name else short_name

            type_id = f"type:{full_name}"
            kind = type(t).__name__.replace("Declaration", "").lower()  # class/interface/enum
            visibility = self._visibility_from_mods(t.modifiers or set())
            is_static, is_abstract, is_final = self._flags_from_mods(t.modifiers or set())

            type_decl = TypeDecl(
                id=type_id,
                name=short_name,
                kind=kind,
                visibility=visibility,
                package=package_name,
                modifiers=tuple(t.modifiers or []),
                is_abstract=is_abstract,
                is_final=is_final,
            )
            graph.add_node(type_id, "TypeDecl", type_decl)
            type_nodes[full_name] = type_id

            unit = {
                "id": type_id,
                "short_name": short_name,
                "full_name": full_name,
                "fields": [],
                "methods": [],
                "extends": [],
                "implements": [],
                "source_file": source_file,
            }

            # extends / implements (store names, we'll resolve later)
            if hasattr(t, "extends") and t.extends:
                try:
                    # extends can be a single or list
                    if hasattr(t.extends, "name"):
                        names = [t.extends.name]
                    else:
                        names = [e.name for e in t.extends]
                except Exception:
                    names = []
                unit["extends"] = names

            if hasattr(t, "implements") and t.implements:
                unit["implements"] = [i.name for i in t.implements]

            # ---------- fields ----------
            for field in getattr(t, "fields", []):
                logical_type, raw_type, multiplicity = self._resolve_type_name_and_multiplicity(field.type)
                for decl in field.declarators:
                    field_id = f"field:{full_name}:{decl.name}"
                    visibility = self._visibility_from_mods(field.modifiers or set())
                    mods = field.modifiers or set()

                    field_node = Field(
                        id=field_id,
                        name=decl.name,
                        type_name=logical_type,
                        raw_type=raw_type,
                        visibility=visibility,
                        modifiers=tuple(mods),
                        multiplicity=multiplicity,
                    )
                    graph.add_node(field_id, "Field", field_node)
                    graph.add_edge(type_id, field_id, "HAS_FIELD")

                    unit["fields"].append({
                        "id": field_id,
                        "element_type": logical_type,
                        "raw_type": raw_type,
                        "multiplicity": multiplicity,
                    })

            # ---------- methods ----------
            # 1) normal methods
            for method in getattr(t, "methods", []):
                method_id = f"method:{full_name}:{method.name}"
                visibility = self._visibility_from_mods(method.modifiers or set())
                mods = method.modifiers or set()
                is_static, is_abs, is_final = self._flags_from_mods(mods)

                logical_ret, raw_ret, _ = self._resolve_type_name_and_multiplicity(method.return_type)

                method_node = Method(
                    id=method_id,
                    name=method.name,
                    return_type=logical_ret,
                    raw_return_type=raw_ret,
                    visibility=visibility,
                    modifiers=tuple(mods),
                    is_constructor=False,
                    is_static=is_static,
                    is_abstract=is_abs,
                    is_final=is_final,
                )
                graph.add_node(method_id, "Method", method_node)
                graph.add_edge(type_id, method_id, "HAS_METHOD")

                param_infos = []
                for p in method.parameters:
                    p_id = f"param:{full_name}:{method.name}:{p.name}"
                    logical, raw, _ = self._resolve_type_name_and_multiplicity(p.type)
                    param_node = Parameter(
                        id=p_id,
                        name=p.name,
                        type_name=logical,
                        raw_type=raw,
                    )
                    graph.add_node(p_id, "Parameter", param_node)
                    graph.add_edge(p_id, method_id, "PARAM_OF")
                    param_infos.append({"id": p_id, "type_name": logical})

                unit["methods"].append({
                    "id": method_id,
                    "return_type": logical_ret,
                    "params": param_infos,
                })

            # 2) constructors
            for ctor in getattr(t, "constructors", []):
                ctor_id = f"ctor:{full_name}:{ctor.name}"
                visibility = self._visibility_from_mods(ctor.modifiers or set())
                mods = ctor.modifiers or set()
                is_static, is_abs, is_final = self._flags_from_mods(mods)

                # constructors have no return type, treat as void/raw="<ctor>"
                method_node = Method(
                    id=ctor_id,
                    name=ctor.name,
                    return_type="void",
                    raw_return_type="<constructor>",
                    visibility=visibility,
                    modifiers=tuple(mods),
                    is_constructor=True,
                    is_static=is_static,
                    is_abstract=is_abs,
                    is_final=is_final,
                )
                graph.add_node(ctor_id, "Method", method_node)
                graph.add_edge(type_id, ctor_id, "HAS_METHOD")

                param_infos = []
                for p in ctor.parameters:
                    p_id = f"param:{full_name}:{ctor.name}:{p.name}"
                    logical, raw, _ = self._resolve_type_name_and_multiplicity(p.type)
                    param_node = Parameter(
                        id=p_id,
                        name=p.name,
                        type_name=logical,
                        raw_type=raw,
                    )
                    graph.add_node(p_id, "Parameter", param_node)
                    graph.add_edge(p_id, ctor_id, "PARAM_OF")
                    param_infos.append({"id": p_id, "type_name": logical})

                unit["methods"].append({
                    "id": ctor_id,
                    "return_type": "void",
                    "params": param_infos,
                })

            units.append(unit)

    def _add_relationship_edges(
        self,
        graph: CIRGraph,
        type_nodes: Dict[str, str],
        units: List[Dict[str, Any]],
    ) -> None:
        """
        Once all types/fields/methods are known, add:
          - INHERITS, IMPLEMENTS
          - ASSOCIATES (field element types)
          - DEPENDS_ON (parameter/return types)
        """
        # For name resolution we use both full and short names (simple heuristic)
        full_to_id = dict(type_nodes)
        short_to_id: Dict[str, str] = {}
        for full_name, nid in type_nodes.items():
            short_name = full_name.split(".")[-1]
            short_to_id.setdefault(short_name, nid)

        def resolve_type_name(tname: str) -> str | None:
            if tname in full_to_id:
                return full_to_id[tname]
            if tname in short_to_id:
                return short_to_id[tname]
            return None

        for u in units:
            src_id = u["id"]

            # ---------- INHERITS / IMPLEMENTS ----------
            for base in u["extends"]:
                target = resolve_type_name(base)
                if target and target != src_id:
                    graph.add_edge(src_id, target, "INHERITS")

            for iface in u["implements"]:
                target = resolve_type_name(iface)
                if target and target != src_id:
                    graph.add_edge(src_id, target, "IMPLEMENTS")

            # ---------- ASSOCIATES & DEPENDS_ON ----------
            # from field element types
            for f in u["fields"]:
                tname = f["element_type"]
                mult = f.get("multiplicity")
                target = resolve_type_name(tname)
                if target and target != src_id:
                    graph.add_edge(src_id, target, "ASSOCIATES", multiplicity=mult)

            # from method/constructor params + return types
            for m in u["methods"]:
                for p in m["params"]:
                    tname = p["type_name"]
                    target = resolve_type_name(tname)
                    if target and target != src_id:
                        graph.add_edge(src_id, target, "DEPENDS_ON")

                rtype = m["return_type"]
                target = resolve_type_name(rtype)
                if target and target != src_id:
                    graph.add_edge(src_id, target, "DEPENDS_ON")
