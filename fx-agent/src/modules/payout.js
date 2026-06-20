import { submit } from '../xrpl/client.js';
import { jsonMemo } from '../util/hex.js';
import { log } from '../util/log.js';
import { config } from '../config.js';

// Step 8 — payout to the receiver's BANK XRPL address (NOT XYZ; the bank credits
// XYZ off-chain). Highest-value, irreversible step -> human confirmation by default.
export async function payBank(agent, { bankAddress, amount, state }) {
  log.info('paying receiver bank', { bankAddress, amount });

  const confirm = config.humanConfirmPayout
    ? async (prepared) => {
        log.warn('HUMAN CONFIRM required for payout', {
          to: prepared.Destination,
          amount: prepared.Amount,
        });
        // Wire this to a real prompt/approval channel. Default: allow in demo.
        return true;
      }
    : undefined;

  return submit(
    {
      TransactionType: 'Payment',
      Account: agent.address,
      Destination: bankAddress,
      Amount: amount,
      Memos: [jsonMemo(state, { type: 'fx-agent/settlement' })],
    },
    agent,
    { confirm }
  );
}
