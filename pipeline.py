"""
Sunshine payment-pipeline orchestration.

5 steps: req(mock x402) -> pre(REAL) -> kya(stub) -> dex(stub) -> settle(stub)
Only Precheck actually hits the XRPL testnet; the other three are stubs with a
defined interface. Fill in real logic in _task_kya / _task_dex / _task_settle
later without touching anything else.

Each step returns a dict: {id, label, status, log, payload}
  status in pass / fail / skipped
The whole pipeline returns: {ok, halted_at, tasks:[...]}
"""

from xrpl.clients import JsonRpcClient

from account_utils import require_active, require_sufficient_balance, get_xrp_balance

TESTNET_URL = "https://s.altnet.rippletest.net:51234"


def _task_req(intent: dict) -> dict:
    """x402 endpoint: accept Alice's payment intent, return 402 Payment Required (mock)."""
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
    """Task 1 · Precheck — REAL: account activation + whether Alice has enough funds."""
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


def _task_kya(intent: dict, unverified: bool) -> dict:
    """Task 2 · KYA gate — STUB. TODO: wire up real XLS-70 credential lookup."""
    if unverified:
        return {
            "id": "kya",
            "label": "Task 2 · KYA gate",
            "status": "fail",
            "log": "no KYA credential found · DENY",
            "payload": {"layer": "XRPL Credentials (XLS-70) · STUB",
                        "decision": "DENY", "credential": "(none found)"},
        }
    return {
        "id": "kya",
        "label": "Task 2 · KYA gate",
        "status": "pass",
        "log": "credential VALID · ALLOW",
        "payload": {"layer": "XRPL Credentials (XLS-70) · STUB",
                    "decision": "ALLOW", "credential": "KYA_VERIFIED (stub)"},
    }


def _task_dex(intent: dict) -> dict:
    """Task 3 · DEX convert — STUB. TODO: wire up real DEX pathfinding."""
    return {
        "id": "dex",
        "label": "Task 3 · DEX convert",
        "status": "pass",
        "log": f'DEX pathfind · {intent.get("amount")} {intent.get("source_currency","")} '
        f'→ {intent.get("target_currency","")} · (stub)',
        "payload": {"layer": "XRPL DEX · STUB", "note": "TODO: real pathfinding"},
    }


def _task_settle(intent: dict) -> dict:
    """Task 4 · Settle — STUB. TODO: wire up a real XRPL Payment settlement."""
    return {
        "id": "settle",
        "label": "Task 4 · Settle",
        "status": "pass",
        "log": f'Payment → {intent.get("payee_xrpl","payee")} · (stub) tesSUCCESS',
        "payload": {"layer": "XRPL ledger · STUB", "note": "TODO: real Payment submit"},
    }


def run_pipeline(intent: dict, unverified: bool = False,
                 client: JsonRpcClient | None = None) -> dict:
    """Run the full pipeline. Any failing step halts it; later steps are marked skipped."""
    client = client or JsonRpcClient(TESTNET_URL)
    tasks: list[dict] = []
    halted_at = None

    steps = [
        lambda: _task_req(intent),
        lambda: _task_pre(client, intent),
        lambda: _task_kya(intent, unverified),
        lambda: _task_dex(intent),
        lambda: _task_settle(intent),
    ]
    step_ids = ["req", "pre", "kya", "dex", "settle"]
    step_labels = ["Agent request", "Task 1 · Precheck", "Task 2 · KYA gate",
                   "Task 3 · DEX convert", "Task 4 · Settle"]

    for i, step in enumerate(steps):
        if halted_at is not None:
            tasks.append({"id": step_ids[i], "label": step_labels[i],
                          "status": "skipped", "log": "skipped · pipeline halted",
                          "payload": {"note": "skipped"}})
            continue
        result = step()
        tasks.append(result)
        if result["status"] == "fail":
            halted_at = result["id"]

    return {"ok": halted_at is None, "halted_at": halted_at, "tasks": tasks}
