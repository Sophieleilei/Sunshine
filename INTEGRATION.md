# Sunshine × fx-agent integration

Sunshine's pipeline steps are backed by the bundled **fx-agent** (Node/xrpl.js) over HTTP
— real XRPL Testnet transactions. The fx-agent **is the agent**: it holds its own key in
`.env` and signs locally. Sunshine (the orchestrator) is **non-custodial** — it only ever
sees an UNSIGNED tx (Trip 1) and the settlement result (Trip 2); the key never reaches it.

Corridor: **XRP → MXN** (bridge through native XRP), payout to the receiver bank, mocked
CLABE off-ramp.

## Two-trip, non-custodial flow

```
sunshine.html ─POST /pay─▶ app.py ─▶ pipeline.py
   req  (mock)         pre (real precheck)
   ─────────────────── Trip 1 (no money) ───────────────────
   kya + prepare  ──POST /prepare──▶ fx-agent: mint MPT, KYA, BUILD UNSIGNED tx
   ---- the agent signs the unsigned tx with its OWN key (inside /submit) ----
   ─────────────────── Trip 2 (money) ──────────────────────
   sign + submit  ──POST /submit──▶  fx-agent: sign + submit (DEX XRP→MXN) + pay bank
   offramp  (mock → CLABE)
```

- **`unverified` toggle** → `forcedKYA=REVERT`: a real on-chain return of XRP to the sender.
- The agent wallet is created **once** (`fx-agent/npm run setup` = onboarding); every call
  reuses it. No per-call wallet spawning.

## fx-agent HTTP API
```
GET  /                 dashboard (settlement flow + tx links)
GET  /api/settlements   JSON log of settlements
GET  /health
POST /prepare  {amount, forcedKYA?, payeeXrpl?}  -> mint+KYA+UNSIGNED tx (Trip 1)
POST /submit   {unsignedTx, context}             -> agent signs+submits + payout (Trip 2)
POST /settle   {amount, forcedKYA?, payeeXrpl?}  -> one-shot (used by the MCP/Claude path)
```
`payeeXrpl` = receiver bank's XRPL address (the MXN issuer); defaults to the agent's bank.

## Dashboard
`http://localhost:8787/` — every settlement's flow (Mint → KYA → Convert → Payout, or
Revert) with Testnet explorer links, auto-refreshing. Served by the HTTP server and/or the
MCP server; backed by `fx-agent/out/settlements.json`.

## Run it (two processes)
```bash
# 1) fx-agent (the settlement engine + dashboard)
cd fx-agent && npm install && npm run setup && npm run seed && npm run serve   # :8787
#    npm run setup prints 5 seeds for fx-agent/.env and the BANK (payee) address
#    npm run seed builds the XRP/MXN AMM

# 2) Sunshine (x402 front + pipeline)
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python generate_wallet.py        # funds Alice (the agent payer) on Testnet
.venv/bin/uvicorn app:app --port 8000       # open http://localhost:8000
```
On Windows set `PYTHONUTF8=1` before `generate_wallet.py`. Override the agent URL with
`FX_AGENT_URL` (default `http://localhost:8787`).

## AI / MCP path (optional)
The fx-agent also exposes an **MCP server** (`npm run mcp`) so Claude (XRPL AI Starter Kit)
can drive settlement from a PDF invoice. See `fx-agent/MCP_SETUP.md`. A sample invoice is
`fx-agent/invoice.pdf` (regenerate with `make_invoice.py`).

## Notes
- **Testnet only.** Both sides hard-target Testnet; the fx-agent refuses mainnet endpoints.
- Keep amounts small (shallow AMM pool); the DEX guard sizes off the live quote ± slippage.
- See **[DOCUMENTATION.md](DOCUMENTATION.md)** for the full architecture and rationale.
