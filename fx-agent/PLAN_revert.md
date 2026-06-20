# REVERT skeleton (return the CONVERTED token to the sender)

## Definition (chosen)
On KYA failure, **REVERT = send the already-converted INR token back to Alice's
wallet.** No swap back to RLUSD, no DEX unwind. Alice simply receives the converted
token; what she does with it afterwards is her call.

Rename everywhere: `KYA.REJECT → KYA.REVERT`, state `REJECTED → REVERTED`,
`demo:reject → demo:revert`.

## Revert flow (skeleton)

```
KYA = REVERT   (or a HOLD that timed out)
   │
   ├─ (HOLD-timeout only) EscrowCancel ──► INR returns to agent
   │
   ▼
1. RETURN   send INR token ──► ALICE's wallet      [Payment to config.addr.alice]
   │
   ▼
2. CLOSE    mark invoice MPT REVERTED (Memo) ; optional clawback/destroy MPT
   │
   ▼
state → REVERTED
```

## Prerequisite (the one new thing)
Alice must be able to **hold the INR token**, so she needs a **trust line to the bank's
INR issuer**. Add `TrustSet (Alice → INR)` in the seed step. (Without it the return
Payment fails with `tecNO_LINE`/`tecPATH_DRY`.)

## Key points
- **No FX loss** — it's a straight token transfer, so the full converted amount goes
  back. (Contrast with the unwind approach, which cost 2× AMM spread.)
- **What Alice ends up with:** INR (the converted token), not her original RLUSD. This
  is the explicit choice — "revert the converted token to the sender."
- **Two triggers, one routine:**
  1. KYA verdict = REVERT (direct).
  2. HOLD path that never clears → `EscrowCancel` returns INR to agent → same return.
- **Amount:** return exactly this invoice's `settlement.convertedAmount` (the INR), not
  the agent's whole balance.

## Module/code impact
- `state.js` — `REJECTED → REVERTED`.
- `modules/kya.js` — `KYA.REJECT → KYA.REVERT`.
- `modules/revert.js` (new) — `returnToSender(agent, { amount, aliceAddress })`:
  one guarded `Payment` of the INR token to Alice.
- `orchestrator.js` — REVERT branch + HOLD-timeout branch both call `returnToSender`.
- `scripts/seed.js` — add Alice's trust line to the INR issuer.
- `index.js` / `package.json` — `--kya=REVERT`, `demo:revert`.
- balances snapshot includes ALICE so the return is visible.

## Demo proof
Before/after: **agent INR → 0**, **Alice INR up by the invoice amount**, bank unchanged.
Explorer link for the return Payment (and the EscrowCancel on the HOLD-timeout variant).
```
