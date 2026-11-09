"""Loopback-only, read-only live queue UI. All actions remain in the CLI."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from urllib.parse import urlsplit

HTML = '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Research queue</title><link rel="stylesheet" href="/style.css"><script defer src="/app.js"></script></head><body>
<main><header><div><p class="eyebrow">RESEARCH OPERATIONS</p><h1>Research queue</h1><p id="project">Connecting to the orchestrator…</p></div><div id="heartbeat" class="badge">Connecting</div></header>
<p id="coordinator-error" role="status" class="muted"></p><section id="summary" class="summary"></section><section><h2>Workers &amp; storage</h2><div id="workers" class="workers"></div><p id="storage" class="muted"></p></section>
<section><div class="toolbar"><h2>Testing jobs</h2><input id="search" type="search" placeholder="Find a candidate, workflow or job" aria-label="Search jobs"><select id="filter" aria-label="Job filter"><option value="active">Active &amp; waiting</option><option value="all">All jobs</option><option value="finished">Finished</option></select></div><p id="message" class="muted"></p><div class="table"><table><thead><tr><th>Workflow / job</th><th>Status</th><th>Worker</th><th>Waiting for / result</th><th>Return to research</th></tr></thead><tbody id="jobs"></tbody></table></div></section>
<footer>Execution status and research outcomes are separate. A completed job does not establish improved trading performance. <span id="updated"></span></footer></main></body></html>'''

CSS = '''*{box-sizing:border-box}body{margin:0;background:#f5f7fa;color:#172436;font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}main{max-width:1500px;margin:auto;padding:36px}header,.toolbar{display:flex;align-items:center;justify-content:space-between;gap:20px}h1{font-size:34px;letter-spacing:-1px;margin:0}h2{font-size:18px;margin:0 0 14px}.eyebrow{font-size:11px;letter-spacing:2px;color:#53657c;font-weight:700;margin:0 0 6px}#project,.muted,footer{color:#65738a}.badge,.state{border-radius:20px;padding:5px 10px;background:#e8edf4;font-size:12px;white-space:nowrap}.good{background:#dff3e8;color:#196340}.warn{background:#fff0d7;color:#805417}.bad{background:#ffe5e5;color:#9f3030}.summary{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin:26px 0}.card{background:white;border:1px solid #dce3ec;border-radius:12px;padding:20px}.number{font-size:30px;line-height:1.2;margin-bottom:7px;font-weight:650}.label{color:#65738a}.workers{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px}.worker-title{display:flex;justify-content:space-between;font-weight:650;margin-bottom:10px}.worker-details{color:#566780;font-size:13px}section{margin-bottom:30px}.toolbar h2{margin:0;flex:1}input,select{font:inherit;border:1px solid #cbd5e2;border-radius:7px;background:white;padding:9px 12px}input{width:310px}.table{overflow:auto;border:1px solid #dce3ec;border-radius:10px;background:#fff}table{width:100%;border-collapse:collapse}th{text-align:left;font-size:11px;text-transform:uppercase;letter-spacing:.7px;color:#65738a;background:#fafbfd;white-space:nowrap}th,td{padding:13px 16px;border-bottom:1px solid #e8edf3;vertical-align:top}tr:last-child td{border-bottom:0}.name{font-weight:600;max-width:450px;overflow-wrap:anywhere}.small{font-size:12px;color:#6a7890;margin-top:4px;max-width:400px;overflow-wrap:anywhere}.reason{max-width:370px;overflow-wrap:anywhere}footer{font-size:12px;border-top:1px solid #dce3ec;padding-top:20px}#updated{display:block;margin-top:5px}@media(max-width:750px){main{padding:20px 14px}header,.toolbar{align-items:flex-start;flex-wrap:wrap}.summary{grid-template-columns:repeat(2,1fr)}input{width:100%}h1{font-size:28px}}'''

JS = '''const $=id=>document.getElementById(id);let state;const terminal=new Set(['succeeded','failed','interrupted','cancelled','skipped','blocked_dependency']);
function el(tag,text,cls){const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e}
const gib=x=>x===null||x===undefined?'unknown':(x/1073741824).toFixed(2)+' GiB';
function render(){if(!state)return;const rows=state.workflows.flatMap(w=>(w.jobs||[]).map(j=>({w,j})));const count=s=>rows.filter(({j})=>s.includes(j.state)).length;
$('project').textContent=state.project_id+' · durable queue · '+state.workflows.length+' workflows';
const stale=state.snapshot_age_seconds>15||state.state!=='running';$('heartbeat').textContent=stale?'Orchestrator offline or stale':'Live · refresh every 3s';$('heartbeat').className='badge '+(stale?'warn':'good');
$('coordinator-error').textContent=state.coordinator_error||((state.source_task_errors||[]).length?'Recent source service errors: '+state.source_task_errors.slice(-3).map(e=>e.workflow_id+' (exit '+e.exit_code+')').join('; '):'');
$('summary').replaceChildren(...[['Running now',count(['running'])],['Queued / waiting',rows.filter(({j})=>!terminal.has(j.state)&&j.state!=='running').length],['Execution succeeded',count(['succeeded'])],['Failed / interrupted',count(['failed','interrupted','blocked_dependency'])]].map(([label,n])=>{const c=el('div',undefined,'card');c.append(el('div',n,'number'),el('div',label,'label'));return c}));
$('workers').replaceChildren(...state.workers.map(w=>{const c=el('div',undefined,'card'),title=el('div',undefined,'worker-title');title.append(el('span',w.worker),el('span',w.retired?'Retired':w.stale?'Stale / unavailable':'Connected','badge '+(w.stale?'warn':'good')));c.append(title,el('div',w.retired?w.retired_reason:w.stale?'Current execution state unknown':`${w.running_jobs??'?'} / ${w.execution_slots??'?'} execution slots occupied`,'worker-details'),el('div',`Free: ${gib(w.free_bytes)} · reserve: ${gib(w.minimum_free_bytes)}`,'worker-details'));if(w.error)c.append(el('p',w.error,'small'));return c}));
const s=state.storage||{};$('storage').textContent=`Source host free: ${gib(s.host_free_bytes)} · evidence drive free: ${gib(s.bulk_free_bytes)} · evidence reserve: ${gib(s.bulk_minimum_free_bytes)}${s.stale?' · STORAGE OBSERVATION STALE':''}. Capacity checks also include each job's work and transfer allowance.`;
const query=$('search').value.toLowerCase(),filter=$('filter').value;const visible=rows.filter(({w,j})=>(filter==='all'||(filter==='finished')===terminal.has(j.state))&&[w.workflow_id,j.node_id,w.worker].join(' ').toLowerCase().includes(query));
$('message').textContent=`${visible.length} of ${rows.length} jobs shown. Waiting jobs start when their dependencies and worker capacity permit. Source transfer errors are retained for recovery.`;
$('jobs').replaceChildren(...visible.map(({w,j})=>{const tr=el('tr'),name=el('td');name.append(el('div',w.workflow_id,'name'),el('div',j.node_id+' · '+j.kind,'small'));const status=el('td');status.append(el('span',j.state.replaceAll('_',' '),'state '+(j.state==='succeeded'?'good':j.state==='failed'||j.state==='interrupted'?'bad':'warn')));if(j.stale)status.append(el('div',j.last_known_state?'Last known: '+j.last_known_state.replaceAll('_',' '):'Last known observation','small'));if(j.worker_phase){status.append(el('div','Last worker phase: '+j.worker_phase.phase.toLowerCase().replaceAll('_',' '),'small'),el('div','Phase recorded: '+new Date(j.worker_phase.updated_at*1000).toLocaleString(),'small'))}const reason=el('td',undefined,'reason');reason.append(el('div',(j.wait_reasons||[]).join(', ').replaceAll('_',' ')||j.error||(j.exit_code!==null&&j.exit_code!==undefined?'Exit '+j.exit_code:'—')));if(j.free_shortfall_bytes)reason.append(el('div','Needs '+gib(j.free_shortfall_bytes)+' more free space','small'));if(w.error)reason.append(el('div','Source: '+w.error,'small'));const ret=el('td');ret.append(el('div',w.phase.replaceAll('_',' ')),el('div',(w.publications?.length||0)+' published origin records','small'));tr.append(name,status,el('td',w.worker),reason,ret);return tr}));
$('updated').textContent='Snapshot: '+new Date(state.updated_at*1000).toLocaleString()+' · processing success does not imply scientific acceptance.';}
async function refresh(){try{const r=await fetch('/api/queue',{cache:'no-store'});if(!r.ok)throw Error('HTTP '+r.status);state=await r.json();render()}catch(e){$('heartbeat').textContent='Connection lost · showing last observation';$('heartbeat').className='badge bad'}finally{setTimeout(refresh,3000)}}
$('search').addEventListener('input',render);$('filter').addEventListener('change',render);refresh();'''


class Monitor(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, orchestrator):
        if address[0] not in {'127.0.0.1', 'localhost'}:
            raise ValueError('the read-only monitor must bind to loopback')
        self.orchestrator = orchestrator
        super().__init__(address, Handler)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_GET(self):
        host = urlsplit('//' + self.headers.get('Host', ''))
        try:
            allowed = host.hostname in {'localhost', '127.0.0.1'} and host.port == self.server.server_port
        except ValueError:
            allowed = False
        origin = self.headers.get('Origin')
        if origin and origin not in {f'http://localhost:{self.server.server_port}', f'http://127.0.0.1:{self.server.server_port}'}:
            allowed = False
        if not allowed:
            self.send_error(403); return
        if self.path == '/api/queue':
            content, mime = json.dumps(self.server.orchestrator.snapshot()).encode(), 'application/json'
        elif self.path in {'/', '/style.css', '/app.js'}:
            text, mime = {'/': (HTML, 'text/html'), '/style.css': (CSS, 'text/css'), '/app.js': (JS, 'text/javascript')}[self.path]
            content = text.encode()
        else:
            self.send_error(404); return
        self.send_response(200)
        self.send_header('Content-Type', mime + '; charset=utf-8')
        self.send_header('Content-Length', str(len(content)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(content)
