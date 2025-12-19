import requests
import json

PARSER_URL = "http://127.0.0.1:7070/parse"
UML_URL = "http://127.0.0.1:7080/uml/regex"

FILE_PATH = r"D:\SLIIT\Year 4\RP\PROJECT\CIRDemo.java"  # adjust path

with open(FILE_PATH, "r", encoding="utf-8") as f:
    code = f.read()

parse_payload = {"code": code, "filename": "CIRDemo.java"}

# 1) Get CIR from parser-core
parse_resp = requests.post(PARSER_URL, json=parse_payload)
parse_data = parse_resp.json()

cir = parse_data.get("cir")
print("=== CIR (debug) ===")
print(json.dumps(cir, indent=2))

# 2) Send CIR to uml-gen-regex
uml_payload = {"cir": cir}
uml_resp = requests.post(UML_URL, json=uml_payload)
uml_data = uml_resp.json()

print("\n=== PlantUML ===")
print(uml_data.get("plantuml", "NO PLANTUML RECEIVED"))
