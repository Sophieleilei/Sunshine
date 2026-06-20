# FX Trustworthy Agent — Implementation Plan

> **STATUS: LOCKED (2026-06-20).** All design decisions settled — funding, dest-token
> issuer, payout endpoint, KYA position, and Risks A/B/C resolved. Next step is the
> orchestrator state machine.


Assembling the locked flow on top of the **XRPL AI Starter Kit** (Wallet skill +
Payments skill). The starter kit gives us the signing ceremony and basic XRP
payments; everything below is what *we* add on top.

---

## 0. What the starter kit gives us vs. what we build

| Layer | Source | Notes |
|---|---|---|
| Wallet / signing ceremony (autofill → preview → confirm → sign → submit) | **Starter kit (Wallet skill)** | Use scoped, time-limited auto-sign for autonomous steps; human-confirm the final payout |
| Basic XRP & token payments | **Starter kit (Payments skill)** | Transaction construction knowledge |
| MPT mint + lifecycle | **We build** | `MPTokenIssuanceCreate`, `MPTokenAuthorize` |
| Trust lines (RLUSD + dest token) | **We build** | `TrustSet` |
| DEX cross-currency conversion | **We build** | cross-currency `Payment` w/ pathfinding, or `OfferCreate` |
| Conditional token escrow (HOLD) | **We build** | `EscrowCreate` / `EscrowFinish` / `EscrowCancel` |
| KYA gate (PASS/HOLD/REJECT) | **We build (assumed oracle)** | off-ledger decision → drives branch |
| Orchestrator (state machine) | **We build** | ties all steps + reacts to KYA |

---

## 1. Step → XRPL transaction mapping

### Step 1 — Invoice issued (off-chain)
No ledger transaction. Agent ingests invoice payload (sender Alice, receiver XYZ,
amount, currency, due date). Store off-ledger; hash it for step 2 metadata.

### Step 2 — Mint invoice as MPT
- `MPTokenIssuanceCreate` — agent (or issuer account) creates the MPT issuance.
- Set issuance **flags** we will need downstream:
  - `tfMPTCanTransfer` — so it can move between accounts
  - `tfMPTCanEscrow` — so it is escrow-eligible (HOLD path)
  - `tfMPTCanTrade` — if the MPT itself ever touches the DEX
- Put the **invoice hash + reference data** in `MPTokenMetadata` (immutable — see Risk A).
- `MPTokenAuthorize` — any holding account opts in to hold the MPT.

### Step 3 — Acquire RLUSD (stable leg)
- `TrustSet` — agent sets a trust line to the **RLUSD Testnet issuer**.
- Claim **testnet RLUSD from tryrlusd.com** (the RLUSD testnet faucet) to the agent's
  address. RLUSD comes from the faucet; the "claw credit" + dest token are
  agent-issued.

### Step 4 — Convert RLUSD → receiver currency via DEX
- `TrustSet` — trust line to the **destination-currency issued token**.
- Cross-currency `Payment` with `SendMax` (RLUSD) + `Amount` (dest token) and
  **pathfinding** — atomic conversion through the native DEX/AMM.
  - Alternative: `OfferCreate` if you want explicit limit-order control instead of
    a market take.

### Step 5 — Updated MPT held by agent
The converted value sits with the agent. The MPT is the **invoice record**; record
the converted amount + FX rate as a **state update** (see Risk A — MPT metadata is
immutable, so this is a Memo/companion record, not a metadata edit).

