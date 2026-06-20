import { submit } from '../xrpl/client.js';
import { jsonMemo } from '../util/hex.js';
import { log } from '../util/log.js';

// REVERT — KYA failed before conversion, so the bridge asset never converted to the
// target currency. Return it straight to the sender (Alice). No DEX unwind, no FX loss.
// `amount` is XRP drops (string) or a token object — works for either bridge.
export async function returnToSender(agent, { aliceAddress, amount, state }) {
  log.info('REVERT — returning bridge funds to sender', { aliceAddress, amount });
  return submit(
    {
      TransactionType: 'Payment',
      Account: agent.address,
      Destination: aliceAddress,
      Amount: amount, // XRP drops or token object
      Memos: [jsonMemo(state, { type: 'fx-agent/revert' })],
    },
    agent
  );
}
