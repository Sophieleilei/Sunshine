import { Client, Wallet } from 'xrpl';
import { config } from '../config.js';
import { log } from '../util/log.js';
import { txLink } from '../util/explorer.js';

let _client = null;

export async function getClient() {
  if (_client && _client.isConnected()) return _client;
  _client = new Client(config.endpoint);
  await _client.connect();
  log.info('connected to XRPL', { endpoint: config.endpoint });
  return _client;
}

export async function disconnect() {
  if (_client && _client.isConnected()) {
    await _client.disconnect();
    _client = null;
  }
}

export function walletFromSeed(seed) {
  if (!seed) throw new Error('missing seed');
  return Wallet.fromSeed(seed);
}

// Full signing ceremony wrapper (mirrors the starter-kit Wallet skill):
// autofill -> (preview) -> sign -> submit -> wait for validation.
// `confirm` is an async predicate; if it returns false we abort before signing.
export async function submit(tx, wallet, { confirm } = {}) {
  const client = await getClient();
  const prepared = await client.autofill(tx);

  if (confirm) {
    const proceed = await confirm(prepared);
    if (!proceed) {
      log.warn('transaction aborted before signing', { type: tx.TransactionType });
      return { aborted: true };
    }
  }

  const signed = wallet.sign(prepared);
  const res = await client.submitAndWait(signed.tx_blob);
  const code = res.result.meta?.TransactionResult;
  if (code !== 'tesSUCCESS') {
    throw new Error(`${tx.TransactionType} failed: ${code}`);
  }
  log.ok(`${tx.TransactionType} validated`, { result: code });
  console.log(`    🔗 ${txLink(res.result.hash)}`);
  return res.result;
}
