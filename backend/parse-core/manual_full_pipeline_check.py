import requests

PARSER_URL = "http://127.0.0.1:7070/parse"
UML_URL = "http://127.0.0.1:7080/uml/regex"
RENDER_URL = "http://127.0.0.1:7090/render/svg"

FILE_PATH = r"D:\SLIIT\Year 4\RP\PROJECT\CIRDemo.java"  # adjust this


def generate_diagram(cir, diagram_type: str, basename: str):
    # 1) CIR -> PlantUML
    uml_payload = {
        "cir": cir,
        "diagram_type": diagram_type,  # "class" or "package"
    }
    uml_resp = requests.post(UML_URL, json=uml_payload)
    uml_resp.raise_for_status()
    uml_data = uml_resp.json()
    plantuml = uml_data["plantuml"]

    print(f"\n=== PlantUML ({diagram_type.upper()} DIAGRAM) ===")
    print(plantuml)

    # Save PlantUML
    puml_name = f"{basename}_{diagram_type}.puml"
    with open(puml_name, "w", encoding="utf-8") as f:
        f.write(plantuml)
    print(f"Saved PlantUML to {puml_name}")

    # 2) PlantUML -> SVG
    render_payload = {"plantuml": plantuml}
    render_resp = requests.post(RENDER_URL, json=render_payload)
    render_resp.raise_for_status()
    render_data = render_resp.json()
    svg_text = render_data["svg"]

    svg_name = f"{basename}_{diagram_type}.svg"
    with open(svg_name, "w", encoding="utf-8") as f:
        f.write(svg_text)
    print(f"Saved SVG to {svg_name}")


def main():
    # 0) Read code
    with open(FILE_PATH, "r", encoding="utf-8") as f:
        code = f.read()

    # 1) Code -> CIR
    parse_payload = {"code": code, "filename": "CIRDemo.java"}
    parse_resp = requests.post(PARSER_URL, json=parse_payload)
    parse_resp.raise_for_status()
    parse_data = parse_resp.json()
    cir = parse_data["cir"]

    print("=== CIR nodes & edges ===")
    print("nodes:", len(cir["nodes"]), "edges:", len(cir["edges"]))

    # 2) Generate CLASS diagram
    generate_diagram(cir, diagram_type="class", basename="diagram")

    # 3) Generate PACKAGE diagram
    generate_diagram(cir, diagram_type="package", basename="diagram")


if __name__ == "__main__":
    main()
