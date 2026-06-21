"""
Sunshine payment-pipeline orchestration — non-custodial, two-trip.

Tasks 2-6 (Trustline KYA, Prepare unsigned tx, Agent signs, Submit+convert) are now
backed by the bundled fx-agent over HTTP. The fx-agent is the agent: it holds its OWN
key in .env and signs locally — Sunshine only ever sees an UNSIGNED tx (Trip 1) and the
settlement result (Trip 2). The key never reaches Sunshine.

  Trip 1 (no money):  req -> pre -> [POST /prepare] -> kya + prepare cards
        --- the agent signs the unsigned tx with its OWN key (inside /submit) ---
  Trip 2 (money):     [POST /submit] -> sign + submit cards -> offramp (mock)

Each step returns {id, label, status, log, payload}; any fail halts the rest.
"""

import os

import requests
from xrpl.clients import JsonRpcClient

from account_utils import require_active, require_sufficient_balance, get_xrp_balance

TESTNET_URL = "https://s.altnet.rippletest.net:51234"
FX_AGENT_URL = os.environ.get("FX_AGENT_URL", "http://localhost:8787")


def _fx_prepare(intent: dict, unverified: bool) -> dict:
    """Trip 1: fx-agent mints the invoice, runs KYA, and builds the UNSIGNED tx."""
    forced = "REVERT" if unverified else "PASS"
    r = requests.post(
        f"{FX_AGENT_URL}/prepare",
        json={"amount": intent.get("amount", 10), "forcedKYA": forced,
              "payeeXrpl": intent.get("payee_xrpl", "")},
        timeout=120,
    )
    r.raise_for_status()
    return r.json()


def _fx_submit(prep: dict) -> dict:
    """Trip 2: fx-agent (the agent) signs the unsigned tx with its own key + submits."""
    r = requests.post(
        f"{FX_AGENT_URL}/submit",
        json={"unsignedTx": prep["unsignedTx"], "context": prep["context"]},
        timeout=120,
    )
    r.raise_for_status()
    return r.json()


def _task_req(intent: dict) -> dict:
    return {
        "id": "req", "label": "Agent request", "status": "pass",
        "log": "intent received from Alice (agent) · "
        f'{intent.get("amount")} {intent.get("source_currency", "")} '
        f'→ {intent.get("target_currency", "")}',
        "payload": {"layer": "Agent entry (MCP / direct API)", "io": "Receive payment intent",
                    "payer_xrpl": intent.get("payer_xrpl", ""),
                    "amount": f'{intent.get("amount")} {intent.get("source_currency", "")}',
                    "target_currency": intent.get("target_currency", "")},
    }


def _task_pre(client: JsonRpcClient, intent: dict) -> dict:
    alice = intent.get("payer_xrpl", "")
    required = float(intent.get("amount", 0) or 0)
    try:
        require_active(client, alice, role="Alice")
        require_sufficient_balance(client, alice, required, role="Alice")
        balance = get_xrp_balance(client, alice)
        return {"id": "pre", "label": "Task 1 · Precheck", "status": "pass",
                "log": f"account_info ok · activated=true · balance={balance} ≥ {required}",
                "payload": {"layer": "XRPL account_info (read-only, REAL)",
                            "activated": True, "xrp_balance": balance, "required": required, "result": "PASS"}}
    except ValueError as e:
        return {"id": "pre", "label": "Task 1 · Precheck", "status": "fail",
                "log": f"precheck FAILED · {str(e).splitlines()[0]}",
                "payload": {"layer": "XRPL account_info (read-only, REAL)", "result": "FAIL", "reason": str(e)}}


def _task_kya(prep, err) -> dict:
    """Task 2 · Trustline KYA — REAL (fx-agent, pre-conversion)."""
    if err or not prep:
        return {"id": "kya", "label": "Task 2 · Trustline KYA", "status": "fail",
                "log": f"fx-agent unreachable · {err or 'no response'}",
                "payload": {"layer": "fx-agent KYA", "error": err}}
    allow = prep.get("kya") == "PASS"
    payload = {"layer": "fx-agent KYA gate (real, pre-conversion)", "decision": "ALLOW" if allow else "DENY",
               "verdict": prep.get("kya"), "mpt_issuance_id": prep.get("mptIssuanceId")}
    if not allow and prep.get("revert"):
        payload["reverted_to_sender"] = prep["revert"].get("returnedTo")
        payload["revert_tx"] = prep["revert"].get("tx")
        payload["explorer"] = prep["revert"].get("explorer")
    return {"id": "kya", "label": "Task 2 · Trustline KYA", "status": "pass" if allow else "fail",
            "log": f'KYA {prep.get("kya")} · {"ALLOW" if allow else "DENY"}', "payload": payload}


