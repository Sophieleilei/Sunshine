// Level-1 liquidity setup (one-time), XRP-bridge version. Stands up the actors that
// exist on mainnet so the agent's swap has real liquidity:
//   - BANK issues the INR token to MM
//   - MM posts an XRP/INR AMM pool (the market maker)
//   - ALICE funds the AGENT with XRP (the per-invoice bridge value)
// XRP needs no issuer/trustline, so the stablecoin issuer is gone entirely.
import { xrpToDrops } from 'xrpl';
import { config } from '../config.js';
import { log } from '../util/log.js';
import { walletFromSeed, submit, disconnect } from '../xrpl/client.js';
import { setTrustLine } from '../modules/trustline.js';
import { snapshot } from '../util/balances.js';

const tok = (currency, issuer, value) => ({ currency, issuer, value: String(value) });

async function pay(fromWallet, to, amount) {
  return submit(
    { TransactionType: 'Payment', Account: fromWallet.address, Destination: to, Amount: amount },
    fromWallet
  );
}

async function main() {
  const agent = walletFromSeed(config.seeds.agent);
  const alice = walletFromSeed(config.seeds.alice);
  const mm = walletFromSeed(config.seeds.mm);
  const bank = walletFromSeed(config.seeds.bank);

  const INR = config.target.currency;
  const inrIss = config.target.issuer;
  const rate = config.xrpInr; // INR per 1 XRP

  // Pool sizing: MM seeds POOL_XRP and the matching INR at the demo rate.
  const POOL_XRP = 80;
  const POOL_INR = POOL_XRP * rate;

  log.step('0. Enable DefaultRipple on the bank (INR issuer) so INR can ripple/AMM');
  await submit({ TransactionType: 'AccountSet', Account: bank.address, SetFlag: 8 }, bank);

  log.step('1. Trust lines to INR (agent + MM). XRP needs none.');
  await setTrustLine(agent, { currency: INR, issuer: inrIss });
  await setTrustLine(mm, { currency: INR, issuer: inrIss });

  log.step('2. Bank issues INR to MM (for the pool)');
  await pay(bank, mm.address, tok(INR, inrIss, POOL_INR));

  log.step('3. Alice funds the agent with XRP (per-invoice bridge value)');
  await pay(alice, agent.address, xrpToDrops('30'));

  log.step(`4. MM posts the XRP/INR AMM pool (${POOL_XRP} XRP / ${POOL_INR} INR)`);
  await submit(
    {
      TransactionType: 'AMMCreate',
      Account: mm.address,
      Amount: xrpToDrops(String(POOL_XRP)),
      Amount2: tok(INR, inrIss, POOL_INR),
      TradingFee: 500, // 0.5%
      Fee: '2000000', // AMMCreate special one-time fee
    },
    mm
  );

  await snapshot('after seed', {
    AGENT: agent.address,
    ALICE: alice.address,
    MM: mm.address,
    BANK: bank.address,
  });

  log.ok('liquidity seeded (XRP/INR) — ready for `npm run demo`');
  await disconnect();
}

main().catch(async (e) => {
  log.err('seed failed', { error: e.message });
  await disconnect();
  process.exit(1);
});
