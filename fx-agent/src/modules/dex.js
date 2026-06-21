import { getClient, submit, prepareTx } from '../xrpl/client.js';
import { log } from '../util/log.js';

// Step: convert the bridge asset -> dest currency via the native XRPL DEX/AMM.
// Bridge is native XRP, so SendMax is a drops string (not a token object).
// Guarded conversion (Risk C): pre-trade quote, min-receive floor (Amount = dest),
// max-spend ceiling (SendMax), tfPartialPayment OFF.

const tfNoPartial = 0; // we deliberately do NOT set tfPartialPayment

const isXrp = (amt) => typeof amt === 'string';

// Advisory quote via ripple_path_find. Returns cheapest source_amount, or null if no
// path. Non-fatal: the binding guard is the payment itself.
export async function quotePath(agent, { destAmount, sendMax }) {
  const client = await getClient();
  const sourceCurrencies = isXrp(sendMax)
    ? [{ currency: 'XRP' }]
    : [{ currency: sendMax.currency, issuer: sendMax.issuer }];
  try {
    const resp = await client.request({
      command: 'ripple_path_find',
      source_account: agent.address,
      destination_account: agent.address,
      destination_amount: destAmount,
      source_currencies: sourceCurrencies,
    });
    const alts = resp.result?.alternatives || [];
    if (!alts.length) return null;
    return alts[0].source_amount; // drops string (XRP) or {currency,issuer,value}
  } catch (e) {
    log.warn('ripple_path_find errored (advisory only)', { error: e.message });
    return undefined;
  }
}

const amtValue = (a) => (isXrp(a) ? Number(a) : Number(a.value)); // drops or token value

// Non-custodial Trip 1: build + autofill the UNSIGNED conversion tx (no key). Quotes
// the live rate, sets the guard (quote + maxSlippage), builds the cross-currency
// Payment, autofills it, and returns the unsigned tx + a human-readable preview.
export async function prepareConvert(agent, { destAmount, sendMax, maxSlippage = 0.05 }) {
  const quote = await quotePath(agent, { destAmount, sendMax });
  if (quote === null) throw new Error('no DEX path for the pair (no liquidity / no route)');

  let effSendMax = sendMax;
  if (quote) {
    if (amtValue(quote) > amtValue(sendMax)) {
      throw new Error(`quote ${amtValue(quote)} exceeds cap ${amtValue(sendMax)} (rate moved far)`);
    }
    effSendMax = isXrp(quote)
      ? String(Math.ceil(Number(quote) * (1 + maxSlippage)))
      : { currency: quote.currency, issuer: quote.issuer, value: (Number(quote.value) * (1 + maxSlippage)).toFixed(6) };
  }

  const tx = {
    TransactionType: 'Payment',
    Account: agent.address,
    Destination: agent.address,
    Amount: destAmount,
    SendMax: effSendMax,
    Flags: tfNoPartial,
  };
  const unsigned = await prepareTx(tx); // autofill, NO signing
  log.ok('unsigned conversion tx prepared (no key touched)', {
    sequence: unsigned.Sequence,
    fee: unsigned.Fee,
  });
  return {
    unsignedTx: unsigned,
    preview: {
      network: 'XRPL Testnet',
      type: `Payment · XRP → ${destAmount.currency} (DEX)`,
      from: agent.address,
      sendMax: isXrp(effSendMax) ? `${effSendMax} drops` : `${effSendMax.value} ${effSendMax.currency}`,
      amount: `${destAmount.value} ${destAmount.currency}`,
      fee: unsigned.Fee,
      sequence: unsigned.Sequence,
    },
  };
}

export async function convert(agent, { destAmount, sendMax, maxSlippage = 0.05 }) {
  // `sendMax` here is a GENEROUS cap just for quoting. The real guard is derived from
  // the LIVE quote + maxSlippage, so it adapts to the current pool rate (drift-proof)
  // while still rejecting an adverse move between quote and execution.
  log.info('quoting DEX path', { destAmount, cap: sendMax });
  const quote = await quotePath(agent, { destAmount, sendMax });
  if (quote === null) {
    throw new Error('no DEX path for the pair (no liquidity / no route)');
  }

  let effSendMax = sendMax; // if the quote errored (undefined), fall back to the cap
  if (quote) {
    if (amtValue(quote) > amtValue(sendMax)) {
      throw new Error(`quote ${amtValue(quote)} exceeds cap ${amtValue(sendMax)} (rate moved far)`);
    }
    effSendMax = isXrp(quote)
      ? String(Math.ceil(Number(quote) * (1 + maxSlippage)))
      : { currency: quote.currency, issuer: quote.issuer, value: (Number(quote.value) * (1 + maxSlippage)).toFixed(6) };
    log.ok('guard set from live quote', {
      needs: isXrp(quote) ? `${quote} drops` : `${quote.value} ${quote.currency}`,
      maxSpend: isXrp(effSendMax) ? `${effSendMax} drops` : `${effSendMax.value} ${effSendMax.currency}`,
    });
  }

  // Currency exchange to self: bridge in (SendMax), dest token out (Amount floor).
  log.info('submitting guarded cross-currency payment');
  return submit(
    {
      TransactionType: 'Payment',
      Account: agent.address,
      Destination: agent.address,
      Amount: destAmount, // min-receive floor (dest token)
      SendMax: effSendMax, // live-quote + slippage ceiling
      Flags: tfNoPartial, // tfPartialPayment OFF
    },
    agent
  );
}
