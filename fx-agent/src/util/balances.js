import { getClient } from '../xrpl/client.js';
import { dropsToXrp } from 'xrpl';

// Read XRP + issued-token balances for an account. Used for before/after snapshots.
export async function getBalances(address) {
  const client = await getClient();
  const info = await client.request({ command: 'account_info', account: address }).catch(() => null);
  const xrp = info ? dropsToXrp(info.result.account_data.Balance) : 0;

  const lines = await client
    .request({ command: 'account_lines', account: address })
    .catch(() => ({ result: { lines: [] } }));

  const tokens = {};
  for (const l of lines.result.lines) {
    const cur = prettyCurrency(l.currency);
    tokens[cur] = (Number(tokens[cur] || 0) + Number(l.balance)).toString();
  }
  return { xrp, tokens };
}

export async function snapshot(label, accounts) {
  console.log(`\n  💰 balances (${label}):`);
  for (const [name, address] of Object.entries(accounts)) {
    const b = await getBalances(address);
    const toks = Object.entries(b.tokens)
      .map(([c, v]) => `${c}=${v}`)
      .join(' ');
    console.log(`     ${name.padEnd(13)} XRP=${b.xrp}  ${toks}`);
  }
}

// 40-char hex currency codes -> readable ASCII when possible.
function prettyCurrency(c) {
  if (c.length !== 40) return c;
  const ascii = Buffer.from(c, 'hex').toString('utf8').replace(/\0+$/, '');
  return /^[\x20-\x7E]+$/.test(ascii) ? ascii : c;
}
