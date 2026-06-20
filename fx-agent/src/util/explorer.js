// Testnet explorer links — the clickable proof for the demo.
export const txLink = (hash) => `https://testnet.xrpl.org/transactions/${hash}`;
export const acctLink = (addr) => `https://testnet.xrpl.org/accounts/${addr}`;

export function printTx(label, hash) {
  if (hash) console.log(`    🔗 ${label}: ${txLink(hash)}`);
}
