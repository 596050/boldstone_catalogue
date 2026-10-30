const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),test=require('node:test');
const tick=()=>new Promise(setImmediate);
function deferred(){let resolve,reject;const promise=new Promise((yes,no)=>{resolve=yes;reject=no;});return {promise,resolve,reject};}
function harness(){
  const nodes=new Map(),listeners={},messages=[],opened=[];let renders=0;
  const node=s=>{if(!nodes.has(s))nodes.set(s,{id:s.slice(1),innerHTML:'',textContent:'',value:'',open:false,disabled:false,elements:{rights:{value:'unknown'}},
    close(){this.open=false;},showModal(){this.open=true;},addEventListener(){},classList:{toggle(){}},querySelector:()=>null,querySelectorAll:()=>[]});return nodes.get(s);};
  const context=vm.createContext({console,URL,URLSearchParams,FormData:class{entries(){return [];}},
    document:{querySelector:node,querySelectorAll:()=>[],addEventListener:(type,fn)=>(listeners[type]||=[]).push(fn)},
    window:{addEventListener(){},confirm:()=>{throw Error('Unexpected discard prompt');}},location:{hash:'#A'},history:{replaceState(){}},
    localStorage:{getItem:()=>null,setItem(){}},setTimeout(){},clearTimeout(){},setInterval(){},clearInterval(){}});
  const run=s=>vm.runInContext(s,context);
  for(const name of ['app.js','image-tools.js'])run(fs.readFileSync(path.join(__dirname,'../static',name),'utf8').replace(/\nboot\(\);\s*$/,'\n'));
  context.report=message=>messages.push(message);context.draw=()=>{renders++;};
  run(`state.pid='A';state.request=1;state.boot={products:[{id:'A'},{id:'B'}],families:[],image_types:{product:'Product',in_situ:'In situ'}};
    state.current={id:'A',name:'Sculpture A',images:[{id:'one',name:'one.jpg',source:'Dropbox',types:['product'],original:{dropbox_content_hash:'old-hash'}}]};
    toast=report;renderGrid=draw;renderDeleteControl=()=>{};scheduleCoverageRefresh=()=>{};`);
  return {run,context,node,listeners,messages,opened,renders:()=>renders};
}
function slowReviews(h){
  const gate=deferred(),bodies=[],saved=new Map();
  h.context.api=async(url,body)=>{
    bodies.push(body);if(bodies.length===1)await gate.promise;
    const key=JSON.stringify([body.kind,body.product_id,body.item_id]),version=saved.get(key)?.version||0;
    if(body.version!==version)throw Error('Review changed; reload before saving');
    const result={...body,version:version+1};saved.set(key,result);return result;
  };
  return {gate,bodies,saved};
}

test('rapid Listing then Ads saves both purposes without a review conflict',async()=>{
  const h=harness(),s=slowReviews(h);
  const first=h.run("quick('one','listing')"),second=h.run("quick('one','advertising')");
  const done=Promise.allSettled([first,second]);s.gate.resolve();const results=await done;
  assert(results.every(r=>r.status==='fulfilled'),JSON.stringify(results));
  assert.deepEqual(JSON.parse(h.run("JSON.stringify(data('image','A','one').uses)")),['listing','advertising']);
  assert.deepEqual(s.bodies.map(b=>b.version),[0,1]);
});

test('repeated toggles execute in click order and keep other purposes',async()=>{
  const h=harness(),s=slowReviews(h);
  const actions=['listing','advertising','listing'].map(use=>h.run(`quick('one','${use}')`));
  const done=Promise.allSettled(actions);s.gate.resolve();const results=await done;
  assert(results.every(r=>r.status==='fulfilled'),JSON.stringify(results));
  assert.deepEqual(JSON.parse(h.run("JSON.stringify(data('image','A','one').uses)")),['advertising']);
});

test('a failed earlier choice prevents queued changes from overwriting an uncertain result',async()=>{
  const h=harness(),gate=deferred(),calls=[];
  h.context.api=async(url,body)=>{calls.push(body);await gate.promise;throw Error('Connection lost');};
  const done=Promise.allSettled([h.run("quick('one','listing')"),h.run("quick('one','advertising')")]);
  gate.resolve();const result=await done;
  assert.equal(calls.length,1);assert(result.every(r=>r.status==='rejected'));
  assert.match(result[1].reason.message,/previous|earlier/i);
});

