import http from 'http';
import { readAll } from './util/store.js';

// Localhost dashboard showing the settlement flow (MINT -> KYA -> CONVERT -> PAYOUT,
// or REVERT) with tx hashes + Testnet explorer links. Served by the HTTP server and/or
// the MCP server. The page polls /api/settlements.

function page() {
  return `<!doctype html><html><head><meta charset="utf-8"/>
<title>FX Agent — Settlement Dashboard</title>
<style>
  :root{--bg:#0d1117;--card:#161b22;--bd:#30363d;--tx:#e6edf3;--mut:#8b949e;
        --ok:#3fb950;--info:#58a6ff;--warn:#d29922;--bad:#f85149}
  *{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--tx);
    font-family:ui-sans-serif,system-ui,Segoe UI,Roboto,sans-serif}
  header{padding:18px 24px;border-bottom:1px solid var(--bd);display:flex;align-items:center;gap:10px}
  header h1{font-size:16px;margin:0;font-weight:600}
  .tag{font-size:12px;color:var(--mut);background:var(--card);border:1px solid var(--bd);
       padding:3px 8px;border-radius:6px}
  .wrap{max-width:980px;margin:0 auto;padding:20px 24px}
  .empty{color:var(--mut);padding:40px;text-align:center}
  .card{background:var(--card);border:1px solid var(--bd);border-radius:10px;padding:14px 16px;margin-bottom:14px}
  .top{display:flex;align-items:center;gap:10px;margin-bottom:12px;flex-wrap:wrap}
  .top .id{font-family:ui-monospace,monospace;font-size:13px}
  .top .ts{color:var(--mut);font-size:12px;margin-left:auto}
  .badge{font-size:11px;font-weight:600;padding:3px 9px;border-radius:6px}
  .b-PAID{background:rgba(63,185,80,.15);color:var(--ok)}
  .b-REVERTED{background:rgba(210,153,34,.15);color:var(--warn)}
  .b-FAILED{background:rgba(248,81,73,.15);color:var(--bad)}
  .flow{display:flex;align-items:stretch;gap:0;flex-wrap:wrap}
  .step{flex:1;min-width:120px;border:1px solid var(--bd);border-radius:8px;padding:9px 11px;margin:3px}
  .step .k{font-size:10px;letter-spacing:.06em;color:var(--mut);text-transform:uppercase}
  .step .v{font-size:13px;margin-top:3px;word-break:break-word}
  .step.ok{border-color:rgba(63,185,80,.5)}
  .step.warn{border-color:rgba(210,153,34,.5)}
  .step.skip{opacity:.45}
  a{color:var(--info);text-decoration:none;font-size:12px} a:hover{text-decoration:underline}
  .arrow{display:flex;align-items:center;color:var(--mut);font-size:18px}
</style></head><body>
<header><h1>⚡ FX Agent — Settlement Dashboard</h1>
  <span class="tag">XRPL Testnet · live</span>
  <span class="tag" id="count">—</span></header>
<div class="wrap"><div id="list" class="empty">loading…</div></div>
<script>
const ex = (h)=>h?('<a href="https://testnet.xrpl.org/transactions/'+h+'" target="_blank">'+h.slice(0,10)+'… ↗</a>'):'';
function step(cls,k,v){return '<div class="step '+cls+'"><div class="k">'+k+'</div><div class="v">'+v+'</div></div>';}
function arrow(){return '<div class="arrow">→</div>';}
function card(s){
  const paid=s.status==='PAID', rev=s.status==='REVERTED';
  const steps=[];
  steps.push(step('ok','1 · Mint MPT', (s.mptIssuanceId||'').slice(0,10)+'…'));
  steps.push(step(rev?'warn':'ok','2 · KYA', (s.kya&&s.kya.decision)||'—'));
  if(rev){
    steps.push(step('warn','3 · Revert','XRP → sender<br>'+ex(s.revert&&s.revert.tx)));
    steps.push(step('skip','4 · Payout','— skipped'));
  } else {
    steps.push(step('ok','3 · Convert',(s.convert&&s.convert.received||'—')+'<br>'+ex(s.convert&&s.convert.tx)));
    steps.push(step('ok','4 · Payout','bank '+((s.settle&&s.settle.paidToBank||'').slice(0,8))+'…<br>'+ex(s.settle&&s.settle.tx)));
  }
  const flow=steps.map((h,i)=> h + (i<steps.length-1?arrow():'')).join('');
  return '<div class="card"><div class="top"><span class="id">'+(s.invoiceId||'invoice')+
    '</span><span class="badge b-'+s.status+'">'+s.status+'</span>'+
    '<span class="ts">'+new Date(s.ts).toLocaleString()+'</span></div>'+
    '<div class="flow">'+flow+'</div></div>';
}
async function refresh(){
  try{
    const r=await fetch('/api/settlements'); const data=await r.json();
    document.getElementById('count').textContent=data.length+' settlement'+(data.length===1?'':'s');
    const el=document.getElementById('list');
    el.className=data.length?'':'empty';
    el.innerHTML=data.length?data.map(card).join(''):'no settlements yet — run one from Claude or the pipeline';
  }catch(e){}
}
refresh(); setInterval(refresh,3000);
</script></body></html>`;
}

// Handle dashboard routes on an existing server. Returns true if it handled the request.
export function handleDashboard(req, res) {
  if (req.method === 'GET' && (req.url === '/' || req.url === '/dashboard')) {
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    res.end(page());
    return true;
  }
  if (req.method === 'GET' && req.url === '/api/settlements') {
    res.writeHead(200, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' });
    res.end(JSON.stringify(readAll()));
    return true;
  }
  return false;
}

// Standalone dashboard server (used by the MCP process). Silently no-ops if the port is
// already in use (e.g. the HTTP server.js is already serving the dashboard).
export function startStandaloneDashboard(port) {
  const server = http.createServer((req, res) => {
    if (!handleDashboard(req, res)) {
      res.writeHead(404);
      res.end();
    }
  });
  server.on('error', () => {});
  server.listen(port);
  return server;
}
