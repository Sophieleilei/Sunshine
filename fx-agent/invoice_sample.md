# INVOICE  —  INV-2026-0042

**Date:** 2026-06-21  **Due date:** 2026-07-05

**From (sender / payer):**
Alice GmbH — Berlin, Germany

**To (receiver / payee):**
Bob Textiles Pvt. Ltd. — Mumbai, India

| Description | Amount |
|---|---|
| Consulting services | **50 INR** |
| **Total due** | **50 INR** |

**Pay in:** INR (Indian Rupee)

**Receiver bank — XRPL settlement address (payee):**
`rzAd1ychrhChJjkiNXVjaBVcmvVuUepi3`

**Receiver bank fiat details (off-chain off-ramp):**
IBAN: CH93 0076 2011 6238 5295 7

---

> Demo note: this is the sample the AI agent reads. Drop this (or a PDF of it) into
> Claude with: "Pay this invoice before the due date, but only at a good rate and if
> compliance clears." Claude extracts the amount + payee, screens KYA, quotes the rate,
> and calls `settle` on the fx-agent MCP. The receiver bank XRPL address above is the
> agent's seeded bank (the INR issuer) — replace it with your own `npm run seed` output.
