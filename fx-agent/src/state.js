// Orchestrator states (screen-first, escrow-free flow).
export const S = Object.freeze({
  ISSUED: 'ISSUED',
  MINTED: 'MINTED',
  KYA: 'KYA',
  CONVERTED: 'CONVERTED',
  PAID: 'PAID',
  REVERTED: 'REVERTED',
  FAILED: 'FAILED',
});

// In-memory settlement record. Mirrors what we also stamp into Memos on-ledger
// (Risk A: MPT metadata is immutable, mutable state lives here + in Memos).
export function newSettlement(invoice) {
  return {
    status: S.ISSUED,
    invoice,
    mptIssuanceId: null,
    kyaVerdict: null,
    stableSpent: null,
    fxRate: null,
    convertedAmount: null,
    convertHash: null,
    payoutHash: null,
    revertHash: null,
    history: [{ at: new Date().toISOString(), status: S.ISSUED }],
  };
}

export function transition(settlement, status, patch = {}) {
  Object.assign(settlement, patch, { status });
  settlement.history.push({ at: new Date().toISOString(), status });
  return settlement;
}