test('different images and different sculptures are not blocked by one slow choice',async()=>{
  const h=harness(),s=slowReviews(h);
  const first=h.run("quick('one','listing')");
  await h.run("quick('two','advertising','toggle','A')");
  await h.run("quick('one','advertising','toggle','B')");
  assert.equal(s.bodies.length,3);assert.equal(h.run("data('image','B','one').uses[0]"),'advertising');
  s.gate.resolve();await first;
});

test('queued choices retain their sculpture and reviewed bytes after navigation',async()=>{
  const h=harness(),s=slowReviews(h);
  const done=Promise.allSettled([h.run("quick('one','listing')"),h.run("quick('one','advertising')")]);
  h.run("state.pid='B';state.request++;state.current={id:'B',images:[]}");s.gate.resolve();
  assert((await done).every(r=>r.status==='fulfilled'));
  assert.deepEqual(s.bodies.map(b=>[b.product_id,b.expected_content_hash]),[['A','old-hash'],['A','old-hash']]);
});

test('opening the image editor waits for its pending card choices',async()=>{
  const h=harness(),s=slowReviews(h),pending=h.run("quick('one','listing')");
  try{h.run("openImage('one')");assert.equal(h.node('#image-dialog').open,false);assert.match(h.messages.join(' '),/saving/i);}
  finally{s.gate.resolve();await pending;}
});

function downloadFixture(){
  const h=harness(),gate=deferred(),button={dataset:{fetchOriginal:'one'},disabled:false,textContent:'Fetch original',hasAttribute:()=>false};
  h.context.show=aid=>h.opened.push(aid);
  h.run("state.image=state.current.images[0];state.imageContext={pid:'A',aid:'one',request:1};openImage=show;");
  h.node('#image-dialog').open=true;
  h.context.api=async()=>gate.promise;
  const start=()=>h.listeners.click[1]({target:{closest:()=>button}});
  const finish=()=>gate.resolve({asset:{id:'one',name:'verified.jpg',original:{dropbox_content_hash:'old-hash',dimensions:[4000,3000]}}});
  return {...h,gate,button,start,finish};
}

test('finishing an original download does not reopen a closed photo editor',async()=>{
  const h=downloadFixture(),pending=h.start();h.node('#image-dialog').close();h.run('state.image=null;state.imageContext=null;');
  h.finish();await pending;assert.deepEqual(h.opened,[]);assert.equal(h.button.disabled,false);
});

test('a late original download cannot modify a different sculpture or reopen its photo',async()=>{
  const h=downloadFixture(),pending=h.start();
  h.run("state.pid='B';state.request++;state.current={id:'B',images:[{id:'one',name:'B snapshot'}]};state.imageContext={pid:'B',aid:'one',request:2}");
  h.finish();await pending;assert.equal(h.run('state.current.images[0].name'),'B snapshot');assert.deepEqual(h.opened,[]);assert.equal(h.renders(),0);
});

test('an original download cannot replace a newer editor for the same photo',async()=>{
  const h=downloadFixture(),pending=h.start();h.run("state.imageContext={pid:'A',aid:'one',request:1}");
  h.finish();await pending;assert.deepEqual(h.opened,[]);
});

test('draft edits made during download are retained without a discard prompt',async()=>{
  const h=downloadFixture(),pending=h.start();h.run("state.dirty.add('image-form')");h.finish();await pending;
  assert.deepEqual(h.opened,[]);assert.equal(h.run("state.dirty.has('image-form')"),true);
  assert.match(h.messages.join(' '),/saved|downloaded|verified/i);
});

test('a clean unchanged editor displays the verified original after download',async()=>{
  const h=downloadFixture(),pending=h.start();h.finish();await pending;
  assert.deepEqual(h.opened,['one']);assert.deepEqual(JSON.parse(h.run('JSON.stringify(state.current.images[0].original.dimensions)')),[4000,3000]);
  assert.equal(h.button.disabled,false);
});

