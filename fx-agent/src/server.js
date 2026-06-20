// HTTP API around the settlement agent — lets external systems (e.g. the Sunshine
// x402 pipeline) drive a real XRPL settlement over HTTP POST.
//
//   GET  /health            -> { status, bridge, target }
//   POST /settle  {amount,forcedKYA?}  -> runs MINT->KYA->CONVERT->PAYOUT (or REVERT)
//                                          and returns per-stage results + tx links.
import http from 'http';
import crypto from 'crypto';
import { config } from './config.js';
import { log } from './util/log.js';
import { run } from './orchestrator.js';
import { txLink } from './util/explorer.js';

const PORT = Number(process.env.FX_AGENT_PORT || 8787);

function buildInvoice(amount) {
  const id = 'INV-' + Date.now();
  const payload = JSON.stringify({ id, amount, target: config.target.currency });
  return {
    id,
    hash: crypto.createHash('sha256').update(payload).digest('hex'),
    amount: String(amount ?? config.invoice?.amount ?? 50),
    srcCurrency: config.target.currency,
    dueDate: new Date(Date.now() + 7 * 86400_000).toISOString(),
  };
}

// Map the orchestrator settlement record into a per-stage API response, so the
// caller can render KYA / DEX / Settle individually.
function toResponse(r) {
  const conv = r.convertedAmount;
  return {
    ok: r.status === 'PAID',
    status: r.status,
    invoiceId: r.invoice?.id,
    mptIssuanceId: r.mptIssuanceId,
    kya: { verdict: r.kyaVerdict, decision: r.kyaVerdict === 'PASS' ? 'ALLOW' : 'DENY' },
    convert: r.convertHash
      ? {
          bridge: config.bridge,
          xrpDropsMax: r.stableSpent,
          received: conv ? `${conv.value} ${conv.currency}` : null,
          hash: r.convertHash,
          explorer: txLink(r.convertHash),
        }
      : null,
    settle: r.payoutHash
      ? { paidTo: config.addr.bank, hash: r.payoutHash, explorer: txLink(r.payoutHash) }
      : null,
    revert: r.revertHash
      ? { returnedTo: config.addr.alice, hash: r.revertHash, explorer: txLink(r.revertHash) }
      : null,
    history: r.history,
  };
}

function send(res, code, obj) {
  const body = JSON.stringify(obj);
  res.writeHead(code, {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
  });
  res.end(body);
}

const server = http.createServer((req, res) => {
  if (req.method === 'OPTIONS') return send(res, 204, {});

  if (req.method === 'GET' && req.url === '/health') {
    return send(res, 200, {
      status: 'ok',
      bridge: config.bridge,
      target: config.target.currency,
      agent: config.addr.agent,
    });
  }

  if (req.method === 'POST' && req.url === '/settle') {
    let body = '';
    req.on('data', (c) => (body += c));
    req.on('end', async () => {
      let amount, forcedKYA, payeeXrpl;
      try {
        const j = body ? JSON.parse(body) : {};
        amount = j.amount;
        forcedKYA = j.forcedKYA; // PASS | HOLD | REVERT (default PASS)
        payeeXrpl = j.payeeXrpl; // receiver bank's XRPL address (the payout destination)
      } catch {
        return send(res, 400, { ok: false, error: 'invalid JSON body' });
      }
      // Only honour a payee that looks like a real classic address; else use our bank.
      const validPayee = typeof payeeXrpl === 'string' && /^r[1-9A-HJ-NP-Za-km-z]{24,34}$/.test(payeeXrpl);
      const bankAddress = validPayee ? payeeXrpl : undefined;
      try {
        log.step('HTTP /settle', { amount, forcedKYA: forcedKYA || 'PASS', bankAddress: bankAddress || '(default bank)' });
        const result = await run(buildInvoice(amount), { forcedKYA, bankAddress });
        return send(res, 200, toResponse(result));
      } catch (e) {
        return send(res, 500, { ok: false, error: e.message });
      }
    });
    return;
  }

  send(res, 404, { ok: false, error: 'not found' });
});

server.listen(PORT, () => {
  log.ok(`fx-agent HTTP API on http://localhost:${PORT}`, {
    endpoints: 'GET /health, POST /settle',
  });
});