def _task_prepare(prep, err) -> dict:
    """Task 3 · Prepare unsigned tx — REAL (end of Trip 1). The agent-built tx Alice signs."""
    if err or not prep or prep.get("status") != "PREPARED":
        return {"id": "prepare", "label": "Task 3 · Prepare unsigned tx", "status": "fail",
                "log": "no unsigned tx (KYA did not clear)", "payload": {"layer": "fx-agent prepare"}}
    pv = prep.get("preview", {})
    return {"id": "prepare", "label": "Task 3 · Prepare unsigned tx", "status": "pass",
            "log": f'built UNSIGNED tx · {pv.get("type","")} · seq {pv.get("sequence")} · (no key touched)',
            "payload": {"layer": "XRPL DEX pathfind + tx build (real, UNSIGNED)", **pv,
                        "txn_signature": "(none — unsigned)"}}


def _task_sign(sub, err) -> dict:
    """Agent signs — the non-custodial boundary. The fx-agent signed with its OWN key."""
    if err or not sub or not (sub.get("convert") and sub["convert"].get("tx")):
        return {"id": "sign", "label": "Agent signs (non-custodial)", "status": "fail",
                "log": "signing/submit failed", "payload": {"layer": "Agent-side local signing", "error": err}}
    return {"id": "sign", "label": "Agent signs (non-custodial)", "status": "pass",
            "log": "agent signed the unsigned tx locally · private key never left the agent",
            "payload": {"layer": "Agent-side local signing (real key in fx-agent .env)",
                        "signed_tx": sub["convert"].get("tx"), "note": "Sunshine only ever saw the UNSIGNED tx"}}


def _task_submit(sub, err) -> dict:
    """Task 4 · Submit + convert — REAL (start of Trip 2)."""
    if err or not sub:
        return {"id": "submit", "label": "Task 4 · Submit + convert", "status": "fail",
                "log": f"submit failed · {err or 'no response'}", "payload": {"layer": "fx-agent submit", "error": err}}
    conv, settle = sub.get("convert") or {}, sub.get("settle") or {}
    return {"id": "submit", "label": "Task 4 · Submit + convert", "status": "pass" if sub.get("status") == "PAID" else "fail",
            "log": f'submitted signed tx · DEX swap → {conv.get("received","")} · {conv.get("tx","")}',
            "payload": {"layer": "XRPL submit + DEX swap (real)", "converted": conv.get("received"),
                        "convert_tx": conv.get("tx"), "convert_explorer": conv.get("explorer"),
                        "paid_to_bank": settle.get("paidToBank"), "payout_tx": settle.get("tx"),
                        "payout_explorer": settle.get("explorer")}}


def _task_offramp(intent: dict, sub) -> dict:
    """Task 5 · Bank off-ramp — MOCK (the licensed off-ramp pays the recipient's bank)."""
    paid = bool(sub and sub.get("status") == "PAID")
    return {"id": "offramp", "label": "Task 5 · Bank off-ramp",
            "status": "pass" if paid else "skipped",
            "log": f'off-ramp → {intent.get("payee_clabe", intent.get("payee_iban", "bank"))} · (mock) settled'
            if paid else "skipped",
            "payload": {"layer": "Licensed off-ramp → bank · MOCK",
                        "note": "TODO: integrate a licensed off-ramp; bank credits the recipient off-chain"}}


def run_pipeline(intent: dict, unverified: bool = False, client: JsonRpcClient | None = None) -> dict:
    client = client or JsonRpcClient(TESTNET_URL)
    tasks: list[dict] = []
    order = [("req", "Agent request"), ("pre", "Task 1 · Precheck"), ("kya", "Task 2 · Trustline KYA"),
             ("prepare", "Task 3 · Prepare unsigned tx"), ("sign", "Agent signs (non-custodial)"),
             ("submit", "Task 4 · Submit + convert"), ("offramp", "Task 5 · Bank off-ramp")]

    def skip_from(i):
        for k in range(i, len(order)):
            tasks.append({"id": order[k][0], "label": order[k][1], "status": "skipped",
                          "log": "skipped · pipeline halted", "payload": {"note": "skipped"}})

    tasks.append(_task_req(intent))
    pre = _task_pre(client, intent)
    tasks.append(pre)
    if pre["status"] == "fail":
        skip_from(2)
        return {"ok": False, "halted_at": "pre", "tasks": tasks}

    # Trip 1: prepare (mint + KYA + build unsigned).
    prep, err = None, None
    try:
        prep = _fx_prepare(intent, unverified)
    except Exception as e:
        err = str(e)

    kya = _task_kya(prep, err)
    tasks.append(kya)
    if kya["status"] == "fail":
        skip_from(3)
        return {"ok": False, "halted_at": "kya", "tasks": tasks}

    prep_card = _task_prepare(prep, err)
    tasks.append(prep_card)
    if prep_card["status"] == "fail":
        skip_from(4)
        return {"ok": False, "halted_at": "prepare", "tasks": tasks}

    # Trip 2: submit (agent signs + submits + payout).
    sub, serr = None, None
    try:
        sub = _fx_submit(prep)
    except Exception as e:
        serr = str(e)

    tasks.append(_task_sign(sub, serr))
    tasks.append(_task_submit(sub, serr))
    if not sub or sub.get("status") != "PAID":
        skip_from(6)
        return {"ok": False, "halted_at": "submit", "tasks": tasks}
    tasks.append(_task_offramp(intent, sub))

    return {"ok": True, "halted_at": None, "tasks": tasks}
