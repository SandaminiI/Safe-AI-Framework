import networkx as nx # type: ignore
from typing import Any, Dict

class CIRGraph:
    """
    Typed multi-graph representing the CIR.
    Nodes: TypeDecl, Field, Method, Parameter, ...
    Edges: HAS_FIELD, HAS_METHOD, PARAM_OF, INHERITS, IMPLEMENTS,
           ASSOCIATES, DEPENDS_ON, ...
    """
    def __init__(self) -> None:
        self.g = nx.MultiDiGraph()

    def add_node(self, node_id: str, kind: str, payload: Any) -> None:
        self.g.add_node(node_id, kind=kind, payload=payload)

    def add_edge(self, src: str, dst: str, etype: str) -> None:
        """
        etype examples: HAS_FIELD, HAS_METHOD, INHERITS, IMPLEMENTS,
                        ASSOCIATES, DEPENDS_ON, PARAM_OF, ...
        """
        self.g.add_edge(src, dst, etype=etype)

    def to_debug_json(self) -> Dict[str, Any]:
        """
        Convert graph to JSON-like dict for debugging / API responses.
        CIR is still a graph internally; this is just a view.
        """
        nodes = []
        for node_id, data in self.g.nodes(data=True):
            payload = data.get("payload")
            if hasattr(payload, "__dict__"):
                attrs = dict(payload.__dict__)
            else:
                attrs = dict(payload) if isinstance(payload, dict) else {}
            nodes.append({
                "id": node_id,
                "kind": data.get("kind"),
                "attrs": attrs,
            })

        edges = []
        for src, dst, data in self.g.edges(data=True):
            edges.append({
                "src": src,
                "dst": dst,
                "type": data.get("etype"),
            })

        return {"nodes": nodes, "edges": edges}
