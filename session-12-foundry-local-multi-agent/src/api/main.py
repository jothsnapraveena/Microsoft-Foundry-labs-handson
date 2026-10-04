"""FastAPI service: streams each agent's progress as newline-delimited JSON and serves the UI."""
from contextlib import asynccontextmanager
import json
import os
from pathlib import Path
import threading

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from foundry_config import MODEL_ALIAS, native_backend
from orchestrator import Pipeline

ALIAS = os.environ.get("FOUNDRY_MODEL_ALIAS", MODEL_ALIAS)
# The model is downloaded on first start unless FOUNDRY_OFFLINE=1.
OFFLINE = os.environ.get("FOUNDRY_OFFLINE") == "1"
RUNTIME_DIR = Path(os.environ.get("FOUNDRY_RUNTIME_DIR", "artifacts/runtime"))
UI_DIR = Path(__file__).parents[2] / "ui"
# One loaded model serves every request, so runs are serialized.
MODEL_LOCK = threading.Lock()


class Facts(BaseModel):
    model_config = ConfigDict(extra="forbid")
    order_id: str = Field(min_length=1, max_length=200)
    ordered: str = Field(min_length=1, max_length=200)
    received: str = Field(min_length=1, max_length=200)


class Case(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=100)
    customer: str = Field(min_length=1, max_length=4000)
    facts: Facts


@asynccontextmanager
async def lifespan(app):
    with native_backend(ALIAS, OFFLINE, RUNTIME_DIR) as backend:
        app.state.pipeline = Pipeline(backend.complete, stream=backend.stream)
        app.state.metadata = backend.metadata
        yield


app = FastAPI(title="Retail support agents", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ready", **app.state.metadata}


@app.post("/api/reply")
def reply(case: Case):
    pipeline = app.state.pipeline
    payload = case.model_dump()

    def lines():
        with MODEL_LOCK:
            for event in pipeline.create(payload):
                yield json.dumps(event) + "\n"

    return StreamingResponse(lines(), media_type="application/x-ndjson")


# Mounted last so the API routes above take precedence.
app.mount("/", StaticFiles(directory=UI_DIR, html=True), name="ui")
