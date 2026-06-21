import path from 'path';
import { fileURLToPath } from 'url';
import dotenv from 'dotenv';
import { Wallet } from 'xrpl';

// Load .env by ABSOLUTE path (fx-agent/.env) so it works no matter the launcher's
// working directory — e.g. when Claude Desktop spawns the MCP server.
const __dirname = path.dirname(fileURLToPath(import.meta.url));
dotenv.config({ path: path.join(__dirname, '..', '.env') });

function bool(v, def = false) {
  if (v === undefined) return def;
  return String(v).toLowerCase() === 'true';
}

// Derive the classic address from a seed (so .env only stores seeds).
const addrOf = (seed) => (seed ? Wallet.fromSeed(seed).address : '');

const seeds = {
  agent: process.env.AGENT_SEED || '',
  alice: process.env.ALICE_SEED || '',
  mm: process.env.MM_SEED || '',
  bank: process.env.BANK_SEED || '',
  stableIssuer: process.env.STABLE_ISSUER_SEED || '',
};

const addr = {
  agent: addrOf(seeds.agent),
  alice: addrOf(seeds.alice),
  mm: addrOf(seeds.mm),
  bank: addrOf(seeds.bank),
  stableIssuer: addrOf(seeds.stableIssuer),
};

export const config = {
  endpoint: process.env.XRPL_ENDPOINT || 'wss://s.altnet.rippletest.net:51233',
  seeds,
  addr,

  // Bridge asset = native XRP (the canonical XRPL cross-currency bridge, ODL-style).
  // No issuer, no trust line, no faucet. RLUSD/stablecoin stays a mainnet config option.
  bridge: 'XRP',
  // FX rate for the XRP -> target leg: target units per 1 XRP (e.g. 1 XRP = ~10 MXN).
  xrpRate: Number(process.env.XRP_RATE || process.env.XRP_INR || 10),

  // Target currency token — issued by the BANK/gateway (licensed issuer).
  target: {
    currency: process.env.DEST_CURRENCY || 'MXN',
    issuer: process.env.DEST_ISSUER || addr.bank,
  },

  invoice: {
    amount: process.env.INVOICE_AMOUNT || '1000',
    srcCurrency: process.env.INVOICE_SRC_CURRENCY || 'USD',
    dueDays: Number(process.env.INVOICE_DUE_DAYS || 7),
  },

  // FX rate used by the seeded AMM (target per 1 stable). 1 USD = ~83 INR.
  fxRate: Number(process.env.FX_RATE || 83),
  maxSlippage: Number(process.env.MAX_SLIPPAGE || 0.02),
  humanConfirmPayout: bool(process.env.HUMAN_CONFIRM_PAYOUT, false),
};

// Guard: Testnet/Devnet ONLY. Refuse anything that looks like mainnet.
const MAINNET_HINTS = ['s1.ripple.com', 's2.ripple.com', 'xrplcluster.com'];
if (MAINNET_HINTS.some((h) => config.endpoint.includes(h))) {
  throw new Error(
    `Refusing to run: endpoint ${config.endpoint} looks like MAINNET. This agent is Testnet/Devnet only.`
  );
}
