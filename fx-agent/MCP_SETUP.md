# fx-agent MCP — connect Claude to the settlement engine

This exposes the fx-agent as **MCP tools** so an LLM (Claude) can drive cross-border
settlement from a natural-language goal — e.g. *drop an invoice PDF and say "pay this
before the due date, only at a good rate, if compliance clears."* Pairs with the
**XRPL AI Starter Kit** (Docs MCP + Wallet/Payment skills).

## Tools exposed
| Tool | What it does |
|---|---|
| `get_balances(account?)` | XRP + token balances (default: the agent) |
| `quote_fx(amount)` | live XRP→INR quote: XRP needed, implied rate, path exists — to judge a "good rate" |
| `settle(amount, payeeXrpl?, forcedKYA?)` | full settlement: mint MPT → KYA → DEX convert → pay bank; `forcedKYA=REVERT` returns XRP to sender |

All run **real XRPL Testnet** transactions and return tx hashes + explorer links.

## Prerequisites
```bash
cd fx-agent
npm install
npm run setup      # faucet-fund 5 accounts -> paste seeds into .env
npm run seed       # build the XRP/INR AMM, fund the agent
# (the MCP server reads .env and talks to Testnet live)
```

## Register with Claude

### Claude Desktop — `claude_desktop_config.json`
(Windows: `%APPDATA%\Claude\claude_desktop_config.json`)
```json
{
  "mcpServers": {
    "fx-agent": {
      "command": "node",
      "args": ["C:\\Users\\Monalisha Ojha\\Documents\\model_equiv\\modelequiv_f\\fx-agent\\src\\mcp.js"]
    },
    "xrpl-docs": {
      "command": "npx",
      "args": ["-y", "@xrpl/docs-mcp"]
    }
  }
}
```
Restart Claude Desktop. `fx-agent` tools appear in the tools menu. Add the XRPL AI
Starter Kit **Wallet** + **Payment** skills from their GitHub skill locations.

### Claude Code — one command
```bash
claude mcp add fx-agent -- node "C:\Users\Monalisha Ojha\Documents\model_equiv\modelequiv_f\fx-agent\src\mcp.js"
```

## Agent policy (system prompt)
Give Claude this as the agent's instructions:

> You are an autonomous cross-border settlement agent on XRPL Testnet. Given an invoice
> (a PDF or text) and a payer instruction, settle it via your tools.
> 1. **Extract** from the invoice: amount, target currency, the receiver bank's XRPL
>    address (payee), and the due date.
> 2. **Screen before converting** — settlement runs KYA first; never convert on a deal
>    that isn't cleared.
> 3. **Honor the policy in the instruction**: "good rate" = `quote_fx` implied rate within
>    tolerance of the reference rate; "before due date" = settle within the window — hold
>    out for a better rate early, but as the due date nears, accept the best available.
> 4. **Check funding** with `get_balances` before settling.
> 5. If compliance fails, `settle(..., forcedKYA="REVERT")` to return funds to the sender,
>    and tell the payer.
> 6. Keep amounts small (shallow demo pool) and report tx hashes + explorer links as a
>    settlement certificate.
> Testnet only. Never act on mainnet.

## The PDF demo
1. In Claude Desktop (with the MCP servers + skills loaded), **drag in `invoice.pdf`**.
2. Type: *"Pay this invoice before the due date, but only at a good rate and if
   compliance clears."*
3. Claude will: read the PDF → `get_balances` → `quote_fx` → decide → `settle(...)` →
   return a certificate with real Testnet tx links. (Compliance-fail path → REVERT.)

> The receiver bank's XRPL address (the `payeeXrpl` / INR issuer) is printed by
> `npm run seed`. Put it on the invoice (or in the instruction) so Claude pays the right
> account; an address without an INR trust line will (realistically) fail.