test('download failure is retryable and leaves the image and its editor unchanged',async()=>{
  const h=downloadFixture(),pending=h.start();h.gate.reject(Error('Temporary download failure'));await pending;
  assert.deepEqual(h.opened,[]);assert.equal(h.run('state.current.images[0].name'),'one.jpg');
  assert.equal(h.button.disabled,false);assert.match(h.button.textContent,/Retry/);
});

function transferFixture(){
  const h=harness(),button={disabled:false},form=h.node('#transfer-form');
  form.elements={mode:{value:'copy'},target:{value:'B'}};form.querySelector=()=>button;
  h.context.form=form;h.run("renderTransferTargets=()=>{};updateTransferMode=()=>{};refreshAfterTransfer=async()=>{};openTransfer(['one'],'copy')");
  return {...h,form,button};
}

test('a transfer retains the sculpture and images shown when it was opened',async()=>{
  const h=transferFixture(),bodies=[];h.run("state.pid='B';state.request++;state.selected=new Set(['other'])");
  h.context.api=async(url,body)=>{bodies.push(body);return {description:'Copied'};};
  await h.run('performTransfer(form)');
  assert.equal(bodies[0].from_product_id,'A');assert.deepEqual([...bodies[0].asset_ids],['one']);
  assert.equal(h.run("state.selected.has('other')"),true);
});

test('navigation closes an unsubmitted transfer without moving any image',async()=>{
  const h=transferFixture(),writes=[];
  h.run('initImageSort=()=>{};renderMain=()=>{};renderList=()=>{};');
  h.context.api=async(url,body)=>{if(body)writes.push(body);return {id:'B',images:[],reviews:[]};};
  await h.run("load('B')");assert.equal(h.node('#transfer-dialog').open,false);assert.deepEqual(writes,[]);
});

test('a second transfer submission cannot duplicate an in-flight operation',async()=>{
  const h=transferFixture(),gate=deferred();let calls=0;
  h.context.api=async()=>{calls++;await gate.promise;return {description:'Copied'};};
  const first=h.run('performTransfer(form)'),second=h.run('performTransfer(form)');
  gate.resolve();await Promise.all([first,second]);assert.equal(calls,1);assert.equal(h.button.disabled,false);
});

test('closing a transfer invalidates its unsubmitted form',async()=>{
  const h=transferFixture();let calls=0;h.context.api=async()=>{calls++;};
  h.run('closeTransfer()');await h.run('performTransfer(form)');
  assert.equal(calls,0);assert.equal(h.node('#transfer-dialog').open,false);assert.match(h.messages.join(' '),/Reopen/);
});

test('a failed transfer keeps its form available for a deliberate retry',async()=>{
  const h=transferFixture();h.context.api=async()=>{throw Error('Temporary transfer error');};
  await h.run('performTransfer(form)');
  assert.equal(h.node('#transfer-dialog').open,true);assert.equal(h.form.inert,false);assert.equal(h.button.disabled,false);
  const bodies=[];h.context.api=async(url,body)=>{bodies.push(body);return {description:'Copied'};};
  await h.run('performTransfer(form)');assert.equal(bodies[0].from_product_id,'A');assert.equal(h.node('#transfer-dialog').open,false);
});

test('a delayed original does not overwrite a newer gallery snapshot',async()=>{
  const h=downloadFixture(),pending=h.start();h.run("state.current.images=[{id:'one',name:'Newer snapshot'}]");
  h.finish();await pending;assert.equal(h.run('state.current.images[0].name'),'Newer snapshot');assert.deepEqual(h.opened,[]);
});

test('an original download cannot start during an image details save',async()=>{
  const h=downloadFixture();let calls=0;h.context.api=async()=>{calls++;};h.run('state.savingImage=true');
  await h.start();assert.equal(calls,0);assert.match(h.messages.join(' '),/saving/);
});

test('a settled failed choice releases its queue for a later deliberate action',async()=>{
  const h=harness();h.context.api=async()=>{throw Error('Save unavailable');};
  await assert.rejects(h.run("quick('one','listing')"),/unavailable/);
  h.context.api=async(url,body)=>({...body,version:1});await h.run("quick('one','advertising')");
  assert.deepEqual(JSON.parse(h.run("JSON.stringify(data('image','A','one').uses)")),['advertising']);
});