### Step 6 — KYA decision (PASS / HOLD / REJECT)
**KYA = Know Your Agent.** It is the gate the **bank** applies to the **agent**
before accepting the converted token — it sits **between the agent (holding the
converted dest token) and the receiver's bank**. The agent cannot pay the bank
(Step 8) until the bank's KYA clears it. Off-ledger gate (assumed). Output drives
the branch:
- **PASS** → Step 8 (agent pays the bank's XRPL address).
- **HOLD** → Step 7 (escrow) — typically while the bank's KYA is still running.
- **REJECT** → terminate; refund/return path (no payout to the bank).

### Step 7 — Conditional escrow (HOLD path)
- `EscrowCreate` — lock the converted funds (token escrow) with:
  - `Condition` = crypto-condition (PREIMAGE-SHA-256). The **fulfillment** is
    released only when KYA returns PASS.
  - `FinishAfter` / `CancelAfter` timeouts as a safety net.
- On KYA PASS → `EscrowFinish` with the fulfillment → funds released.
- On KYA timeout/REJECT → `EscrowCancel` → funds returned.

### Step 8 — Payout to the receiver's BANK address (not XYZ directly)
- The agent holds the converted **dest-currency token** (bank-issued INR). It does
  **not** pay XYZ's address — XYZ has no XRPL address.
- After KYA **PASS**, the agent sends a `Payment` of the dest token to the
  **receiver's bank's XRPL address** — since the bank issued it, this is a
  **redemption** of the bank's own IOU.
- The **bank** then credits XYZ off-chain (the off-ramp / final delivery to XYZ
  happens inside the bank, outside the ledger).
- **Human-confirm this step** (highest-value, irreversible).
- On-ledger endpoint = bank address. XYZ stays fully off-chain end to end.

### Step 9 — Settle / close
Mark invoice settled off-ledger; optionally `MPTokenIssuanceDestroy` or keep MPT as
the immutable audit record. Emit settlement summary.

---

## 2. Build phases

**Phase A — Foundation**
- Stand up starter kit (Wallet + Payments skills), testnet wallets, faucet funding.
- Confirm signing ceremony + scoped auto-sign work end to end with a plain XRP payment.

**Phase B — Asset rails**
- MPT module: issuance create/authorize + flags. (Step 2)
- Trust-line module: RLUSD + dest token. (Steps 3–4)

**Phase C — Conversion**
- DEX module: cross-currency payment w/ pathfinding; slippage/min-receive guard.
  (Step 4)

**Phase D — Escrow + gate**
- KYA gate adapter (mock returning PASS/HOLD/REJECT). (Step 6)
- Conditional token-escrow module: create / finish / cancel + condition handling.
  (Step 7)

**Phase E — Orchestrator**
- State machine: `ISSUED → MINTED → CONVERTED → KYA → {PAID | ESCROWED → PAID | REJECTED}`.
- Wire scoped auto-sign for autonomous steps; human-confirm payout.

**Phase F — Hardening**
- Idempotency (don't double-mint / double-pay on retry).
- Failure recovery for each tx type; escrow timeout reconciliation.
- Audit log keyed to the MPT.

---

## 3. Risks / decisions on XRPL

- **Risk A — MPT metadata is immutable. → DECIDED (Memos).** The MPT is the
  **immutable invoice anchor**. All mutable state — FX rate, converted amount,
  status (`MINTED/CONVERTED/ESCROWED/PAID/REJECTED`), KYA verdict, escrow ref — is
  carried in payment **Memos** plus an off-ledger record keyed to the MPT issuance
  ID. No in-place MPT edits; no Dynamic NFT companion.

- **Risk B — Token escrow. → SCOPED (Testnet/Devnet only).** This project runs
  **only on Testnet/Devnet**, never mainnet. Action: confirm the **Token Escrow
  amendment** is enabled on the chosen dev network before building the HOLD path; if
  it isn't active there, fall back to escrowing XRP (or demo the HOLD path on
  whichever of Testnet/Devnet has it enabled).

- **Risk C — DEX liquidity / pathfinding. → DECIDED (guarded conversion).** Add to
  the DEX module (Step 4 / Phase C):
  - **Min-receive / max-slippage guard:** set `Amount` (dest) as the floor and
    `SendMax` (RLUSD) as the ceiling on the cross-currency `Payment` so the swap
    either lands within bounds or fails — no unbounded fills.
  - **`tfPartialPayment` OFF** for the conversion so a thin book can't deliver less
    than `Amount`; the payment fails cleanly instead of underdelivering.
  - **Pre-trade path check:** quote via `path_find` / `ripple_path_find` before
    submitting; abort if no path meets the guard rate.
  - **Slippage tolerance** as a config knob (e.g. max % off the quoted rate), with
    retry/back-off on `tecPATH_PARTIAL` / `tecPATH_DRY`.
  - On dev networks liquidity may be thin — seed a test AMM/order book for the
    RLUSD→dest pair so the path exists.

---

## 4. Decisions & remaining open question

1. **Funding model → LOCKED (Clawback-enabled issued credit).** The agent is funded
   the way the XRPL AI Starter Kit funds its account, as **Clawback-enabled issued
   credit** ("claw credit") on the dev network — not Alice pre-funding or an external
   treasury. That credit is the source the agent uses to acquire RLUSD in Step 3.
   Because the agent is also the **issuer** of this credit and the dest token, set the
   issuer Clawback flags — `tfMPTCanClawback` on the MPT and Clawback on the issued
   token — so the agent can claw funds back (e.g. on REJECT or error recovery).

3. **Dest-currency token issuer → REVISED 2026-06-20 (bank/gateway issues it, NOT the
   agent).** A live Testnet run exposed a contradiction: you cannot "convert RLUSD →
   INR on the DEX" into a token the agent issues itself — issuing your own token isn't
   a DEX trade. For **real institutions** the INR-pegged token must come from a
   **licensed issuer** (the receiving bank or an Indian gateway) holding rupee
   reserves; the agent stays a non-custodial router. Therefore:
   - The **bank/gateway issues** the INR token and runs its market.
   - The **agent** sets a trust line to that issuer and **buys INR on the DEX with
     RLUSD** — a genuine FX conversion (Step 4).
   - Payout (Step 8) is a **redemption**: agent sends the bank's own INR IOU back to
     the bank, which credits XYZ off-chain.
   - The agent remains issuer of the **funding "claw credit"** only — not the dest
     token. (Demo: the BANK Testnet account plays the issuer role.)
   - Trade-off: needs **seeded RLUSD/INR liquidity** on Testnet (Risk C) for the swap
     to find a path.

2. **Payout endpoint → DECIDED (pay the bank, not XYZ).** The agent holds the
   converted dest token and, after KYA PASS, pays it to the **receiver's bank's XRPL
   address**. The bank credits XYZ off-chain. XYZ never has an XRPL address and stays
   fully off-chain. The only non-XRPL hop is inside the bank (token → XYZ's account),
   which is out of scope.
