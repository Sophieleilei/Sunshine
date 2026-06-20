# FX Trustworthy Agent (XRPL Testnet)

Autonomous cross-border invoice settlement agent on the XRP Ledger.
Alice (US, off-chain) invoices Bob (India, off-chain); the agent mints the invoice as
an **MPT**, swaps a bridge **stablecoin → INR token** on the native **XRPL DEX/AMM**,
gates the release on a **KYA** (Know Your Agent) decision from the receiver's **bank**,
and pays the **bank's XRPL address**. The bank does the fiat last-mile to Bob.

> Design is locked in [IDEA.md](IDEA.md) · [PLAN.md](PLAN.md) · [SKELETON.md](SKELETON.md).
> **Testnet/Devnet only** (mainnet endpoints are hard-refused in `config.js`).

## Actors (all Testnet accounts)

| Account | Role |
|---|---|
| **Agent** | autonomous orchestrator |
| **Alice** | sender; holds the bridge stablecoin, funds the agent |
| **MM** | market maker; seeds the USD/INR AMM (the "Bitso" stand-in) |
| **Bank** | issues the INR token, screens via KYA, redeems at payout |
| **Stable issuer** | issues the bridge stablecoin (stands in for RLUSD) |

## Lifecycle (screen-first, escrow-free, XRP bridge)

```
ISSUED → MINTED → KYA ┌─ PASS / HOLD→cleared → CONVERT (XRP→INR) → PAYOUT → PAID
                      └─ REVERT (or HOLD declined) → return XRP → REVERTED
```

Bridge asset = **native XRP** (the canonical XRPL cross-currency bridge, ODL-style) —
no issuer, no trust line, no faucet. KYA runs **before** conversion; the XRP stays in
the agent's wallet until KYA passes, so on failure it never converted and is returned
to the sender. (RLUSD/stablecoin stays a one-line mainnet config option.)

| Step | XRPL tx | Module |
|---|---|---|
| Mint invoice | `MPTokenIssuanceCreate` | `src/modules/mpt.js` |
| KYA gate (pre-conversion) | off-ledger oracle (mock PASS/HOLD/REVERT) | `src/modules/kya.js` |
| Convert XRP→INR via DEX/AMM | guarded cross-currency `Payment` (+ `ripple_path_find`) | `src/modules/dex.js` |
| Payout to bank | `Payment` (= redemption of the bank's IOU) | `src/modules/payout.js` |
| Revert to sender | `Payment` of XRP back to Alice | `src/modules/revert.js` |
| Orchestrator | state machine + balance snapshots | `src/orchestrator.js` |

The market maker seeds an **XRP/INR AMM** (`AMMCreate`) — the Bitso/B2C2 stand-in.

## Run

```bash
npm install
cp .env.example .env
npm run setup   # faucet-funds 5 accounts; paste the printed seeds into .env
npm run seed    # issuer flags + trust lines + issues tokens + seeds the USD/INR AMM
npm run demo            # PASS   path  (KYA passes → convert → redeem to bank)
npm run demo:hold       # HOLD   path  (funds wait in wallet → clear → convert → pay)
npm run demo:revert     # REVERT path  (KYA fails pre-conversion → stablecoin back to Alice)
```

Each run prints **balances before/after** and a **Testnet explorer link for every
transaction** — that chain of validated txs is the proof of transfer.

## Verified on Testnet (PASS / HOLD / REVERT all green)

- **PASS** — mint → KYA passes → AMM swap → redeem to bank; bank IOU reduced.
- **HOLD** — KYA pending; the stablecoin **stays in the agent's wallet** while the bank
  finishes screening, then on clearance converts + pays.
- **REVERT** — KYA fails **before** conversion; the stablecoin is returned to Alice
  (her balance goes up), nothing converted, bank untouched.

## Notes / design decisions

- **Risk A** — MPT metadata is immutable; mutable state (FX rate, status, KYA verdict)
  rides in payment **Memos** + the settlement record.
- **No escrow (by design)** — KYA runs before conversion and funds wait in the agent's
  wallet, so no escrow is needed. (Also, RLUSD *cannot* be escrowed: its issuer leaves
  `AllowTrustLineLocking` off on both Testnet and Mainnet, even though XLS-85 token
  escrow is live on Mainnet — escrow is per-issuer opt-in.)
- **Risk C** — DEX conversion is **guarded**: `ripple_path_find` quote vs. SendMax,
  min-receive floor, `tfPartialPayment` OFF. The MM's AMM provides the liquidity.
- **Stablecoin** — a self-contained test USD stablecoin stands in for **RLUSD** so the
  demo runs without the browser faucet. On mainnet, point `STABLE_*` at real RLUSD.
- **Market maker** — Level 1 (passive AMM). On mainnet you trade against real makers
  (B2C2 / Bitso / exchanges); here the MM account plays that role.
- **X402** is out of scope (HTTP-layer, not on-ledger).

## Roadmap talking points (not built)

- KYA → on-chain **credentials + permissioned DEX** (ledger-enforced compliance).
- Multi-currency: swap the bridge stablecoin per sender region (USD→RLUSD, EUR→EURC).
- Clawback on REJECT (`tfMPTCanClawback`); active market-maker agent (Level 2).
