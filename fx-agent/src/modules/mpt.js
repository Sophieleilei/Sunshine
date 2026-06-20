import { submit } from '../xrpl/client.js';
import { toHex } from '../util/hex.js';
import { log } from '../util/log.js';

// MPT issuance flags (XRPL). The flow needs transfer + escrow + trade + clawback.
export const MPT_FLAGS = {
  CanLock: 0x0002,
  RequireAuth: 0x0004,
  CanEscrow: 0x0008, // HOLD path
  CanTrade: 0x0010, // if the MPT ever touches the DEX
  CanTransfer: 0x0020, // move between accounts
  CanClawback: 0x0040, // "claw credit" recovery on REJECT/error
};

// Step 2 — mint the invoice as an MPT. Metadata is IMMUTABLE; it holds the invoice
// anchor (hash + immutable reference fields) only. Mutable state goes in Memos.
export async function mintInvoiceMPT(agent, invoice) {
  const metadata = {
    kind: 'cross-border-invoice',
    invoiceId: invoice.id,
    invoiceHash: invoice.hash,
    src: { currency: invoice.srcCurrency, amount: invoice.amount },
    dueDate: invoice.dueDate,
  };

  const flags =
    MPT_FLAGS.CanTransfer | MPT_FLAGS.CanEscrow | MPT_FLAGS.CanTrade | MPT_FLAGS.CanClawback;

  log.info('minting invoice MPT', { invoiceId: invoice.id, flags });
  const res = await submit(
    {
      TransactionType: 'MPTokenIssuanceCreate',
      Account: agent.address,
      AssetScale: 2,
      MaximumAmount: '100000000',
      MPTokenMetadata: toHex(JSON.stringify(metadata)),
      Flags: flags,
    },
    agent
  );

  // Pull the issuance id out of the metadata (created node).
  const id = extractIssuanceId(res);
  log.ok('invoice MPT minted', { mptIssuanceId: id });
  return id;
}

// Holder opts in to hold an MPT.
export async function authorizeMPT(wallet, mptIssuanceId) {
  return submit(
    {
      TransactionType: 'MPTokenAuthorize',
      Account: wallet.address,
      MPTokenIssuanceID: mptIssuanceId,
    },
    wallet
  );
}

function extractIssuanceId(txResult) {
  const nodes = txResult.meta?.AffectedNodes || [];
  for (const n of nodes) {
    const created = n.CreatedNode;
    if (created?.LedgerEntryType === 'MPTokenIssuance') {
      return created.LedgerIndex; // issuance id
    }
  }
  // Some servers return it directly in meta.
  return txResult.meta?.mpt_issuance_id || null;
}
