// Tiny structured logger. Every settlement step is logged and keyed to the MPT
// issuance id so the log doubles as the off-ledger audit record (Risk A decision).
const ts = () => new Date().toISOString();

export const log = {
  step: (name, data = {}) => console.log(`\n[STEP] ${ts()} ${name}`, fmt(data)),
  info: (msg, data = {}) => console.log(`  · ${msg}`, fmt(data)),
  ok: (msg, data = {}) => console.log(`  ✓ ${msg}`, fmt(data)),
  warn: (msg, data = {}) => console.warn(`  ! ${msg}`, fmt(data)),
  err: (msg, data = {}) => console.error(`  ✗ ${msg}`, fmt(data)),
};

function fmt(data) {
  return Object.keys(data).length ? JSON.stringify(data) : '';
}
