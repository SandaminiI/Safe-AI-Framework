from fastapi import FastAPI, HTTPException  # type: ignore
from pydantic import BaseModel  # type: ignore
from typing import Any, Dict

from uml_rules import (
    generate_plantuml_from_cir,  # default class diagram
    generate_class_diagram,
    generate_package_diagram,
    generate_sequence_diagram,   # <-- NEW
)

app = FastAPI(title="UML Regex Generator (CIR -> PlantUML)")


class UMLRegexRequest(BaseModel):
    cir: Dict[str, Any]
    diagram_type: str = "class"  # "class", "package", or "sequence"


class UMLRegexResponse(BaseModel):
    plantuml: str


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/uml/regex", response_model=UMLRegexResponse)
def uml_regex(req: UMLRegexRequest):
    dt = req.diagram_type.lower().strip()

    if dt == "class":
        plantuml = generate_class_diagram(req.cir)
    elif dt == "package":
        plantuml = generate_package_diagram(req.cir)
    elif dt == "sequence":
        plantuml = generate_sequence_diagram(req.cir)
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported diagram_type: {req.diagram_type}",
        )

    return UMLRegexResponse(plantuml=plantuml)


# Optional: run locally
if __name__ == "__main__":
    import uvicorn # type: ignore

    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=7080,
        reload=True,
    )
