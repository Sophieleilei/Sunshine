"""
Sunshine payment-pipeline orchestration.

Sunshine is a non-custodial, compliance-gated cross-border payment orchestrator for AI
agents. An agent (Alice) holds an XRPL stablecoin and wants to pay a recipient abroad
(e.g. Mexico, in MXN, landing in a CLABE bank account). Sunshine runs compliance checks,
prepares the transaction and finds a conversion path — but NEVER holds the agent's
private key.

Two-trip, non-custodial signing model — the signature splits the flow in two:

  Trip 1 (before signature, no money moves)   -> Tasks 1-3
    req      Agent request: receive the payment intent
    pre      Task 1 · Precheck: activation + balance               [REAL]
    kya      Task 2 · Trustline KYA: issuer-authorized trustline   [TODO stub]
    prepare  Task 3 · Prepare unsigned tx: DEX pathfind + build    [TODO stub]

  -- agent signs the unsigned tx LOCALLY with its own key (sign) --

  Trip 2 (after signature, money moves)        -> Tasks 4-5
    submit   Task 4 · Submit + convert: submit signed tx, DEX swap, tokenize   [TODO stub]
    offramp  Task 5 · Bank off-ramp: licensed off-ramp lands MXN to CLABE      [TODO stub]

Sunshine only ever handles an unsigned-JSON tx and a signed blob — neither contains the
private key. Ownership is enforced by XRPL signature verification.

Each step returns a dict: {id, label, status, log, payload}
  status in pass / fail / skipped
The whole pipeline returns: {ok, halted_at, tasks:[...]}
"""

from xrpl.clients import JsonRpcClient

from account_utils import require_active, require_sufficient_balance, get_xrp_balance

TESTNET_URL = "https://s.altnet.rippletest.net:51234"


