# Sunshine × fx-agent integration

Sunshine's pipeline had **KYA / DEX / Settle as stubs**. They are now backed by the
**fx-agent** (a Node/xrpl.js settlement engine) over HTTP — running real transactions on
the XRPL Testnet.

```
sunshine.html ─POST /pay─▶ app.py ─▶ pipeline.py
                                       │ req   (mock x402)        — local
                                       │ pre   (precheck)         — local, real account_info
                                       │ kya ┐
                                       │ dex ┤─ POST /settle ─▶ fx-agent (Node) ─▶ XRPL Testnet
                                       │ settle ┘                  MINT→KYA→XRP/INR DEX→PAYOUT
```

- **KYA is taken as PASS.** Sunshine's `unverified` toggle drives a real on-chain
  **REVERT** instead (XRP returned to the sender), so the "deny" path is also real.
- **`payee_xrpl` from the intent is the payout destination** — the receiver bank's XRPL
  address. The agent sends the converted INR there (a redemption of the bank's IOU);
  the bank then does the fiat→IBAN off-ramp off-chain (not implemented).
- One `POST /settle` call returns per-stage results (KYA verdict, DEX convert tx,
  payout tx, or revert tx) which Sunshine splits into its KYA / DEX / Settle cards —
  each with a **Testnet explorer link**.

## fx-agent HTTP API
```
GET  /health   -> { status, bridge:"XRP", target:"INR", agent }
POST /settle   { amount, forcedKYA?, payeeXrpl? }
   forcedKYA ∈ PASS | HOLD | REVERT   (default PASS)
   payeeXrpl  = receiver bank's XRPL address (must be the INR issuer; else the
                payout realistically fails — no trust line for the token)
   -> { ok, status, mptIssuanceId,
        kya:{verdict,decision},
        convert:{bridge,received,hash,explorer} | null,
        settle:{paidTo,hash,explorer} | null,
        revert:{returnedTo,hash,explorer} | null,
        history }
```

## Run it (two processes)

**1. Start the fx-agent (Node) — the settlement engine**
```bash
cd fx-agent
npm install
npm run setup     # faucet-funds 5 Testnet accounts; paste seeds into fx-agent/.env
npm run seed      # builds the XRP/INR AMM + funds the agent
npm run serve     # HTTP API on http://localhost:8787
```

**2. Start Sunshine (Python) — the x402 front + pipeline**
```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python generate_wallet.py        # funds Alice (the payer) on Testnet
.venv/bin/uvicorn app:app --port 8000 --reload
# open http://localhost:8000
```
On Windows, set `PYTHONUTF8=1` before `generate_wallet.py` (it prints non-ASCII).
Point Sunshine at a non-default agent with `FX_AGENT_URL` (default `http://localhost:8787`).

## Demo input
```json
{ "payer_xrpl": "<Alice, from generate_wallet>",
  "payee_xrpl": "<the fx-agent's BANK address — from seed output / /settle log>",
  "amount": 50, "source_currency": "XRP", "target_currency": "INR" }
```
- `payee_xrpl` **must be the agent's bank** (the INR issuer) or the payout fails.
- Keep `amount` small (shallow AMM pool; the DEX guard rejects large price impact).
- `unverified` toggle → real on-chain REVERT.

## Notes
- **Testnet only.** Both sides hard-target Testnet; the fx-agent refuses mainnet endpoints.
- The fx-agent runs on its own seeded accounts (agent / bank / market-maker); Sunshine's
  precheck validates its own Alice wallet, then hands settlement to the agent.
- `target_currency` other than INR and `payee_iban` are **display-only** today.

See **[DOCUMENTATION.md](DOCUMENTATION.md)** for the full architecture and design rationale.
