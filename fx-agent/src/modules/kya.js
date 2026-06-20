import { log } from '../util/log.js';

// KYA = Know Your Agent. The gate the receiver's BANK applies to the AGENT before the
// transaction proceeds. It runs BEFORE conversion, while the agent still holds the
// bridge stablecoin — so on failure the funds never moved and are returned to the
// sender. Implementation is ASSUMED / out of scope — mock oracle returning
// PASS / HOLD / REVERT.

export const KYA = Object.freeze({ PASS: 'PASS', HOLD: 'HOLD', REVERT: 'REVERT' });

// `forced` lets the demo drive a specific branch (--kya=HOLD etc.).
export async function checkKYA({ agentAddress, bankAddress }, forced) {
  log.info('requesting KYA verdict from bank (pre-conversion)', { agentAddress, bankAddress });
  const verdict = forced || KYA.PASS;
  log.ok('KYA verdict received', { verdict });
  return verdict;
}

// HOLD: bank still screening. Funds stay in the agent's wallet (no escrow). This
// re-checks until the bank resolves. Mock resolves to PASS.
export async function awaitKYAClearance({ agentAddress, bankAddress }) {
  log.info('bank KYA still running — funds remain in agent wallet, awaiting clearance');
  return KYA.PASS;
}
