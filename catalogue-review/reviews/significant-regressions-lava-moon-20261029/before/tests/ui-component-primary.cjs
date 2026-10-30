const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),test=require('node:test');
const copy=x=>JSON.parse(JSON.stringify(x));
const fixture=()=>({image:{id:'id:photo',name:'photo.png',family:'Frozen Fish',types:['product']},content_hash:'original-bytes',rows:[
  {product_id:'A',name:'Frozen Fish White',family:'Frozen Fish',shown:true,listing:false,primary:false,advertising:false,image_version:0},
  {product_id:'B',name:'Frozen Fish Verdigris',family:'Frozen Fish',shown:false,listing:false,primary:false,advertising:false,image_version:0}
]});
function harness(saved={}){
  const nodes=new Map(),listeners={},messages=[],storage=new Map(Object.entries(saved));
  const node=s=>{if(!nodes.has(s))nodes.set(s,{innerHTML:'',textContent:'',value:'',open:false,disabled:false,
    querySelectorAll:()=>[],addEventListener(){},showModal(){this.open=true;},close(){this.open=false;},setAttribute(){},removeAttribute(){},classList:{toggle(){}}});return nodes.get(s);};
  const c=vm.createContext({console,URL,URLSearchParams,FormData:class{},document:{querySelector:node,querySelectorAll:()=>[],addEventListener:(k,f)=>(listeners[k]||=[]).push(f)},
    window:{addEventListener(){},confirm:()=>false},location:{hash:'#library'},history:{replaceState(){}},
    localStorage:{getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,v)},setTimeout(){},clearTimeout(){},setInterval(){},clearInterval(){}});
  const run=s=>vm.runInContext(s,c);
  for(const file of ['app.js','image-tools.js','family-tools.js','component-tools.js'])run(fs.readFileSync(path.join(__dirname,'../static',file),'utf8').replace(/\nboot\(\);\s*$/,'\n'));
  c.report=m=>messages.push(m);let refreshed=0;
  c.refresh=async()=>{refreshed++;};
  run("state.pid='__library__';state.request=1;state.library={images:[]};state.boot={products:[],image_types:{},families:[]};toast=report;scheduleCoverageRefresh=()=>{};holdImageOrder=()=>{};refreshAfterTransfer=refresh;");
  c.api=async()=>copy(fixture());
  function change(pid,key,checked){c.event={target:{dataset:{componentPid:pid,componentChoice:key},checked,closest:()=>null}};for(const fn of listeners.change||[])fn(c.event);}
  return {run,c,node,listeners,messages,storage,change,refreshes:()=>refreshed,open:()=>run("openComponents('id:photo')")};
}

