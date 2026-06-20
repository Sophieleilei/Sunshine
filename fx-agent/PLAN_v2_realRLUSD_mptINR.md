# Plan v2 — Real RLUSD + INR as an MPT (skeleton)

Two changes requested:
1. Use **real testnet RLUSD** (from tryrlusd.com): 5 RLUSD → Alice, 5 RLUSD → MM.
2. Make **INR an MPT** (not an IOU trustline token) — "real, not mock".

---

## ⚠️ Gating risk (decide FIRST): the MPT-on-DEX amendment

Making INR an MPT *and* swapping it on the AMM needs **XLS-82 (MPT DEX integration)** —
which adds IOU/MPT and MPT/MPT AMM pairs. Base MPT (XLS-33) does NOT allow DEX/AMM
trading; **XLS-82 does**.

**Action 0:** verify XLS-82 is **enabled on the target network**.
- If enabled on **Testnet (altnet)** → proceed there.
- If only on a **Devnet** → point `XRPL_ENDPOINT` at that devnet (and re-faucet there;
  note: real RLUSD faucet may not exist on that devnet — see conflict below).
- If enabled **nowhere we can use** → INR stays an **IOU** (keep current working demo);
  MPT is used only for the invoice. (Fallback.)

**Conflict to resolve:** real RLUSD (tryrlusd.com) is a **Testnet** asset. XLS-82 may
only be on a **Devnet**. We may not be able to have *both* real RLUSD *and* MPT-INR on
the same network. Possible outcomes:
- (a) Testnet has XLS-82 → both work. ✅ best case.
- (b) Only Devnet has XLS-82 → MPT-INR works there, but RLUSD must be a **self-issued
  stand-in** again (no real RLUSD faucet on that devnet).
- (c) Neither → keep IOU-INR + real RLUSD on Testnet.

---

## Part A — Real RLUSD (5 + 5)

**Manual (you, in browser):** sign in to tryrlusd.com with GitHub, claim RLUSD.
- Faucet gives **10 RLUSD / 24h**. Plan: **claim 10 to Alice**, then Alice sends **5 to
  MM** on-ledger (one claim, split 5/5). (Or two daily claims if you prefer.)

**Code changes:**
- `.env`: `STABLE_CURRENCY=524C555344...(40-hex)`, `STABLE_ISSUER=<real RLUSD testnet issuer>`.
- `seed.js`: **remove** the "issue USD stablecoin" step (no longer self-issued); instead
  assume RLUSD already in Alice + MM from the faucet. Keep: trust lines to RLUSD issuer
  for Alice/agent/MM.
- Alice funds the agent with a small RLUSD amount per invoice.

**⚠️ Liquidity caveat:** 5 RLUSD is a *very shallow* pool (5 RLUSD + ~415 INR). Any
non-tiny swap moves the price hugely → big slippage. So:
- shrink invoices to **tens of INR** (e.g. 50 INR ≈ 0.6 RLUSD), and
- widen `MAX_SLIPPAGE` (e.g. 0.1–0.2), or
- put **all 10 RLUSD into the MM pool** and fund the agent from Alice's share.
This is the price of using real (rate-limited) RLUSD.

---

## Part B — INR as an MPT

**Bank issues INR as an MPT** (instead of an IOU):
- `MPTokenIssuanceCreate` by BANK, flags: `CanTransfer | CanEscrow | CanTrade`
  (CanTrade is required for the AMM/DEX leg under XLS-82).
- `MPTokenAuthorize` by MM and Agent (opt-in to hold the INR MPT).

**AMM pair becomes RLUSD (IOU) / INR (MPT):**
- `AMMCreate` with `Amount = RLUSD (IOU)`, `Amount2 = INR (MPT amount)`. (IOU/MPT pair,
  allowed by XLS-82.)

**Conversion (Step 4):** unchanged in spirit — guarded cross-currency `Payment`
RLUSD→INR-MPT, matched against the AMM. `Amount` = INR MPT (floor), `SendMax` = RLUSD.

**Escrow (HOLD):** `EscrowCreate` with an **MPT amount** (MPT token escrow). Bank still
sets `asfAllowTrustLineLocking`/MPT-equivalent issuer permission.

**Payout (Step 8):** `Payment` of the INR **MPT** to the bank = redemption.

**Module impact:**
- `mpt.js` — add a reusable "issue currency MPT" + authorize helper (separate from the
  invoice MPT).
- `dex.js` — amounts already generic; MPT amount format is `{ mpt_issuance_id, value }`.
- `escrow.js` / `payout.js` — pass MPT amount objects.
- `balances.js` — read MPT balances (`account_objects` / `mpt_holders`) not just
  trust lines.

---

## What stays the same
- 5-actor model, orchestrator state machine, KYA branches, explorer-link proof.
- Invoice is still its own MPT.
- Mainnet kill-switch.

## Recommendation
1. **First run Action 0** (check XLS-82 availability) — it decides everything.
2. If Testnet has XLS-82 → do Part A + Part B together (best demo: real RLUSD + MPT INR).
3. If not → either MPT-INR on devnet with stand-in stable (b), or real-RLUSD + IOU-INR
   on Testnet (c). Pick based on which story matters more to the judges:
   **real RLUSD** vs **everything-MPT**.
