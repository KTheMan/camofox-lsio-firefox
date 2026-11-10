// Run only in a fresh isolated candidate container. No production or real vault.
import fs from 'node:fs';
import http from 'node:http';
import { spawn } from 'node:child_process';
if (process.env.CAMOFOX_REVIEW_FIXTURES !== '1' || process.env.CAMOFOX_API_KEY !== 'candidate-review-dummy-key') throw new Error('Use an isolated review container with the dummy key');
const base = 'http://127.0.0.1:9377';
const headers = { Authorization: 'Bearer candidate-review-dummy-key', 'Content-Type': 'application/json' };
const results = [];
function record(test, passed, detail = {}) {
  results.push({ test, passed, ...detail });
  fs.writeFileSync('/tmp/r2-verification.json', JSON.stringify(results, null, 2));
  console.log(JSON.stringify({ test, passed, ...detail }));
}
async function api(method, path, body, authenticated = true) {
  const res = await fetch(base+path, { method, headers: authenticated ? headers : { 'Content-Type': 'application/json' }, body: body === undefined ? undefined : JSON.stringify(body), signal: AbortSignal.timeout(45000) });
  return { status: res.status, body: await res.json() };
}
const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
const initial = await api('GET', '/health');
record('fresh_browser_has_no_user_tabs', initial.body.activeTabs === 0);
const bw = await api('POST', '/bitwarden/status', { userId: 'review' });
record('first_bitwarden_status_without_manual_setup', bw.status === 200 && bw.body.ok && ['login_start','logged_out','locked'].includes(bw.body.state), { state: bw.body.state });
for (const path of ['/tabs?userId=review', '/TABS/?userId=review', '/snapshot?userId=review']) {
  const r = await api('GET', path, undefined, false); record('unauthenticated_control_rejected', r.status === 401, { path, status: r.status });
}
const mainHtml = `<title>Review fixture</title><form><label>Password<input id=p type=password value=DUMMY-PASS-123456></label><label>Ordinary<input id=o name=ordinary value=ordinary-visible></label><input name=code autocomplete=one-time-code value=DUMMY-OTP-123456><input aria-label="API key" value=DUMMY-API-123456><select name=api_key aria-label="API key selector"><option value=DUMMY-OPTION-KEY>DUMMY-OPTION-LABEL</option></select><textarea name=secret>DUMMY-MULTILINE
secret</textarea><button aria-labelledby=p>Submit</button></form><div id=shadow></div><iframe src=http://127.0.0.1:18081/inner></iframe><iframe src=http://127.0.0.1:18081/recaptcha/api2/bframe></iframe><script>document.querySelector('#shadow').attachShadow({mode:'open'}).innerHTML='<input type=password value=DUMMY-SHADOW-123456>';</script>`;
const fixture = http.createServer((q,s) => { s.setHeader('Content-Type','text/html'); s.end(q.url.startsWith('/search') ? '<title>Google fixture</title><input type=password name=q value=DUMMY-GOOGLE-123456><div id=rso><h3>Local result</h3></div>' : mainHtml); });
const frame = http.createServer((q,s) => { s.setHeader('Content-Type','text/html'); s.end(q.url.includes('recaptcha') ? '<button>Controlled human challenge</button>' : '<input type=password value=DUMMY-IFRAME-123456>'); });
await new Promise(resolve => fixture.listen(18080,'0.0.0.0',resolve));
await new Promise(resolve => frame.listen(18081,'127.0.0.1',resolve));
const created = await api('POST','/tabs',{ userId:'review',sessionKey:'fixture',url:'http://127.0.0.1:18080' });
const tab = created.body.tabId;
record('authorized_tab_creation', created.status === 200 && !!tab);
const snap = await api('GET',`/tabs/${tab}/snapshot?userId=review`);
record('all_snapshot_representations_private', snap.status === 200 && !JSON.stringify(snap.body).includes('DUMMY-') && JSON.stringify(snap.body).includes('ordinary-visible'));
record('snapshot_exposes_captcha_handoff_signal', snap.body.humanChallenge?.detected === true);
const legacy = await api('GET',`/snapshot?userId=review&targetId=${tab}`);
record('legacy_snapshot_private', legacy.status === 200 && !JSON.stringify(legacy.body).includes('DUMMY-'));
const dom = await api('POST',`/tabs/${tab}/evaluate`,{userId:'review',expression:`document.querySelector('#p').value==='DUMMY-PASS-123456'&&document.querySelector('#o').value==='ordinary-visible'`});
record('masking_preserves_actual_dom', dom.body.result === true);

