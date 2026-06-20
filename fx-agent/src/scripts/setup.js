// One-time setup: faucet-fund all five Testnet accounts and print seeds for .env.
//   AGENT  – the autonomous orchestrator
//   ALICE  – sender, holds the bridge stablecoin
//   MM     – market maker (seeds the AMM)
//   BANK   – issues the target (INR) token, redeems at payout
//   STABLE_ISSUER – issues the bridge stablecoin (stands in for RLUSD)
import { getClient, disconnect } from '../xrpl/client.js';
import { log } from '../util/log.js';

async function fundOne(client, label) {
  const { wallet, balance } = await client.fundWallet();
  log.ok(`${label} funded`, { address: wallet.address, balanceXRP: balance });
  return wallet;
}

async function main() {
  const client = await getClient();
  log.step('Faucet-funding 5 accounts (Testnet)');

  const agent = await fundOne(client, 'AGENT');
  const alice = await fundOne(client, 'ALICE');
  const mm = await fundOne(client, 'MM');
  const bank = await fundOne(client, 'BANK');
  const stableIssuer = await fundOne(client, 'STABLE_ISSUER');

  console.log('\n--- paste into .env ---');
  console.log(`AGENT_SEED=${agent.seed}`);
  console.log(`ALICE_SEED=${alice.seed}`);
  console.log(`MM_SEED=${mm.seed}`);
  console.log(`BANK_SEED=${bank.seed}`);
  console.log(`STABLE_ISSUER_SEED=${stableIssuer.seed}`);
  console.log('-----------------------\n');
  console.log('Next: `npm run seed`  (issues tokens + seeds the AMM), then `npm run demo`.');

  await disconnect();
}

main().catch((e) => {
  log.err('setup failed', { error: e.message });
  process.exit(1);
});
