# FX Agent — Workflow Skeleton (hackathon / Testnet)

## Actors & accounts (all XRPL Testnet)

| Actor | On-chain? | Account holds | Role |
|---|---|---|---|
| **Alice** (sender) | ✅ has a wallet | **stablecoin** (e.g. RLUSD) the agent may spend | issues invoice, funds the value |
| **FX Agent** | ✅ | operates on Alice's behalf; holds value mid-flow | autonomous orchestrator |
| **Market Maker (MM)** | ✅ (we create it) | **RLUSD + target-currency token** | posts AMM liquidity; the DEX swaps against it |
| **Bank** (Bob's bank) | ✅ | issues the **target-currency token**; redeems it | on-chain endpoint + off-ramp to fiat |
| **Bob** (receiver) | ❌ off-chain | a normal bank account | gets **fiat** from the bank |

## Assets

- **Stablecoin** = bridge value (RLUSD = USD; EURC for EU sender, etc.)
- **Target token** = bank/gateway-issued (e.g. INR.bank) — a *claim*, not fiat
- **Invoice MPT** = immutable on-ledger invoice record (state in Memos)

---

## One-time setup (bootstrap — done before demo)

- [ ] Fund accounts via faucet: **Agent, MM, Bank**
- [ ] Alice's wallet holds **stablecoin** (agent authorized to use it)
- [ ] **MM** gets RLUSD + holds target token → posts **AMM pool** (`AMMCreate`) RLUSD/INR
- [ ] Trust lines set where needed (`TrustSet`)

---

## Runtime flow (autonomous)

```
ALICE (off-ramp-side, on-chain wallet w/ stablecoin)
  │  invoice {amount, currency, due} + stablecoin authorized
  ▼
┌──────────────────────── FX AGENT (autonomous) ────────────────────────┐
│ 1. MINT     invoice → MPT      [MPTokenIssuanceCreate]                 │
│             memo: invoice hash, amount, FX rate, status, KYA verdict   │
│                                                                       │
│ 2. SWAP     stablecoin ──DEX──► target token   [Payment + path]       │
│             matched against MM's AMM liquidity (guarded: floor,       │
│             SendMax, no partial)                                       │
│                                                                       │
│ 3. KYA      bank screens agent ──► PASS / HOLD / REJECT               │
│               ├ PASS   → step 5                                        │
│               ├ HOLD   → step 4 (escrow)                              │
│               └ REJECT → stop (clawback / return)                    │
│                                                                       │
│ 4. ESCROW   conditional token escrow [EscrowCreate]                   │
│             ⌛ wait for KYA clearance → [EscrowFinish] (release)       │
│             (timeout → [EscrowCancel])                                │
│                                                                       │
│ 5. PAYOUT   send target token → BANK's XRPL address  [Payment]        │
│             = redemption of the bank's own IOU (human-confirm)        │
└───────────────────────────────────────────────────────────────────────┘
  │
  ▼
BANK (on-chain endpoint)
  │  burns/redeems token → pushes FIAT off-chain   ⟵ bank's job, NOT agent
  ▼
BOB (off-chain bank account)  ← receives real money (INR)
```

---

## Role boundaries

- **Agent does:** mint, swap, KYA gate, escrow, deliver token to bank. Fully autonomous.
- **MM does:** stand in the DEX with liquidity (passive, Level 1 AMM).
- **Bank does:** issue/redeem the token + **fiat off-ramp to Bob** (off-chain).
- **Agent never:** issues the target token, holds fiat, or touches Bob's bank.

## What's autonomous vs one-time

| One-time (bootstrap) | Autonomous (every invoice) |
|---|---|
| create + fund accounts | mint → swap → KYA → escrow → payout |
| seed AMM liquidity | the whole settlement loop |
| claim RLUSD (browser faucet) | balances move, hashes produced |

## Proof for the demo
Print **balances before/after** + **Testnet explorer links** for every tx.
The chain of validated transactions = the evidence of transfer.

## Roadmap talking points (say, don't build)
- KYA → on-chain **credentials + permissioned DEX** (ledger-enforced compliance)
- Multi-currency: swap the bridge stablecoin per sender region (USD→RLUSD, EUR→EURC)
