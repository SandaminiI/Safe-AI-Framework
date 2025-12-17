from fastapi import FastAPI # type: ignore
from pydantic import BaseModel # type: ignore
from detect import detect_language
#from adapters.java_adapter import JavaAdapter

app = FastAPI()
#java_adapter = JavaAdapter()

class Req(BaseModel):
    code: str
    filename: str | None = None

@app.post("/detect")
def detect(req: Req):
    lang, conf, source = detect_language(req.code, req.filename)
    return {
        "language": lang,
        "confidence": conf,
        "source": source
    }

class ParseRequest(BaseModel):
    code: str
    filename: str | None = None

# @app.post("/parse")
# def parse(req: ParseRequest):
#     # detect language
#     lang, conf, source = detect_language(req.code, req.filename)

#     if lang == "java":
#         graph = java_adapter.build_cir_graph_for_code(req.code, req.filename)
#         cir_json = graph.to_debug_json()
#         return {
#             "language": lang,
#             "confidence": conf,
#             "source": source,
#             "cir": cir_json
#         }

#     # future: handle python / typescript
#     return {"error": f"Parsing not yet implemented for language: {lang}"}