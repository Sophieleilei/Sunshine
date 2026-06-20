# Sunshine

x402 → XRPL payment pipeline demo. An agent (**Alice**) submits a payment intent to a
(mock) x402 endpoint; the backend runs a 5-step pipeline against the **XRPL Testnet**.

```
sunshine.html ──POST /pay──▶ FastAPI (app.py) ──▶ pipeline.py ──account_info──▶ XRPL Testnet
```

## Pipeline

| Step | Status | What it does |
|------|--------|--------------|
| `req` · Agent request | mock | Receive Alice's intent via x402, return HTTP 402 |
| `pre` · Precheck | **REAL** | Check payer is activated + has sufficient XRP balance (fail-fast) |
| `kya` · KYA gate | stub | Verify agent credential (XLS-70) — TODO |
| `dex` · DEX convert | stub | RLUSD → target token via pathfinding — TODO |
| `settle` · Settle | stub | Pay the recipient wallet — TODO |

Only **Precheck** is wired to the live ledger today; the other three are clearly-marked
stubs in `pipeline.py` with a defined interface to fill in later.

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
- `pipeline.py` — pipeline orchestration (Precheck real, rest stubbed)
- `app.py` — FastAPI: `GET /`, `POST /pay`, `/alice`, `/health`
- `sunshine.html` — frontend: drives the real backend, live replay, audit log
- `generate_wallet.py` — make + activate a fixed-seed testnet wallet
- `transfer_demo.py` — demo of a two-account transfer on testnet
- `test_pipeline.py` — pipeline pass / insufficient-balance / unverified checks

> Testnet only. The seeds in demo scripts are throwaway test wallets — never reuse them on mainnet.
