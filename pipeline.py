"""
Sunshine 支付管线编排。

5 步：req(mock x402) → pre(真实) → kya(stub) → dex(stub) → settle(stub)
只有 Precheck 是真实打 XRPL testnet 的；其余三步是留好接口的 stub，
你之后往 _task_kya / _task_dex / _task_settle 里填真实逻辑即可，不动其他部分。

每步返回一个 dict: {id, label, status, log, payload}
  status ∈ pass / fail / skipped
管线整体返回: {ok, halted_at, tasks:[...]}
"""

from xrpl.clients import JsonRpcClient

from account_utils import require_active, require_sufficient_balance, get_xrp_balance

TESTNET_URL = "https://s.altnet.rippletest.net:51234"


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


def _task_kya(intent: dict, unverified: bool) -> dict:
    """Task 2 · KYA gate —— STUB。TODO: 接真实 XLS-70 credential 查询。"""
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
    """Task 3 · DEX convert —— STUB。TODO: 接真实 DEX pathfinding。"""
    return {
        "id": "dex",
        "label": "Task 3 · DEX convert",
        "status": "pass",
        "log": f'DEX pathfind · {intent.get("amount")} {intent.get("source_currency","")} '
        f'→ {intent.get("target_currency","")} · (stub)',
        "payload": {"layer": "XRPL DEX · STUB", "note": "TODO: real pathfinding"},
    }


def _task_settle(intent: dict) -> dict:
    """Task 4 · Settle —— STUB。TODO: 接真实 XRPL Payment 结算。"""
    return {
        "id": "settle",
        "label": "Task 4 · Settle",
        "status": "pass",
        "log": f'Payment → {intent.get("payee_xrpl","payee")} · (stub) tesSUCCESS',
        "payload": {"layer": "XRPL ledger · STUB", "note": "TODO: real Payment submit"},
    }


def run_pipeline(intent: dict, unverified: bool = False,
                 client: JsonRpcClient | None = None) -> dict:
    """跑完整管线。任一步 fail 即 halt，后续步标记 skipped。"""
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
