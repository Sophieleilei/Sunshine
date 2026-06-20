# Sunshine

**Non-custodial, compliance-gated agent cross-border payment orchestration.**

An AI agent initiates an XRPL stablecoin payment; Sunshine runs compliance review, prepares
the transaction and finds a conversion path — but **never holds the agent's private key** —
and finally off-ramps tokenized fiat to the recipient's overseas bank account.

### Scenario

Agent **Alice** holds an XRPL stablecoin and wants to pay a recipient in **Mexico** who wants
**MXN**, landing in a bank account (**CLABE**). Sunshine turns "stablecoin in the agent's hands"
into "pesos in the recipient's bank account" — safely and compliantly.

## Architecture — non-custodial two-trip signing

The agent's signature splits the flow into two trips; the private key never leaves the agent.

```
Trip 1 (before signature, no money moves)
  req      Agent request — receive the payment intent
  pre      Task 1 · Precheck — activation + balance                 [REAL]
  kya      Task 2 · Trustline KYA — issuer-authorized trustline      [TODO]
  prepare  Task 3 · Prepare unsigned tx — DEX pathfind + build       [TODO]
        │
        ▼  agent signs the unsigned tx LOCALLY with its own key  (sign)
        │
Trip 2 (after signature, money moves)
  submit   Task 4 · Submit + convert — submit signed tx, DEX swap, tokenize   [TODO]
  offramp  Task 5 · Bank off-ramp — licensed off-ramp pays MXN to CLABE        [TODO]
```

Sunshine only ever touches an **unsigned-JSON tx** and a **signed blob** — neither contains
the private key. Ownership is enforced by XRPL signature verification: a request spoofing
someone else's address cannot produce a valid signature.

### Compliance gate — Trustline KYA (not DID/VC, not x402)

- No x402 handshake. No DID / Verifiable Credentials.
- Sunshine is the stablecoin **issuer** and sets `RequireAuth`, so it only **authorizes a
  trustline** for agents that pass review. The presence of that issuer-authorized trustline
  *is* the compliance signal — an on-chain, pre-settlement gate that runs **before money moves**.

### Fund-safety loop

Funds always have a home: DEX swap succeeds → off-ramp; swap fails → lock in an **XRPL Escrow**
(`CancelAfter` = retry window) and retry; retry succeeds → off-ramp; retry fails → refund the
sender. Nothing gets stuck mid-flow.

### Differentiation (vs. t54)

1. **Non-custodial** — never holds user keys; every transfer is user-signed, ownership enforced at the XRPL protocol layer.
2. **On-chain pre-settlement compliance** — trustline-based KYA completes before money moves (vs. t54's off-chain underwriting + post-hoc chargeback).
3. **Fund-safety loop** — escrow retry/refund on conversion failure; funds never lost.

## What's real vs. TODO

Only **Task 1 · Precheck** hits the live XRPL testnet today (`account_utils.py`). Tasks 2–5 are
clearly-marked stubs in `pipeline.py`, each with a comment describing its real job. The
**signing function itself is proven** in `sign_demo.py`.

Three real interfaces are still mocked: the licensed bank off-ramp (Task 5), the tokenized-MXN
issuer, and whether a refund returns the original stablecoin or the token.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Generate + activate a fixed-seed testnet wallet (writes demo_wallets.json)
.venv/bin/python generate_wallet.py

# Run the app
.venv/bin/uvicorn app:app --port 8000 --reload
# open http://localhost:8000
```

`demo_wallets.json` holds a wallet **seed (private key)** and is gitignored — it is created
locally by `generate_wallet.py`. See `demo_wallets.example.json` for the shape.

## Files

- `account_utils.py` — `is_account_active`, `require_active`, `require_sufficient_balance` (XRPL read-only guards)
- `pipeline.py` — pipeline orchestration (Precheck real; KYA / prepare / submit / off-ramp stubbed)
- `app.py` — FastAPI: `GET /`, `POST /pay`, `/alice`, `/health`
- `sunshine.html` — frontend: live task dashboard with the signing step, driven by the real backend
- `sign_demo.py` — proof that local agent signing works (no funds moved)
- `generate_wallet.py` — make + activate a fixed-seed testnet wallet
- `transfer_demo.py` — demo of a two-account transfer on testnet
- `test_pipeline.py` — pipeline pass / insufficient-balance / KYA-deny checks

> Testnet only. The seeds in demo scripts are throwaway test wallets — never reuse them on mainnet.
