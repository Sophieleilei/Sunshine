// Helpers for putting state on-ledger. MPT metadata is immutable, so mutable
// settlement state (FX rate, status, KYA verdict) rides in Payment Memos
// (Risk A decision in PLAN.md).

export const toHex = (s) => Buffer.from(s, 'utf8').toString('hex').toUpperCase();
export const fromHex = (h) => Buffer.from(h, 'hex').toString('utf8');

// Build a single XRPL Memo object from a JS object.
export function jsonMemo(obj, { type = 'fx-agent/state' } = {}) {
  return {
    Memo: {
      MemoType: toHex(type),
      MemoData: toHex(JSON.stringify(obj)),
    },
  };
}