const shot=await fetch(base+`/tabs/${tab}/screenshot?userId=review`,{headers,signal:AbortSignal.timeout(45000)});
const shotData=Buffer.from(await shot.arrayBuffer()).toString('base64');
const pixels=await api('POST',`/tabs/${tab}/evaluate`,{userId:'review',expression:`(async()=>{const image=new Image();image.src='data:image/png;base64,${shotData}';await image.decode();const c=document.createElement('canvas');c.width=image.width;c.height=image.height;const x=c.getContext('2d');x.drawImage(image,0,0);return ['p','o'].every(id=>{const r=document.getElementById(id).getBoundingClientRect();const d=x.getImageData(Math.floor(r.x+r.width/2),Math.floor(r.y+r.height/2),1,1).data;return d[0]===255&&d[1]===0&&d[2]===255})})()`});
record('screenshot_masks_editable_controls',shot.status===200&&pixels.body.result===true);

const google = await api('POST','/tabs',{ userId:'google-review',sessionKey:'google-fixture',url:'http://www.google.com:18080/search?q=fixture' });
const gs = await api('GET',`/tabs/${google.body.tabId}/snapshot?userId=google-review`);
record('google_fastpath_private', gs.status === 200 && !JSON.stringify(gs.body).includes('DUMMY-GOOGLE'), {status:gs.status});
await api('DELETE',`/tabs/${google.body.tabId}?userId=google-review`);
const tokens = JSON.parse(fs.readFileSync('/review-fixtures/tokens.json','utf8'));
const edgeHost = process.env.CAMOFOX_REVIEW_EDGE;
for (const [name, token] of [['missing',null],['forged','not-a-jwt'],['wrongAudience',tokens.wrongAudience],['expired',tokens.expired],['valid',tokens.valid]]) {
  const status = await new Promise((resolve,reject) => {
    const req = http.get({host:edgeHost,port:8080,path:'/',headers:{Host:'camofox.example.invalid',...(token?{'Cf-Access-Jwt-Assertion':token}:{})}},res=>{res.resume();res.on('end',()=>resolve(res.statusCode));});
    req.on('error',reject);req.setTimeout(10000,()=>req.destroy(new Error('edge timeout')));
  });
  record(`edge_${name}`,status===(name==='valid'?200:403),{status});
}
for (const [name, token] of [['forged','not-a-jwt'],['valid',tokens.valid]]) {
  const status = await new Promise((resolve,reject) => {
    const req=http.request({host:edgeHost,port:8080,path:'/api/websockets',headers:{Host:'camofox.example.invalid',Origin:'https://camofox.example.invalid','Cf-Access-Jwt-Assertion':token,Connection:'Upgrade',Upgrade:'websocket','Sec-WebSocket-Version':'13','Sec-WebSocket-Key':'dGhlIHNhbXBsZSBub25jZQ=='}},res=>{res.resume();resolve(res.statusCode);});
    req.on('upgrade',(res,socket)=>{socket.destroy();resolve(res.statusCode);}); req.on('error',reject); req.setTimeout(10000,()=>req.destroy(new Error('upgrade timeout')));req.end();
  }); record(`edge_websocket_${name}`,status===(name==='valid'?101:403),{status});
}
const raw=await api('POST','/bitwarden/unlock',{userId:'review',masterPassword:'DUMMY-REJECTED'});
record('http_password_payload_rejected',raw.status===400);
const op=await api('POST','/bitwarden/unlock',{userId:'review'});
record('opaque_unlock_operation',op.status===202&&op.body.state==='awaiting_secret'&&!JSON.stringify(op.body).includes('masterPassword'));
const cancelled=await api('POST','/bitwarden/cancel',{userId:'review',operationId:op.body.operationId});
record('pending_unlock_cancelled_without_secret',cancelled.body.state==='cancelled');
const lease=await api('POST',`/tabs/${tab}/handoff`,{userId:'review',reason:'captcha',ttlSeconds:180});
record('human_handoff_preserves_same_tab',lease.status===200&&lease.body.tabId===tab&&lease.body.challenge.detected);
for (const [method,path,body] of [['GET',`/tabs/${tab}/snapshot?userId=review`],['POST',`/tabs/${tab}/evaluate`,{userId:'review',expression:'1'}],['POST','/tabs',{userId:'other'}],['GET',`/TABS/${tab}/SCREENSHOT/?userId=review`],['DELETE','/sessions/review']]) {
  const r=await api(method,path,body);record('human_excludes_competing_control',r.status===409,{method,path});
}
console.log(JSON.stringify({phase:'waiting_for_actual_reaper_tick'}));
await wait(35000); console.log(JSON.stringify({phase:'lease_still_waiting'})); await wait(30000);
const after=await api('GET',`/tabs/${tab}/handoff?userId=review`);
record('lease_survives_actual_cleanup_tick',after.status===200&&after.body.leaseId===lease.body.leaseId);
const unconfirmed=await api('POST',`/tabs/${tab}/handoff/resume`,{userId:'review',leaseId:lease.body.leaseId});
record('resume_requires_human_confirmation',unconfirmed.status===400);
const resumed=await api('POST',`/tabs/${tab}/handoff/resume`,{userId:'review',leaseId:lease.body.leaseId,humanConfirmed:true});
const retained=await api('GET',`/tabs/${tab}/snapshot?userId=review`);
record('confirmed_resume_retains_private_tab',resumed.status===200&&retained.status===200&&!JSON.stringify(retained.body).includes('DUMMY-'));
// Exercise actual MCP transport and the new tool schemas with a stable identity.
const mcp=spawn('node',['/opt/camofox-browser/mcp/server.mjs'],{env:{...process.env,CAMOFOX_BASE_URL:base,CAMOFOX_USER_ID:'review-mcp',CAMOFOX_SESSION_KEY:'fixture'},stdio:['pipe','pipe','ignore']});
let buffer='',seq=0;const pending=new Map();mcp.stdout.on('data',data=>{buffer+=data;let i;while((i=buffer.indexOf('\n'))>=0){let row=JSON.parse(buffer.slice(0,i));buffer=buffer.slice(i+1);if(pending.has(row.id)){pending.get(row.id)(row);pending.delete(row.id);}}});
const rpc=(method,params)=>{let id=++seq;return new Promise((resolve,reject)=>{let timer=setTimeout(()=>reject(new Error('MCP timeout')),15000);pending.set(id,x=>{clearTimeout(timer);resolve(x.result);});mcp.stdin.write(JSON.stringify({jsonrpc:'2.0',id,method,params})+'\n');});};
await rpc('initialize',{protocolVersion:'2024-11-05',capabilities:{},clientInfo:{name:'isolated-review',version:'1'}});
mcp.stdin.write(JSON.stringify({jsonrpc:'2.0',method:'notifications/initialized'})+'\n');
const tools=await rpc('tools/list',{});record('mcp_22_typed_tools',tools.tools.length===22);
const call=(name,args)=>rpc('tools/call',{name,arguments:args});const value=r=>JSON.parse(r.content[0].text);
const mt=value(await call('camofox_create_tab',{url:'http://127.0.0.1:18080'}));
const ml=value(await call('camofox_request_handoff',{tabId:mt.tabId,reason:'manual',ttlSeconds:180}));
const blocked=await call('camofox_snapshot',{tabId:mt.tabId});
record('mcp_handoff_blocks_snapshot',blocked.isError===true);
const mr=await call('camofox_resume_handoff',{tabId:mt.tabId,leaseId:ml.leaseId,humanConfirmed:true});
record('mcp_confirmed_resume',mr.isError!==true);
await call('camofox_close_tab',{tabId:mt.tabId});mcp.kill();
fixture.close();frame.close();
console.log(JSON.stringify({passed:results.filter(r=>r.passed).length,total:results.length}));
process.exit(results.every(r=>r.passed)?0:1);