def _task_req(intent: dict) -> dict:
    """Agent request: receive the agent's payment intent (no x402 handshake)."""
    return {
        "id": "req",
        "label": "Agent request",
        "status": "pass",
        "log": "intent received from Alice · "
        f'{intent.get("amount")} {intent.get("source_currency", "")} '
        f'→ {intent.get("target_currency", "")}',
        "payload": {
            "layer": "Agent entry (MCP / direct API)",
            "io": "Receive payment intent",
            "payer_xrpl": intent.get("payer_xrpl", ""),
            "payee_clabe": intent.get("payee_clabe", ""),
            "amount": f'{intent.get("amount")} {intent.get("source_currency", "")}',
            "target_currency": intent.get("target_currency", ""),
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
    """Task 2 · Trustline KYA — STUB.

    TODO (real): Sunshine is the stablecoin issuer and sets RequireAuth, so it only
    authorizes a trustline for agents that pass review. The compliance signal is simply
    whether the agent holds that issuer-authorized trustline. Real implementation:
    query `account_lines` for the payer, look for a line to Sunshine's issuing address,
    and require the `authorized` flag to be set (ALLOW); otherwise DENY. This is the
    on-chain pre-settlement gate — it runs before any money moves.
    """
    if unverified:
        return {
            "id": "kya",
            "label": "Task 2 · Trustline KYA",
            "status": "fail",
            "log": "no issuer-authorized trustline · DENY",
            "payload": {"layer": "XRPL trustline (account_lines) · STUB",
                        "decision": "DENY", "authorized_trustline": False},
        }
    return {
        "id": "kya",
        "label": "Task 2 · Trustline KYA",
        "status": "pass",
        "log": "issuer-authorized trustline found · ALLOW",
        "payload": {"layer": "XRPL trustline (account_lines) · STUB",
                    "decision": "ALLOW", "authorized_trustline": True,
                    "issuer": "Sunshine (stub)"},
    }


def _task_prepare(intent: dict) -> dict:
    """Task 3 · Prepare unsigned tx — STUB (end of Trip 1).

    TODO (real): find a DEX path for source-stablecoin -> target token, construct the
    corresponding unsigned XRPL transaction (Payment with paths, or an OfferCreate),
    `autofill` it (sequence + fee), and return the UNSIGNED tx JSON to the agent.
    No private key is involved here — Sunshine only builds the transaction.
    """
    return {
        "id": "prepare",
        "label": "Task 3 · Prepare unsigned tx",
        "status": "pass",
        "log": f'DEX pathfind + build unsigned tx · {intent.get("amount")} '
        f'{intent.get("source_currency","")} → {intent.get("target_currency","")} · (stub)',
        "payload": {"layer": "XRPL DEX pathfind + tx build · STUB",
                    "note": "TODO: real pathfinding + unsigned tx returned to agent",
                    "returns": "unsigned tx JSON"},
    }


def _task_sign(intent: dict) -> dict:
    """Agent signs — the non-custodial boundary between Trip 1 and Trip 2.

    The agent signs the unsigned tx LOCALLY with its own key; the private key never
    reaches Sunshine. See sign_demo.py for a working proof of the signing function.
    (Shown here as a pipeline step; in the real flow this happens on the agent side.)
    """
    return {
        "id": "sign",
        "label": "Agent signs (non-custodial)",
        "status": "pass",
        "log": "agent signed unsigned tx locally · private key never left the agent",
        "payload": {"layer": "Agent-side local signing",
                    "note": "private key stays with the agent; Sunshine gets only a signed blob",
                    "see": "sign_demo.py"},
    }


def _task_submit(intent: dict) -> dict:
    """Task 4 · Submit + convert — STUB (start of Trip 2).

    TODO (real): submit the agent's signed blob; XRPL verifies the signature and applies
    the tx. Then execute the DEX swap (stablecoin -> target token) and tokenize the target
    fiat (e.g. tokenized MXN). Fund-safety loop: on swap failure, lock the funds in an
    XRPL Escrow (CancelAfter = retry window) and retry; if retry also fails, refund the
    sender — funds never get stuck mid-flow.
    """
    return {
        "id": "submit",
        "label": "Task 4 · Submit + convert",
        "status": "pass",
        "log": f'submit signed tx · DEX swap → tokenized {intent.get("target_currency","")} · (stub)',
        "payload": {"layer": "XRPL submit + DEX swap + tokenize · STUB",
                    "note": "TODO: submit signed blob, swap, tokenize; escrow retry/refund on failure"},
    }


def _task_offramp(intent: dict) -> dict:
    """Task 5 · Bank off-ramp — STUB.

    TODO (real): hand the tokenized target fiat to a LICENSED off-ramp partner that
    redeems the token and pays the recipient's overseas bank account (CLABE for Mexico).
    Mocked for the demo. Open items: who issues the tokenized MXN, and whether a refund
    returns the original stablecoin or the token.
    """
    return {
        "id": "offramp",
        "label": "Task 5 · Bank off-ramp",
        "status": "pass",
        "log": f'off-ramp → {intent.get("payee_clabe","CLABE")} · (mock) settled',
        "payload": {"layer": "Licensed off-ramp → bank (CLABE) · MOCK",
                    "note": "TODO: integrate a licensed off-ramp; pays MXN to the CLABE account"},
    }


def run_pipeline(intent: dict, unverified: bool = False,
                 client: JsonRpcClient | None = None) -> dict:
    """Run the full pipeline. Any failing step halts it; later steps are marked skipped."""
    client = client or JsonRpcClient(TESTNET_URL)
    tasks: list[dict] = []
    halted_at = None

    steps = [
        ("req", "Agent request", lambda: _task_req(intent)),
        ("pre", "Task 1 · Precheck", lambda: _task_pre(client, intent)),
        ("kya", "Task 2 · Trustline KYA", lambda: _task_kya(intent, unverified)),
        ("prepare", "Task 3 · Prepare unsigned tx", lambda: _task_prepare(intent)),
        ("sign", "Agent signs (non-custodial)", lambda: _task_sign(intent)),
        ("submit", "Task 4 · Submit + convert", lambda: _task_submit(intent)),
        ("offramp", "Task 5 · Bank off-ramp", lambda: _task_offramp(intent)),
    ]

    for step_id, label, step in steps:
        if halted_at is not None:
            tasks.append({"id": step_id, "label": label,
                          "status": "skipped", "log": "skipped · pipeline halted",
                          "payload": {"note": "skipped"}})
            continue
        result = step()
        tasks.append(result)
        if result["status"] == "fail":
            halted_at = result["id"]

    return {"ok": halted_at is None, "halted_at": halted_at, "tasks": tasks}
