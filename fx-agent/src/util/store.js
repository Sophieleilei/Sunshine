import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

// File-backed settlement log so the dashboard shows settlements regardless of which
// process produced them (the HTTP server OR the MCP server spawned by Claude Desktop).
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const FILE = path.join(__dirname, '..', '..', 'out', 'settlements.json');

export function recordSettlement(s) {
  fs.mkdirSync(path.dirname(FILE), { recursive: true });
  const all = readAll();
  all.unshift({ ts: new Date().toISOString(), ...s });
  fs.writeFileSync(FILE, JSON.stringify(all.slice(0, 50), null, 2));
}

export function readAll() {
  try {
    return JSON.parse(fs.readFileSync(FILE, 'utf8'));
  } catch {
    return [];
  }
}
