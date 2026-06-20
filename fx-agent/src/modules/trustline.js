import { submit } from '../xrpl/client.js';
import { log } from '../util/log.js';

// Step 3 & 4 prerequisite: set a trust line so an account can hold an issued token
// (RLUSD, or the agent-issued dest token).
export async function setTrustLine(wallet, { currency, issuer, limit = '1000000000' }) {
  log.info('setting trust line', { currency, issuer, account: wallet.address });
  return submit(
    {
      TransactionType: 'TrustSet',
      Account: wallet.address,
      LimitAmount: { currency, issuer, value: String(limit) },
    },
    wallet
  );
}
