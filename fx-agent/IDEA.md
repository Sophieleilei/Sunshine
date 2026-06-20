# FX Trustworthy Agent — Locked Idea

> Reference: XRPL AI Starter Kit — https://ripple.com/insights/xrpl-ai-starter-kit/

## One-line

An autonomous cross-border invoice settlement agent on the XRPL. A US business
invoices an Indian business; the agent mints the invoice on-ledger, converts the
payment through RLUSD to the receiver's currency via the XRPL DEX, gates the
release on a KYA decision, and pays out to the receiver's bank — both parties stay
off-chain.

## Actors

- **Alice** — sender, a Texas (US) company. Issues the invoice. **Off-chain.**
- **XYZ** — receiver, a company in India. Gets paid. **Off-chain.**
- **FX Trustworthy Agent** — the autonomous on-ledger actor. Holds the MPT, runs
  the conversion, holds escrow, and makes the final payout. Built on the XRPL AI
  Starter Kit.
- **KYA check** — **assumed present** (Know-Your-Agent / compliance gate). Returns
  one of: **PASS / HOLD / REJECT**. Implementation is out of scope — we just consume
  its verdict.

## Flow (locked)

1. **Invoice issued (off-chain).** Alice releases an invoice to XYZ. Neither party
   touches the ledger directly.

2. **Mint invoice as MPT.** The agent mints the invoice data as a **Multi-Purpose
   Token (MPT)** on the XRPL. This is the on-ledger representation of the invoice.

3. **Convert to RLUSD.** The invoice amount is converted into the **RLUSD**
   stablecoin (the stable settlement leg).

4. **Convert to receiver currency via DEX.** RLUSD is converted to the invoice
   receiver's destination currency through the **native XRPL DEX**.

5. **Updated MPT held by agent.** The MPT — now reflecting the converted payment —
   stays with the **same agent**.

6. **KYA decision → PASS / HOLD / REJECT.**
   - **PASS** → proceed to payout (step 8).
   - **HOLD** → funds go into **conditional token escrow** (step 7). Used when the
     bank's KYA takes longer.
   - **REJECT** → no payout; settlement does not proceed.

7. **Conditional escrow (HOLD path).** On HOLD, the converted funds sit in a
   **conditional token escrow**. When KYA later returns **PASS**, the funds are
   **released** from escrow.

8. **Payout to receiver bank.** The agent makes the transaction to the **receiver's
   bank address**.

9. **Settlement complete.** Both invoices / both parties remain off-chain throughout.

## Removed from the earlier draft (out of scope now)

- DepositPreauth as on-ledger authorization
- Explicit OFAC/EU sanctions-list screening detail (folded into the assumed KYA gate)
- PriceOracle guard-rate FX timing / due-date-window firing
- X402 settlement framing
- Multi-sign for high-value transfers
- Separate settlement certificate artifact

## Core primitives in play

- **MPT (Multi-Purpose Token)** — on-ledger invoice representation.
- **RLUSD** — stablecoin settlement leg.
- **XRPL DEX** — native cross-currency conversion.
- **Conditional escrow** — the HOLD mechanism, released on KYA PASS.
- **KYA gate (assumed)** — PASS / HOLD / REJECT.
