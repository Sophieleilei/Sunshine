import { getClient, submit } from '../xrpl/client.js';
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

export async function convert(agent, { destAmount, sendMax }) {
  log.info('quoting DEX path', { destAmount, sendMax });
  const quote = await quotePath(agent, { destAmount, sendMax });
  if (quote === null) {
    throw new Error('no DEX path for the pair (no liquidity / no route)');
  }
  if (quote && amtValue(quote) > amtValue(sendMax)) {
    throw new Error(`quote ${amtValue(quote)} exceeds guard SendMax ${amtValue(sendMax)} (slippage too high)`);
  }
  if (quote) log.ok('quote within guard', { needs: isXrp(quote) ? `${quote} drops` : `${quote.value} ${quote.currency}` });

  // Currency exchange to self: bridge in (SendMax), dest token out (Amount floor).
  log.info('submitting guarded cross-currency payment');
  return submit(
    {
      TransactionType: 'Payment',
      Account: agent.address,
      Destination: agent.address,
      Amount: destAmount, // min-receive floor (dest token)
      SendMax: sendMax, // max-spend ceiling (XRP drops or token)
      Flags: tfNoPartial, // tfPartialPayment OFF
    },
    agent
  );
}
