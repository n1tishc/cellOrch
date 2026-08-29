"""CV inference service: POST /analyze -> confluence + cell count."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel

from . import analyzer
from .logging_config import configure_logging, get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    yield


app = FastAPI(title="CellFlow CV Service", lifespan=lifespan)


class AnalyzeRequest(BaseModel):
    run_id: int
    image_index: int = 0


@app.post("/analyze")
def analyze(req: AnalyzeRequest):
    return analyzer.analyze(req.run_id, req.image_index)


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
