# Flow v3 — Screen-first (KYA + escrow BEFORE conversion)

Locked 2026-06-20. KYA gate runs before conversion; HOLD escrows the bridge currency
(RLUSD); conversion happens only on a cleared deal. REVERT returns RLUSD to Alice.

## State machine

```
ISSUED → MINTED → KYA ┌─ PASS   → CONVERT → PAYOUT            → PAID
                      ├─ HOLD   → ESCROW(RLUSD) ─clears─→ CONVERT → PAYOUT → PAID
                      │                         └─timeout─→ REVERT
                      └─ REVERT → return RLUSD to Alice     → REVERTED
```

## Steps

1. **MINT** — invoice → MPT (immutable anchor; state in Memos). Agent already holds
   RLUSD (funded by Alice).
2. **KYA** — bank screens the agent **while it still holds RLUSD** (pre-conversion).
   Verdict: PASS / HOLD / REVERT.
   - (recommended enforcement) on PASS the bank issues `DepositPreauth(agent)` and runs
     `DepositAuth`, so the later payout is ledger-authorized and not re-screened.
3a. **PASS → CONVERT** — guarded DEX swap RLUSD → INR (only now).
3b. **PASS → PAYOUT** — `Payment` INR → bank (redemption).
4.  **HOLD → ESCROW(RLUSD)** — lock the **RLUSD** in a conditional escrow while the
    bank finishes screening.
    - clears (PASS) → `EscrowFinish` → CONVERT → PAYOUT → PAID.
    - timeout/decline → `EscrowCancel` → RLUSD back to agent → REVERT.
5.  **REVERT** — `Payment` RLUSD → Alice's wallet. (She already trusts RLUSD; no INR
    trust line, no FX unwind, no loss.) → REVERTED.

## Why this order
- Don't execute FX on a deal that isn't cleared.
- HOLD escrows the bridge currency, so a stuck deal is refundable to the sender as-is.
- REVERT is a plain RLUSD return — realistic (sender gets their own currency back).

## What changes in code (vs current convert→KYA build)
- `orchestrator.js` — **move CONVERT to after KYA PASS / after escrow clears**; KYA runs
  right after MINT.
- `modules/escrow.js` — escrow **RLUSD** amount (stable), not INR. (Bank no longer needs
  AllowTrustLineLocking for INR; the **stable issuer** must allow locking instead — or
  use XRP-equivalent path. Verify on Testnet.)
- `modules/revert.js` (new) — `returnToSender(agent,{ rlusdAmount, aliceAddress })`:
  one `Payment` of RLUSD to Alice.
- `modules/kya.js` — verdicts PASS/HOLD/REVERT; (optional) bank `DepositPreauth` on PASS.
- `state.js` — REVERTED state.
- `index.js`/`package.json` — `--kya=REVERT`, `demo:revert`.

## Note on escrow + Token Escrow amendment
Escrowing RLUSD (an issued token) still needs the **stable issuer** to permit trustline
locking (`asfAllowTrustLineLocking`) for token escrow. On the self-issued stand-in we
control that; with real RLUSD we can't set flags on Ripple's issuer — so the HOLD/escrow
demo may need the stand-in stablecoin even if PASS/REVERT use real RLUSD. Flag to verify.

## Open / separate
- Clawback (claw credit) reserved for **post-settlement** recovery only — not used in the
  pre-payout REVERT.
- XLS-82 (MPT-on-DEX) check still pending — only relevant if INR becomes an MPT.
```
