"""
Sunshine 支付管线编排。

5 步：req(mock x402) → pre(真实) → kya(stub) → dex(stub) → settle(stub)
只有 Precheck 是真实打 XRPL testnet 的；其余三步是留好接口的 stub，
你之后往 _task_kya / _task_dex / _task_settle 里填真实逻辑即可，不动其他部分。

每步返回一个 dict: {id, label, status, log, payload}
  status ∈ pass / fail / skipped
管线整体返回: {ok, halted_at, tasks:[...]}
"""

import os

import requests
from xrpl.clients import JsonRpcClient

from account_utils import require_active, require_sufficient_balance, get_xrp_balance

TESTNET_URL = "https://s.altnet.rippletest.net:51234"

# The fx-agent HTTP service (Node) does the REAL KYA -> DEX (XRP->INR) -> Settle work.
# Start it with:  cd fx-agent && npm run serve   (defaults to port 8787)
FX_AGENT_URL = os.environ.get("FX_AGENT_URL", "http://localhost:8787")


def _call_fx_agent(intent: dict, unverified: bool) -> dict:
    """POST the intent to the fx-agent and return its per-stage settlement result.

    KYA is taken as PASS by default; the 'unverified' toggle drives a real on-chain
    REVERT (XRP returned to the sender) instead.
    """
    forced = "REVERT" if unverified else "PASS"
    amount = intent.get("amount", 50)
    payee = intent.get("payee_xrpl", "")  # receiver bank's XRPL address (payout destination)
    resp = requests.post(
        f"{FX_AGENT_URL}/settle",
        json={"amount": amount, "forcedKYA": forced, "payeeXrpl": payee},
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()


def _task_req(intent: dict) -> dict:
    """x402 端点：收下 Alice 的支付意图，返回 402 Payment Required（mock）。"""
    return {
        "id": "req",
        "label": "Agent request",
        "status": "pass",
        "log": "POST /pay · intent received from Alice",
        "payload": {
            "layer": "x402 endpoint (mock)",
            "io": "Receive payment intent, return HTTP 402",
            "payer": intent.get("payer_xrpl", ""),
            "amount": f'{intent.get("amount")} {intent.get("source_currency", "")}'
            f' → {intent.get("target_currency", "")}',
            "status": "402 Payment Required",
        },
    }


def _task_pre(client: JsonRpcClient, intent: dict) -> dict:
    """Task 1 · Precheck —— 真实：账户激活 + Alice 钱够不够。"""
    alice = intent.get("payer_xrpl", "")
    required = float(intent.get("amount", 0) or 0)
    try:
        require_active(client, alice, role="Alice")
        require_sufficient_balance(client, alice, required, role="Alice")
        balance = get_xrp_balance(client, alice)
        return {
            "id": "pre",
            "label": "Task 1 · Precheck",
            "status": "pass",
            "log": f"account_info ok · activated=true · balance={balance} ≥ {required}",
            "payload": {
                "layer": "XRPL account_info (read-only, REAL)",
                "io": "Check payer activated + sufficient balance",
                "activated": True,
                "xrp_balance": balance,
                "required": required,
                "result": "PASS",
            },
        }
    except ValueError as e:
        return {
            "id": "pre",
            "label": "Task 1 · Precheck",
            "status": "fail",
            "log": f"precheck FAILED · {str(e).splitlines()[0]}",
            "payload": {
                "layer": "XRPL account_info (read-only, REAL)",
                "io": "Check payer activated + sufficient balance",
                "result": "FAIL",
                "reason": str(e),
            },
        }


# --- Tasks 2-4 now backed by the REAL fx-agent over HTTP (no longer stubs) ---

def _task_kya(fx: dict | None, err: str | None) -> dict:
    """Task 2 · KYA gate —— REAL (fx-agent, pre-conversion screen)."""
    if err or not fx:
        return {"id": "kya", "label": "Task 2 · KYA gate", "status": "fail",
                "log": f"fx-agent unreachable · {err or 'no response'}",
                "payload": {"layer": "fx-agent KYA gate", "error": err}}
    kya = fx.get("kya", {})
    allow = kya.get("decision") == "ALLOW"
    payload = {"layer": "fx-agent KYA gate (real, pre-conversion)",
               "decision": kya.get("decision"), "verdict": kya.get("verdict"),
               "mpt_issuance_id": fx.get("mptIssuanceId")}
    if not allow and fx.get("revert"):
        # DENY -> funds returned to sender on-chain; show the real revert tx.
        payload["reverted_to_sender"] = fx["revert"].get("returnedTo")
        payload["revert_tx"] = fx["revert"].get("hash")
        payload["explorer"] = fx["revert"].get("explorer")
    return {
        "id": "kya", "label": "Task 2 · KYA gate",
        "status": "pass" if allow else "fail",
        "log": f'KYA {kya.get("verdict")} · {kya.get("decision")}',
        "payload": payload,
    }


def _task_dex(fx: dict | None, err: str | None) -> dict:
    """Task 3 · DEX convert —— REAL (fx-agent: XRP -> INR on the XRPL AMM)."""
    if err or not fx:
        return {"id": "dex", "label": "Task 3 · DEX convert", "status": "fail",
                "log": f"fx-agent unreachable · {err or 'no response'}",
                "payload": {"layer": "fx-agent DEX", "error": err}}
    conv = fx.get("convert")
    if not conv:
        # KYA reverted -> no conversion happened
        rev = fx.get("revert") or {}
        return {"id": "dex", "label": "Task 3 · DEX convert", "status": "fail",
                "log": "no conversion · KYA reverted, funds returned to sender",
                "payload": {"layer": "fx-agent DEX", "reverted": True,
                            "revert_tx": rev.get("hash"), "explorer": rev.get("explorer")}}
    return {
        "id": "dex", "label": "Task 3 · DEX convert", "status": "pass",
        "log": f'DEX {conv.get("bridge")} → {conv.get("received")} · {conv.get("hash")}',
        "payload": {"layer": "XRPL DEX/AMM (real)", "bridge": conv.get("bridge"),
                    "received": conv.get("received"), "tx": conv.get("hash"),
                    "explorer": conv.get("explorer")},
    }


def _task_settle(fx: dict | None, err: str | None) -> dict:
    """Task 4 · Settle —— REAL (fx-agent: Payment to the bank = redemption)."""
    if err or not fx:
        return {"id": "settle", "label": "Task 4 · Settle", "status": "fail",
                "log": f"fx-agent unreachable · {err or 'no response'}",
                "payload": {"layer": "fx-agent settle", "error": err}}
    s = fx.get("settle")
    if not s:
        return {"id": "settle", "label": "Task 4 · Settle", "status": "fail",
                "log": "no settlement · pipeline did not reach payout",
                "payload": {"layer": "fx-agent settle", "status": fx.get("status")}}
    return {
        "id": "settle", "label": "Task 4 · Settle", "status": "pass",
        "log": f'Payment → bank {s.get("paidTo")} · {s.get("hash")} tesSUCCESS',
        "payload": {"layer": "XRPL ledger (real)", "paid_to_bank": s.get("paidTo"),
                    "tx": s.get("hash"), "explorer": s.get("explorer"),
                    "final_status": fx.get("status")},
    }


def run_pipeline(intent: dict, unverified: bool = False,
                 client: JsonRpcClient | None = None) -> dict:
    """Run the full pipeline. Any fail halts; later steps marked skipped.

    req + pre stay local; kya/dex/settle are driven by ONE call to the fx-agent.
    """
    client = client or JsonRpcClient(TESTNET_URL)
    tasks: list[dict] = []
    halted_at = None

    def skip(i):
        ids = ["req", "pre", "kya", "dex", "settle"]
        labels = ["Agent request", "Task 1 · Precheck", "Task 2 · KYA gate",
                  "Task 3 · DEX convert", "Task 4 · Settle"]
        return {"id": ids[i], "label": labels[i], "status": "skipped",
                "log": "skipped · pipeline halted", "payload": {"note": "skipped"}}

    # Step 0: req (mock x402)
    tasks.append(_task_req(intent))

    # Step 1: pre (real precheck)
    pre = _task_pre(client, intent)
    tasks.append(pre)
    if pre["status"] == "fail":
        tasks += [skip(2), skip(3), skip(4)]
        return {"ok": False, "halted_at": "pre", "tasks": tasks}

    # Steps 2-4: one real call to the fx-agent, split into KYA / DEX / Settle cards.
    fx, err = None, None
    try:
        fx = _call_fx_agent(intent, unverified)
    except Exception as e:  # fx-agent down / network / settlement error
        err = str(e)

    for builder, sid in ((_task_kya, "kya"), (_task_dex, "dex"), (_task_settle, "settle")):
        if halted_at is not None:
            tasks.append(skip({"kya": 2, "dex": 3, "settle": 4}[sid]))
            continue
        result = builder(fx, err)
        tasks.append(result)
        if result["status"] == "fail":
            halted_at = result["id"]

    return {"ok": halted_at is None, "halted_at": halted_at, "tasks": tasks}
