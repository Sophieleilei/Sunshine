"""
Sunshine 后端 (FastAPI)。

  GET  /         -> 提供 sunshine.html 前端
  POST /pay      -> 接收 Alice 的 x402 支付意图，跑真实管线，返回结果 JSON
  GET  /health   -> 健康检查

启动：
  .venv/bin/uvicorn app:app --reload --port 8000
  浏览器打开 http://localhost:8000
"""

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from pipeline import run_pipeline

BASE = Path(__file__).parent
WALLETS_FILE = BASE / "demo_wallets.json"

app = FastAPI(title="Sunshine", description="x402 → XRPL payment pipeline demo")


def alice_address() -> str:
    """Alice = demo_wallets.json 里的固定钱包。"""
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
    """前端用来预填 Alice 的真实地址。"""
    return {"address": alice_address()}


@app.post("/pay")
def pay(req: PayRequest):
    """Alice 的 (mock) x402 请求入口 -> 跑真实管线。"""
    intent = dict(req.intent)
    # 若前端没填 payer，默认用固定的 Alice 地址（保证 Precheck 打到真实账户）
    if not intent.get("payer_xrpl"):
        intent["payer_xrpl"] = alice_address()
    try:
        result = run_pipeline(intent, unverified=req.unverified)
    except Exception as e:  # XRPL 网络异常等 -> 500 + 原因
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})
    return result
