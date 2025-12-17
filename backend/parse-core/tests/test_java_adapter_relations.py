import os
import sys

CURRENT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from adapters.java_adapter import JavaAdapter

def get_type_nodes(cir_json):
    return {n["attrs"]["name"]: n for n in cir_json["nodes"] if n["kind"] == "TypeDecl"}

def test_association_and_multiplicity():
    code = """
    import java.util.List;
    class Item {}

    class Order {
        private List<Item> items;
        private Item mainItem;

        public Order(List<Item> items, Item mainItem) {
            this.items = items;
            this.mainItem = mainItem;
        }
    }
    """
    adapter = JavaAdapter()
    graph = adapter.build_cir_graph_for_code(code)
    data = graph.to_debug_json()

    nodes_by_id = {n["id"]: n for n in data["nodes"]}
    edges = {(e["src"], e["dst"], e["type"]) for e in data["edges"]}

    type_nodes = get_type_nodes(data)
    order_id = type_nodes["Order"]["id"]
    item_id = type_nodes["Item"]["id"]

    # class-level associations and dependencies
    assert (order_id, item_id, "ASSOCIATES") in edges
    assert (order_id, item_id, "DEPENDS_ON") in edges

    # check field multiplicity for items
    field_nodes = [n for n in data["nodes"] if n["kind"] == "Field"]
    items_field = [f for f in field_nodes if f["attrs"]["name"] == "items"][0]
    assert items_field["attrs"]["multiplicity"] == "1..*"
