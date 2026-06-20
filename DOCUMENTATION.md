# How it works — Sunshine × fx-agent

An autonomous cross-border invoice settlement system on the XRP Ledger (Testnet). A
payer's agent submits a payment intent over an x402-style HTTP endpoint; the system
screens the agent, converts the value on the native XRPL DEX, and settles to the
receiver's bank — all as real on-ledger transactions, with the sender and recipient
staying off-chain.

---

## 1. The two services

| Service | Stack | Role | Port |
|---|---|---|---|
| **Sunshine** | Python · FastAPI | x402 front-end + 5-step pipeline + Alice precheck | 8000 |
| **fx-agent** | Node · xrpl.js | the settlement engine (MINT → KYA → DEX → PAYOUT/REVERT) | 8787 |

Sunshine owns the **request handling and the local precheck**; the fx-agent owns the
**real XRPL settlement**. They talk over one HTTP call.

```
Browser ─POST /pay─▶ Sunshine (8000) ─POST /settle─▶ fx-agent (8787) ─▶ XRPL Testnet
```

---

## 2. Actors (on-ledger Testnet accounts)

| Actor | On-chain? | Role |
|---|---|---|
| **Alice** (payer) | ✅ | Sender. Funded with XRP; her account is precheck-validated. |
| **fx-agent** | ✅ | Autonomous operator: mints the invoice, screens, converts, pays. |
| **Market maker (MM)** | ✅ | Seeds the **XRP/INR AMM** — the "Bitso/B2C2" stand-in. |
| **Bank** | ✅ | Issues the **INR** token; receives the payout (redemption). |
| **Bob** (recipient) | ❌ off-chain | Gets fiat from the bank via IBAN (off-ramp, not implemented). |

The only on-ledger parties in a settlement are the **agent** and the **bank**. Alice is
validated but her value is bridged through the agent; Bob is entirely off-chain.

---

## 3. End-to-end flow

### The Sunshine pipeline (5 steps)
Each step returns `{id, label, status, log, payload}`; any `fail` halts the rest.

| Step | Where | What |
|---|---|---|
| `req` | local | Mock x402: receive Alice's intent, "402 Payment Required". |
| `pre` | local, **real** | `account_info` — is Alice activated + does she have enough XRP? |
| `kya` | **fx-agent** | Screen the agent (PASS/ALLOW). `unverified` → REVERT/DENY. |
| `dex` | **fx-agent** | Convert XRP → INR on the XRPL AMM (real tx). |
| `settle` | **fx-agent** | Pay the bank = redeem the bank's INR IOU (real tx). |

Steps 3–5 are produced by **one** `POST /settle` call to the fx-agent, whose response is
split into the three cards.

### The fx-agent lifecycle (screen-first, escrow-free)
```
ISSUED → MINTED → KYA ┌─ PASS / HOLD→cleared → CONVERT (XRP→INR) → PAYOUT → PAID
                      └─ REVERT (or HOLD declined) → return XRP to Alice → REVERTED
```

1. **MINT** — the invoice is minted as an **MPT** (Multi-Purpose Token) — an immutable
   on-ledger anchor. Mutable state (status, FX rate, KYA verdict) rides in Memos.
2. **KYA** — the bank's "Know Your Agent" gate runs **before** any conversion, while the
   agent still holds plain XRP. PASS → proceed; HOLD → wait (funds stay in wallet);
   REVERT → return the XRP to Alice (no conversion ever happened).
3. **CONVERT** — guarded cross-currency `Payment`: XRP in (`SendMax`), INR out (`Amount`
   floor), `tfPartialPayment` OFF, with a pre-trade `ripple_path_find` quote. Matched
   against the MM's XRP/INR AMM.
4. **PAYOUT** — `Payment` of the INR token to the **receiver bank's XRPL address**
   (`payee_xrpl`). Because the bank issued the token, this is a **redemption**.
5. The bank then pushes fiat to Bob's IBAN **off-chain** (out of scope).

---

## 4. Key design decisions (and why)

- **Bridge = native XRP.** XRP is the canonical XRPL cross-currency bridge (Ripple ODL
  bridges through XRP). No issuer, no trust line, no faucet — every account already holds
  XRP. We previously used RLUSD/a stablecoin, but real testnet RLUSD requires a wallet
  faucet (Xaman) that kept mis-submitting to mainnet. XRP removes all of that.
  *(RLUSD/EURC stays a one-line config swap for a stable leg.)*
- **Invoice = MPT.** The invoice is a unique, auditable record → an MPT anchor. MPT
  metadata is immutable, so mutable state lives in payment Memos.
- **Screen before convert.** Banks pre-screen before executing FX. KYA runs first; the
  XRP sits in the agent's wallet until cleared, so a failed deal never converted.
- **No escrow.** Holding-until-KYA gives the same "funds don't move early" guarantee
  without escrow — and RLUSD can't be escrowed anyway (its issuer leaves trustline
  locking off, on both testnet and mainnet). XLS-85 token escrow is live but per-issuer.
