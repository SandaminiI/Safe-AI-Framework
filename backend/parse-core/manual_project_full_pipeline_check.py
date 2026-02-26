import os
import glob
import requests

from adapters.java_adapter import JavaAdapter  

PROJECT_SRC_DIR = r"D:\SLIIT\Year 4\RP\PROJECT\Library Management"

UML_URL = "http://127.0.0.1:7080/uml/regex"
RENDER_URL = "http://127.0.0.1:7090/render/svg"

def collect_java_files(root_dir: str):
    """
    Find all .java files under root_dir (recursively).
    Returns list of absolute paths.
    """
    pattern = os.path.join(root_dir, "**", "*.java")
    return glob.glob(pattern, recursive=True)


def generate_diagram(cir, diagram_type: str, basename: str):
    """
    CIR -> PlantUML (uml-gen-regex) -> SVG (uml-renderer)
    Saves both .puml and .svg.
    """
    # CIR -> PlantUML
    uml_payload = {"cir": cir, "diagram_type": diagram_type}
    uml_resp = requests.post(UML_URL, json=uml_payload)
    uml_resp.raise_for_status()
    uml_data = uml_resp.json()
    plantuml = uml_data["plantuml"]

    puml_name = f"{basename}_{diagram_type}.puml"
    with open(puml_name, "w", encoding="utf-8") as f:
        f.write(plantuml)
    print(f"[OK] Saved PlantUML to {puml_name}")

    # PlantUML -> SVG
    render_payload = {"plantuml": plantuml}
    render_resp = requests.post(RENDER_URL, json=render_payload)
    render_resp.raise_for_status()
    render_data = render_resp.json()
    svg_text = render_data["svg"]

    svg_name = f"{basename}_{diagram_type}.svg"
    with open(svg_name, "w", encoding="utf-8") as f:
        f.write(svg_text)
    print(f"[OK] Saved SVG to {svg_name}")


def main():
    print(f"Scanning Java files under: {PROJECT_SRC_DIR}")
    java_files = collect_java_files(PROJECT_SRC_DIR)
    if not java_files:
        print("No .java files found. Check PROJECT_SRC_DIR.")
        return

    print(f"Found {len(java_files)} Java files:")
    for path in java_files:
        print("  -", path)


    # Build ONE CIR for ALL files at once
    adapter = JavaAdapter()
    graph = adapter.build_cir_graph_for_files(java_files)
    cir = graph.to_debug_json()

    print(
        f"\n[MERGED CIR] total: {len(cir['nodes'])} nodes, "
        f"{len(cir['edges'])} edges"
    )

    # Generate class + package diagrams
    print("\n[UML] Generating CLASS diagram...")
    generate_diagram(cir, "class", basename="project_diagram")

    print("\n[UML] Generating PACKAGE diagram...")
    generate_diagram(cir, "package", basename="project_diagram")

    print("\nDone. Check project_diagram_class.svg and project_diagram_package.svg")


if __name__ == "__main__":
    main()
