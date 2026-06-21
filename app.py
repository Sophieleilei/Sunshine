"""
Sunshine backend (FastAPI).

Non-custodial, compliance-gated agent cross-border payment orchestrator. Runs the
compliance + preparation pipeline (see pipeline.py); never holds the agent's private key.

  GET  /         -> serve the sunshine.html frontend
  POST /pay      -> receive Alice's payment intent, run the pipeline, return JSON
  GET  /health   -> health check

Run:
  .venv/bin/uvicorn app:app --reload --port 8000
  open http://localhost:8000
"""

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from pipeline import run_pipeline

BASE = Path(__file__).parent
WALLETS_FILE = BASE / "demo_wallets.json"

app = FastAPI(title="Sunshine",
              description="Non-custodial, compliance-gated agent cross-border payment orchestrator")


def alice_address() -> str:
    """Alice = the fixed wallet in demo_wallets.json."""
    if WALLETS_FILE.exists():
        data = json.loads(WALLETS_FILE.read_text())
        addr = data.get("main", {}).get("address")
        if addr:
            return addr
    return ""


class PayRequest(BaseModel):
    intent: dict
    unverified: bool = False


@app.get("/")
def index():
    return FileResponse(BASE / "sunshine.html")


@app.get("/health")
def health():
    return {"status": "ok", "alice": alice_address()}


@app.get("/alice")
def alice():
    """Used by the frontend to prefill Alice's real address."""
    return {"address": alice_address()}


@app.post("/pay")
def pay(req: PayRequest):
    """Entry point for Alice's payment intent -> run the pipeline."""
    intent = dict(req.intent)
    # If the frontend left payer empty, default to the fixed Alice address
    # so Precheck still hits a real account.
    if not intent.get("payer_xrpl"):
        intent["payer_xrpl"] = alice_address()
    try:
        result = run_pipeline(intent, unverified=req.unverified)
    except Exception as e:  # XRPL network errors etc. -> 500 + reason
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})
    return result