test('new browser starts with component sculptures, not installation folders',()=>{
  assert.equal(harness().run('sidebarMode'),'components');
});
test('an explicit folder or component preference is still respected',()=>{
  for(const mode of ['folders','components'])assert.equal(harness({'boldstone.review.sidebarMode.v1':mode}).run('sidebarMode'),mode);
});
test('library chooser requests and renders the saved Primary value',async()=>{
  const h=harness(),saved=fixture(),reads=[];saved.rows[0].primary=true;saved.rows[0].listing=true;
  h.c.api=async url=>{reads.push(url);return copy(saved);};await h.open();
  assert.match(reads[0],/&primary=1$/);assert.equal(h.run('componentReview.rows[0].primary'),true);
  assert.match(h.node('#component-dialog').innerHTML,/<th>Primary<\/th>/);
  assert.match(h.node('#component-rows').innerHTML,/aria-label="Primary for Frozen Fish White" checked/);
  assert.equal(h.run('componentChanges().length'),0);
});
test('selecting Primary attaches only the chosen component and selects Listing',async()=>{
  const h=harness();await h.open();h.change('B','primary',true);
  assert.deepEqual(copy(h.run('componentChanges().map(r=>[r.product_id,r.shown,r.listing,r.primary,r.advertising])')),[['B',true,true,true,false]]);
});
test('removing Primary keeps Listing and Ads; removing Listing clears only Primary',async()=>{
  const h=harness();await h.open();h.change('A','primary',true);h.change('A','advertising',true);h.change('A','primary',false);
  assert.deepEqual(copy(h.run('componentReview.rows.map(r=>[r.listing,r.primary,r.advertising])'))[0],[true,false,true]);
  h.change('A','primary',true);h.change('A','listing',false);
  assert.deepEqual(copy(h.run('componentReview.rows.map(r=>[r.listing,r.primary,r.advertising])'))[0],[false,false,true]);
});
test('removing Show clears component uses and does not change another component',async()=>{
  const h=harness();await h.open();for(const pid of ['A','B']){h.change(pid,'primary',true);h.change(pid,'advertising',true);}
  h.change('A','shown',false);
  assert.deepEqual(copy(h.run('componentReview.rows.map(r=>[r.shown,r.listing,r.primary,r.advertising])')),[[false,false,false,false],[true,true,true,true]]);
});
test('Listing shortcut clears a former Primary; Ads shortcut retains it',async()=>{
  for(const purpose of ['listing','advertising']){
    const h=harness(),saved=fixture();saved.rows[0].listing=true;saved.rows[0].primary=true;
    h.c.api=async()=>copy(saved);await h.run("openComponents('id:photo','"+purpose+"')");
    assert.equal(h.run('componentReview.rows[0].primary'),purpose==='advertising');
    assert.equal(h.run('componentReview.rows[1].shown'),false);
  }
});
test('primary is not automatically selected for every component when opening the chooser',async()=>{
  const h=harness();await h.run("openComponents('id:photo','primary')");assert.equal(h.run('componentChanges().length'),0);
});
test('Primary alone counts as a dirty edit and cannot be dismissed by X unnoticed',async()=>{
  const h=harness(),saved=fixture();saved.rows[0].listing=true;h.c.api=async()=>copy(saved);await h.open();h.change('A','primary',true);
  assert.equal(h.run("state.dirty.has('component-review')"),true);assert.equal(h.node('#component-save').disabled,false);
  h.run('closeComponents()');assert.equal(h.node('#component-dialog').open,true);
});
test('multi-component save submits exact Primary choices and displayed content hash once',async()=>{
  const h=harness();await h.open();h.change('A','primary',true);h.change('B','advertising',true);
  const calls=[];let release;h.c.api=async(url,body)=>{calls.push({url,body:copy(body)});return new Promise(resolve=>release=resolve);};
  const save=h.run('saveComponents()');await h.run('saveComponents()');h.change('A','primary',false);
  assert.equal(calls.length,1);assert.equal(calls[0].body.content_hash,'original-bytes');
  assert.deepEqual(calls[0].body.rows.map(r=>[r.product_id,r.primary,r.advertising]),[['A',true,false],['B',false,true]]);
  assert.equal(h.run('componentReview.rows[0].primary'),true);release({});await save;
  assert.equal(h.refreshes(),1);assert.equal(h.node('#component-dialog').open,false);
});
test('response lost after commit is confirmed by readback without replaying the write',async()=>{
  const h=harness();await h.open();h.change('A','primary',true);let writes=0,reads=0,saved=fixture();
  h.c.api=async(url,body)=>{if(body){writes++;saved.rows[0]={...body.rows[0]};throw Error('Response lost');}reads++;return copy(saved);};
  await h.run('saveComponents()');assert.equal(writes,1);assert.equal(reads,1);
  assert.equal(h.node('#component-dialog').open,false);assert.equal(h.refreshes(),1);assert.match(h.messages[0],/saved/);
});
test('unconfirmed or stale save retains the draft and blocks retry until fresh read',async()=>{
  const h=harness();await h.open();h.change('A','primary',true);let writes=0;
  h.c.api=async(url,body)=>{if(body){writes++;throw Error('Newer edit in another tab');}return fixture();};
  await h.run('saveComponents()');await h.run('saveComponents()');
  assert.equal(writes,1);assert.equal(h.run('componentReview.rows[0].primary'),true);assert.equal(h.run('componentReview.needsRefresh'),true);
  assert.equal(h.node('#component-save').disabled,true);assert.match(h.node('#component-result').innerHTML,/Reload saved choices/);
  assert.equal(h.messages.length,0);assert.equal(h.node('#component-dialog').open,true);
});
test('readback of different image bytes cannot confirm a lost save',async()=>{
  const h=harness();await h.open();h.change('A','primary',true);const saved=fixture();
  h.c.api=async(url,body)=>{if(body){saved.rows[0]={...body.rows[0]};throw Error('Response lost');}return {...saved,content_hash:'changed-bytes'};};
  await h.run('saveComponents()');assert.equal(h.run('componentReview.needsRefresh'),true);assert.equal(h.refreshes(),0);
});
test('successful save followed by gallery failure is reported as saved, not offered for replay',async()=>{
  const h=harness();await h.open();h.change('A','primary',true);let writes=0;
  h.c.api=async()=>{writes++;return {};};h.c.refreshAfterTransfer=async()=>{throw Error('Gallery unavailable');};
  await h.run('saveComponents()');assert.equal(writes,1);assert.equal(h.node('#component-dialog').open,false);
  assert.match(h.messages[0],/were saved.*Reload/);
});
