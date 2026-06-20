import crypto from 'crypto';
import { config } from './config.js';
import { log } from './util/log.js';
import { disconnect } from './xrpl/client.js';
import { run } from './orchestrator.js';

// Parse --kya=PASS|HOLD|REJECT
function forcedKYA() {
  const arg = process.argv.find((a) => a.startsWith('--kya='));
  return arg ? arg.split('=')[1].toUpperCase() : undefined;
}

function buildInvoice() {
  const id = 'INV-' + Date.now();
  const payload = JSON.stringify({
    id,
    from: 'Alice (Texas, US)',
    to: 'XYZ (India)',
    amount: config.invoice.amount,
    srcCurrency: config.invoice.srcCurrency,
  });
  return {
    id,
    hash: crypto.createHash('sha256').update(payload).digest('hex'),
    amount: config.invoice.amount,
    srcCurrency: config.invoice.srcCurrency,
    dueDate: new Date(Date.now() + config.invoice.dueDays * 86400_000).toISOString(),
  };
}

async function main() {
  if (!config.seeds.agent) {
    log.err('AGENT_SEED is empty — run `npm run setup` first and fill in .env');
    process.exit(1);
  }

  log.step('FX Trustworthy Agent — settlement run', {
    endpoint: config.endpoint,
    forcedKYA: forcedKYA() || 'PASS (default)',
  });

  const invoice = buildInvoice();
  const result = await run(invoice, { forcedKYA: forcedKYA() });

  log.step('DONE', { status: result.status, mptIssuanceId: result.mptIssuanceId });
  console.log('\nSettlement history:');
  for (const h of result.history) console.log(`  ${h.at}  ${h.status}`);

  await disconnect();
}

main().catch(async (e) => {
  log.err('fatal', { error: e.message });
  await disconnect();
  process.exit(1);
});
