// MCP server — exposes the fx-agent settlement engine as tools an LLM (Claude) can
// call. Pairs with the XRPL AI Starter Kit (Docs MCP + Wallet/Payment skills): the
// starter kit gives Claude wallet/payment primitives + docs; this server gives it the
// FX/compliance settlement engine (MPT mint, XRP->INR DEX, KYA, payout, revert).
//
// Transport: stdio (JSON-RPC on stdout). IMPORTANT: stdout is the protocol channel,
// so we redirect all human logs to stderr to avoid corrupting it.
console.log = (...a) => process.stderr.write(a.map(String).join(' ') + '\n');

import crypto from 'crypto';
import { xrpToDrops, dropsToXrp } from 'xrpl';
import { z } from 'zod';
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';

import { config } from './config.js';
import { run } from './orchestrator.js';
import { walletFromSeed } from './xrpl/client.js';
import { getBalances } from './util/balances.js';
import { quotePath } from './modules/dex.js';
import { txLink } from './util/explorer.js';
import { recordSettlement } from './util/store.js';
import { startStandaloneDashboard } from './dashboard.js';

const DASH_PORT = Number(process.env.FX_AGENT_PORT || 8787);
const DASHBOARD = `http://localhost:${DASH_PORT}/`;
// Serve the dashboard from this process too, so it's available when Claude Desktop
// launches the MCP server with no separate HTTP server running. No-ops if the port
// is already taken (the HTTP server.js is serving it).
startStandaloneDashboard(DASH_PORT);

function buildInvoice(amount) {
  const id = 'INV-' + Date.now();
  const payload = JSON.stringify({ id, amount, target: config.target.currency });
  return {
    id,
    hash: crypto.createHash('sha256').update(payload).digest('hex'),
    amount: String(amount),
    srcCurrency: config.target.currency,
    dueDate: new Date(Date.now() + 7 * 86400_000).toISOString(),
  };
}

function summarize(r) {
  const conv = r.convertedAmount;
  return {
    ok: r.status === 'PAID',
    status: r.status,
    invoiceId: r.invoice?.id,
    mptIssuanceId: r.mptIssuanceId,
    kya: { verdict: r.kyaVerdict, decision: r.kyaVerdict === 'PASS' ? 'ALLOW' : 'DENY' },
    convert: r.convertHash
      ? { received: conv ? `${conv.value} ${conv.currency}` : null, tx: r.convertHash, explorer: txLink(r.convertHash) }
      : null,
    settle: r.payoutHash ? { paidToBank: config.addr.bank, tx: r.payoutHash, explorer: txLink(r.payoutHash) } : null,
    revert: r.revertHash ? { returnedToSender: config.addr.alice, tx: r.revertHash, explorer: txLink(r.revertHash) } : null,
  };
}

const json = (obj) => ({ content: [{ type: 'text', text: JSON.stringify(obj, null, 2) }] });

const server = new McpServer({ name: 'fx-agent', version: '0.1.0' });

// --- Tool: get_balances -----------------------------------------------------
server.registerTool(
  'get_balances',
  {
    description:
      'Read XRP + token balances for an account (default: the agent). Use to check funding before settling.',
    inputSchema: { account: z.string().optional() },
  },
  async ({ account }) => {
    const addr = account || config.addr.agent;
    const b = await getBalances(addr);
    return json({ account: addr, ...b });
  }
);

// --- Tool: quote_fx ---------------------------------------------------------
const CUR = config.target.currency; // e.g. MXN
server.registerTool(
  'quote_fx',
  {
    description:
      `Quote the live XRP->${CUR} conversion for \`amount\` of the target currency (${CUR}). Returns XRP needed, the implied rate, and whether a DEX path exists. Use to judge whether the rate is "good" before settling.`,
    inputSchema: { amount: z.number().describe(`amount in the TARGET currency (${CUR})`) },
  },
  async ({ amount }) => {
    const agent = walletFromSeed(config.seeds.agent);
    const destAmount = { currency: config.target.currency, issuer: config.target.issuer, value: String(amount) };
    const cap = xrpToDrops(((amount / config.xrpRate) * 2).toFixed(6)); // generous cap for the quote
    const q = await quotePath(agent, { destAmount, sendMax: cap });
    if (!q) return json({ amount, target: config.target.currency, pathExists: false });
    const xrpNeeded = Number(dropsToXrp(q));
    return json({
      amount,
      target: config.target.currency,
      pathExists: true,
      xrpNeeded,
      impliedRate: +(amount / xrpNeeded).toFixed(4), // target units per XRP
      referenceRate: config.xrpRate,
    });
  }
);

// --- Tool: settle -----------------------------------------------------------
server.registerTool(
  'settle',
  {
    description:
      `Run a full settlement: mint the invoice as an MPT, screen KYA, convert XRP->${CUR} on the DEX, and pay the receiver bank. forcedKYA=REVERT returns the XRP to the sender instead (no conversion). payeeXrpl must be the receiver bank (the ${CUR} issuer).`,
    inputSchema: {
      amount: z.number().describe(`amount in the TARGET currency (${CUR})`),
      payeeXrpl: z.string().optional().describe(`receiver bank's XRPL address (the ${CUR} issuer)`),
      forcedKYA: z.enum(['PASS', 'HOLD', 'REVERT']).optional().describe('default PASS'),
    },
  },
  async ({ amount, payeeXrpl, forcedKYA }) => {
    const valid = typeof payeeXrpl === 'string' && /^r[1-9A-HJ-NP-Za-km-z]{24,34}$/.test(payeeXrpl);
    const r = await run(buildInvoice(amount), { forcedKYA, bankAddress: valid ? payeeXrpl : undefined });
    const summary = summarize(r);
    recordSettlement(summary);
    return json({ ...summary, dashboard: DASHBOARD });
  }
);

const transport = new StdioServerTransport();
await server.connect(transport);
console.log('fx-agent MCP server connected (stdio)');