- **REVERT returns the bridge asset to the sender.** Realistic: a rejected cross-border
  payment is returned to the sender in their own asset, not the destination currency.
- **Market maker is a real, self-run AMM.** Not a mock — the MM account genuinely holds
  XRP + INR and posts an `AMMCreate` pool; the agent's swap really executes against it.
  On mainnet you'd trade against real makers (Bitso/B2C2); here we play that role.
- **Payee = the receiver bank's XRPL address.** The agent pays *that* address. It must be
  the INR issuer (the bank); an address without an INR trust line cannot receive the
  token — which is itself the realistic constraint.

---

## 5. Repository layout

```
Sunshine-main/
├── app.py                 FastAPI: GET / , POST /pay , /health , /alice
├── pipeline.py            5-step pipeline; kya/dex/settle → fx-agent over HTTP
├── account_utils.py       XRPL read-only guards (activation, balance)
├── sunshine.html          front-end (drives /pay, renders step cards + audit log)
├── generate_wallet.py     create + faucet-fund Alice (writes demo_wallets.json)
├── requirements.txt       fastapi, uvicorn, xrpl-py, requests
├── INTEGRATION.md         how the two services are wired + run steps
├── DOCUMENTATION.md       this file
└── fx-agent/              the settlement engine (Node · xrpl.js)
    ├── src/
    │   ├── server.js          HTTP API: GET /health , POST /settle
    │   ├── orchestrator.js    the state machine (MINT→KYA→CONVERT→PAYOUT/REVERT)
    │   ├── config.js          bridge=XRP, target=INR, mainnet kill-switch
    │   ├── state.js           settlement record + transitions
    │   ├── modules/
    │   │   ├── mpt.js          mint invoice as MPT
    │   │   ├── kya.js          KYA gate (mock oracle: PASS/HOLD/REVERT)
    │   │   ├── dex.js          guarded XRP→INR conversion (ripple_path_find + guards)
    │   │   ├── payout.js       pay the bank (redemption)
    │   │   ├── revert.js       return XRP to the sender
    │   │   └── trustline.js    TrustSet helper
    │   ├── scripts/
    │   │   ├── setup.js        faucet-fund 5 accounts
    │   │   └── seed.js         issuer flags + trust lines + INR issuance + XRP/INR AMM
    │   └── util/               log, hex/memo, explorer links, balance snapshots
    ├── package.json           scripts: setup, seed, serve, demo, demo:hold, demo:revert
    └── README.md / PLAN*.md    design history + decisions
```

---

## 6. Running it

See **[INTEGRATION.md](INTEGRATION.md)** for the exact commands. In short:

```bash
# Terminal 1 — settlement engine
cd fx-agent && npm install && npm run setup && npm run seed && npm run serve

# Terminal 2 — x402 front + pipeline
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python generate_wallet.py
.venv/bin/uvicorn app:app --port 8000
# open http://localhost:8000  → fill the intent → press the button
```

`npm run setup` prints 5 seeds for `fx-agent/.env`; `npm run seed` prints the **bank
address** to use as `payee_xrpl`. The fx-agent can also be exercised directly:

```bash
curl -X POST localhost:8787/settle \
  -H 'content-type: application/json' \
  -d '{"amount":50,"forcedKYA":"PASS","payeeXrpl":"<bank address>"}'
```

---

## 7. What's real vs. mock / display-only

| Real on-chain (Testnet) | Mock / display-only |
|---|---|
| Alice precheck (`account_info`) | x402 `req` step (mocked 402) |
| Invoice MPT mint | KYA decision logic (oracle stub: always PASS / REVERT) |
| XRP→INR DEX swap (AMM) | `target_currency` other than INR (label only) |
| Payout to bank (redemption) | `payee_iban` + the fiat off-ramp to Bob |
| REVERT (XRP back to Alice) | |
| Explorer links per tx | |

---

## 8. Limitations & roadmap

- **Single corridor / currency** — XRP→INR only. Multi-currency = swap the bridge
  (USD→RLUSD, EUR→EURC) + a dest token per corridor.
- **KYA is a stub oracle** — productionize as on-chain **credentials + permissioned DEX**
  (XLS-70 / PermissionedDEX, enabled on Testnet) or `DepositPreauth` so the verdict is
  ledger-enforced authorization.
- **No fiat off-ramp** — the bank→Bob IBAN leg is out of scope (the bank's job).
- **Shallow AMM** — the demo pool is small; large swaps hit the slippage guard. Real
  corridors have deep market-maker liquidity.
- **Stateless HTTP** — each `/settle` runs a fresh settlement; no persistence/idempotency
  store yet.

> **Testnet only.** All accounts are throwaway faucet wallets; the fx-agent refuses
> mainnet endpoints. No real funds are ever involved.
