import { xrpToDrops } from 'xrpl';
import { config } from './config.js';
import { log } from './util/log.js';
import { S, newSettlement, transition } from './state.js';
import { walletFromSeed } from './xrpl/client.js';
import { mintInvoiceMPT } from './modules/mpt.js';
import { checkKYA, awaitKYAClearance, KYA } from './modules/kya.js';
import { convert } from './modules/dex.js';
import { returnToSender } from './modules/revert.js';
import { payBank } from './modules/payout.js';
import { snapshot } from './util/balances.js';

// Screen-first, escrow-free lifecycle:
//   ISSUED -> MINTED -> KYA -> { PASS|HOLD->cleared -> CONVERT -> PAYOUT -> PAID
//                               REVERT (or HOLD declined) -> return stable -> REVERTED }
// The bridge stablecoin stays in the agent's wallet until KYA passes. On failure it
// never converted, so it is returned to the sender as-is.
export async function run(invoice, { forcedKYA, bankAddress: bankOverride } = {}) {
  const agent = walletFromSeed(config.seeds.agent);
  // Payout destination = the receiver bank's XRPL address (the payee). In this demo
  // it must be the INR issuer (our seeded bank) for the redemption to settle; an
  // address without an INR trust line will (realistically) fail.
  const bankAddress = bankOverride || config.addr.bank;
  const aliceAddress = config.addr.alice;
  const s = newSettlement(invoice);

  const accounts = { AGENT: agent.address, ALICE: aliceAddress, BANK: bankAddress };
  await snapshot('BEFORE', accounts);

  // Bridge = native XRP (agent holds it, funded by Alice). invoice.amount is in the
  // target currency (INR); xrpNominal is the XRP equivalent at the demo FX rate.
  const xrpNominal = Number(invoice.amount) / config.xrpInr; // XRP the sender's value buys
  const xrpDrops = (xrp) => xrpToDrops(xrp.toFixed(6));

  try {
    // --- MINT invoice MPT ---
    log.step('MINT invoice MPT');
    const mptId = await mintInvoiceMPT(agent, invoice);
    transition(s, S.MINTED, { mptIssuanceId: mptId });

    // --- KYA gate FIRST (before any conversion; funds stay in wallet) ---
    log.step('KYA gate (bank screens agent, pre-conversion)');
    transition(s, S.KYA);
    let verdict = await checkKYA({ agentAddress: agent.address, bankAddress }, forcedKYA);
    transition(s, S.KYA, { kyaVerdict: verdict });

    if (verdict === KYA.HOLD) {
      log.step('HOLD — funds stay in agent wallet, awaiting bank clearance');
      verdict = await awaitKYAClearance({ agentAddress: agent.address, bankAddress });
      transition(s, S.KYA, { kyaVerdict: verdict });
    }

    if (verdict === KYA.REVERT) {
      log.step('REVERT — returning XRP to sender (no conversion happened)');
      const res = await returnToSender(agent, {
        aliceAddress,
        amount: xrpDrops(xrpNominal),
        state: { invoiceId: invoice.id, mptIssuanceId: mptId, kya: 'REVERT' },
      });
      return finish(s, transition(s, S.REVERTED, { revertHash: res?.hash }), accounts);
    }

    // --- PASS: convert XRP -> target, then pay the bank ---
    log.step(`CONVERT XRP -> ${config.target.currency} via DEX`);
    const destAmount = {
      currency: config.target.currency,
      issuer: config.target.issuer,
      value: invoice.amount,
    };
    const sendMax = xrpDrops(xrpNominal * (1 + config.maxSlippage)); // XRP drops ceiling
    const cres = await convert(agent, { destAmount, sendMax });
    transition(s, S.CONVERTED, {
      convertedAmount: destAmount,
      stableSpent: sendMax,
      fxRate: config.xrpInr,
      convertHash: cres?.hash,
    });

    log.step('PAYOUT — pay bank (redemption of its IOU)');
    const res = await payBank(agent, {
      bankAddress,
      amount: destAmount,
      state: { invoiceId: invoice.id, mptIssuanceId: mptId, kya: 'PASS', fxRate: config.fxRate },
    });
    return finish(s, transition(s, S.PAID, { payoutHash: res?.hash }), accounts);
  } catch (e) {
    log.err('settlement failed', { error: e.message, status: s.status });
    return finish(s, transition(s, S.FAILED, { error: e.message }), accounts);
  }
}

async function finish(_s, result, accounts) {
  await snapshot('AFTER', accounts);
  return result;
}
