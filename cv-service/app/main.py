"""CV inference service: POST /analyze -> confluence + cell count."""
from fastapi import FastAPI
from pydantic import BaseModel

from . import analyzer

app = FastAPI(title="CellFlow CV Service")


class AnalyzeRequest(BaseModel):
    run_id: int
    image_index: int = 0


@app.post("/analyze")
def analyze(req: AnalyzeRequest):
    return analyzer.analyze(req.run_id, req.image_index)


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
