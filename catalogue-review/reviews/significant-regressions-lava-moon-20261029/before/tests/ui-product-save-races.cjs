const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),test=require('node:test');
const tick=()=>new Promise(setImmediate);
function deferred(){let resolve,reject;const promise=new Promise((yes,no)=>{resolve=yes;reject=no;});return {promise,resolve,reject};}
const response=value=>({ok:true,json:async()=>value});
function harness(){
  const nodes=new Map(),listeners={},windowListeners={},messages=[];
  const node=s=>{if(!nodes.has(s))nodes.set(s,{id:s.slice(1),value:'',innerHTML:'',textContent:'',open:false,disabled:false,dataset:{},
    addEventListener(){},closest(){return null;},querySelector:()=>null,querySelectorAll:()=>[],classList:{toggle(){}},
    close(){this.open=false;},showModal(){this.open=true;}});return nodes.get(s);};
  const context=vm.createContext({console,URL,URLSearchParams,
    FormData:class{constructor(form){this.form=form;}entries(){return Object.entries(this.form.values||{});}[Symbol.iterator](){return this.entries()[Symbol.iterator]();}},
    document:{querySelector:node,querySelectorAll:()=>[],addEventListener:(type,fn)=>(listeners[type]||=[]).push(fn)},
    window:{addEventListener:(type,fn)=>windowListeners[type]=fn,confirm:()=>true},location:{hash:'#A'},history:{replaceState(){}},
    setTimeout(){},clearTimeout(){},setInterval(){},clearInterval(){}});
  const run=s=>vm.runInContext(s,context);
  run(fs.readFileSync(path.join(__dirname,'../static/app.js'),'utf8').replace(/\nboot\(\);\s*$/,'\n'));
  context.report=message=>messages.push(message);
  run(`state.pid='A';state.request=1;state.boot={csrf_token:'test-only',products:[{id:'A'},{id:'B'}],families:[]};
    state.current={id:'A',name:'A',images:[{id:'one',original:{dropbox_content_hash:'hash'}}],fields:[]};
    toast=report;renderList=()=>{};renderMain=()=>{};renderGrid=()=>{};scheduleCoverageRefresh=()=>{};
    globalThis.initImageSort=()=>{};globalThis.typeLabels=()=>({});`);
  node('#product-decision').value='pending';node('#product-status').value='unreviewed';
  const choose=(field,value)=>{const el=node('#product-'+field);el.value=value;return listeners.change[0]({target:el});};
  return {run,context,node,listeners,windowListeners,messages,choose};
}
function server(h){
  const gate=deferred(),writes=[],reads=[],saved=new Map();let rejectFirst=false;
  h.context.fetch=async(url,options={})=>{
    if(options.method!=='POST'){
      reads.push(url);
      return response({id:url.split('/').pop(),images:[],fields:[],reviews:[...saved.values()]});
    }
    const body=JSON.parse(options.body);writes.push(body);
    if(writes.length===1){await gate.promise;if(rejectFirst)throw Error('Connection lost');}
    const id=JSON.stringify([body.kind,body.product_id,body.item_id]),version=saved.get(id)?.version||0;
    if(body.version!==version)return {ok:false,status:409,json:async()=>({error:'Review changed; reload'})};
    const result={...body,version:version+1};saved.set(id,result);return response(result);
  };
  return {gate,writes,reads,saved,failFirst(){rejectFirst=true;}};
}
function notes(h){
  const button={disabled:false},status={textContent:''};
  const form={id:'product-notes',values:{notes:'My private note'},elements:{notes:{value:'My private note'}},matches:()=>false,
    querySelector:s=>s==='button[type=submit]'?button:s==='.save-state'?status:null};
  h.context.form=form;return {form,button,status,start:()=>h.run('submitForm(form)')};
}

test('quick product decision and progress changes both survive the save',async()=>{
  const h=harness(),s=server(h),first=h.choose('decision','include'),second=h.choose('status','reviewed');
  s.gate.resolve();await Promise.all([first,second]);
  assert.deepEqual(s.writes.map(b=>b.version),[0,1]);
  assert.equal(h.run("data('product','A').decision"),'include');assert.equal(h.run("data('product','A').status"),'reviewed');
  assert(!h.messages.some(m=>m.includes('reload')),h.messages.join(' '));
});

for(const notesFirst of [true,false])test('notes and listing choice share a save queue, notes first = '+notesFirst,async()=>{
  const h=harness(),s=server(h),f=notes(h);
  const actions=notesFirst?[f.start(),h.choose('decision','include')]:[h.choose('decision','include'),f.start()];
  s.gate.resolve();await Promise.all(actions);
  assert.equal(h.run("data('product','A').notes"),'My private note');assert.equal(h.run("data('product','A').decision"),'include');
  assert.deepEqual(s.writes.map(b=>b.version),[0,1]);
});

test('a queued notes save captures the submitted note, keeping later text as an unsaved draft',async()=>{
  const h=harness(),s=server(h),f=notes(h),first=h.choose('decision','include'),second=f.start();
  f.form.values.notes=f.form.elements.notes.value='Later unsaved note';s.gate.resolve();await Promise.all([first,second]);
  assert.equal(h.run("data('product','A').notes"),'My private note');assert.equal(h.run("state.dirty.has('product-notes')"),true);
  assert.match(f.status.textContent,/not saved|unsaved/i);
});

test('queued product changes retain their original sculpture after navigation',async()=>{
  const h=harness(),s=server(h),first=h.choose('decision','include'),second=h.choose('status','reviewed');
  h.run("state.pid='B';state.request++");s.gate.resolve();await Promise.all([first,second]);
  assert(s.writes.every(b=>b.product_id==='A'));assert.equal(h.run("data('product','A').status"),'reviewed');
  assert.equal(h.run("review('product','B').version"),0);
});

test('another sculpture can save while the first sculpture is still saving',async()=>{
  const h=harness(),s=server(h),first=h.choose('decision','include');
  h.run("state.pid='B';state.request++");await h.choose('status','reviewed');
  assert.equal(s.writes.length,2);assert.equal(h.run("data('product','B').status"),'reviewed');s.gate.resolve();await first;
});

test('an unconfirmed earlier product change stops its queued successors',async()=>{
  const h=harness(),s=server(h);s.failFirst();
  const first=h.choose('decision','include'),second=h.choose('status','reviewed');s.gate.resolve();await Promise.all([first,second]);
  assert.equal(s.writes.length,1);assert.equal(h.run("review('product','A').version"),0);
  assert.match(h.messages.join(' '),/previous|earlier/);
});

test('failure on an old page does not read recovery values from the new sculpture',async()=>{
  const h=harness(),s=server(h);s.failFirst();const first=h.choose('decision','include');
  h.run("state.pid='B';state.request++;state.reviews.set(key('product','B',''),{version:2,data:{decision:'exclude'}})");
  s.gate.resolve();await first;assert.notEqual(h.node('#product-decision').value,'exclude');
});

test('closing the tab warns while product choices are still saving',async()=>{
  const h=harness(),s=server(h),first=h.choose('decision','include');let prevented=false;
  h.windowListeners.beforeunload({preventDefault(){prevented=true;}});
  s.gate.resolve();await first;assert.equal(prevented,true);
});

test('opening a page waits for pending image choices before reading the catalogue',async()=>{
  const h=harness(),s=server(h),first=h.run("quick('one','listing')"),second=h.run("quick('one','advertising')");
  const pending=h.run("load('A')");await tick();const readsBeforeSave=s.reads.length;
  s.gate.resolve();await Promise.all([first,second,pending]);
  assert.equal(readsBeforeSave,0);assert.equal(h.run("review('image','A','one').version"),2);
  assert.equal(h.run('state.loading'),false);
});

test('a navigation response captured before a save is re-read instead of rolling back that save',async()=>{
  const h=harness(),s=server(h),oldGet=deferred(),underlying=h.context.fetch;let reads=0;
  h.context.fetch=async(url,options={})=>{if(options.method!=='POST'&&++reads===1)return oldGet.promise;return underlying(url,options);};
  const pending=h.run("load('A')");await tick();const saving=h.run("save('image','A','one',{decision:'reviewed',uses:['listing']})");
  s.gate.resolve();await saving;
  oldGet.resolve(response({id:'A',images:[],reviews:[{kind:'image',product_id:'A',item_id:'one',version:0,data:{uses:[]}}]}));
  await pending;assert.equal(reads,2);assert.equal(h.run("review('image','A','one').version"),1);
});

test('navigation during pending saves only reads the latest destination',async()=>{
  const h=harness(),s=server(h),saving=h.choose('decision','include'),old=h.run("load('A')"),latest=h.run("load('B')");
  await tick();s.gate.resolve();await Promise.all([saving,old,latest]);
  assert.deepEqual(s.reads,['/api/products/B']);assert.equal(h.run('state.current.id'),'B');assert.equal(h.run('state.loading'),false);
});

test('navigation can recover the server record after a failed save',async()=>{
  const h=harness(),s=server(h);s.failFirst();const saving=h.choose('decision','include'),pending=h.run("load('A')");
  s.gate.resolve();await Promise.all([saving,pending]);
  assert.deepEqual(s.reads,['/api/products/A']);assert.equal(h.run('state.loading'),false);
});

test('export waits for the entire image choice queue before packaging decisions',async()=>{
  const h=harness(),s=server(h),originalFetch=h.context.fetch;let exported=null;
  h.context.fetch=async(url,options)=>{
    if(url==='/api/export'){exported=[...s.saved.values()];return response({review_decisions:1,included:1,listing_ready:0,download_url:'/download',path:'fixture'});}
    return originalFetch(url,options);
  };
  const button=h.node('#export-run'),event={target:{closest:selector=>selector==='.select-box'?null:button}};
  const first=h.run("quick('one','listing')"),second=h.run("quick('one','advertising')"),pending=h.listeners.click[0](event);
  await tick();const before=exported;s.gate.resolve();await Promise.all([first,second,pending]);
  assert.equal(before,null);assert.deepEqual(exported[0].data.uses,['listing','advertising']);
});

test('export does not package decisions when a pending save fails',async()=>{
  const h=harness(),s=server(h),underlying=h.context.fetch;let exported=false;s.failFirst();
  h.context.fetch=async(url,options)=>{if(url==='/api/export'){exported=true;return response({});}return underlying(url,options);};
  const button=h.node('#export-run'),event={target:{closest:selector=>selector==='.select-box'?null:button}};
  const saving=h.choose('decision','include'),pending=h.listeners.click[0](event);s.gate.resolve();await Promise.all([saving,pending]);
  assert.equal(exported,false);assert.match(h.node('#export-result').textContent,/save|confirm|Connection/i);assert.equal(button.disabled,false);
});

for(const endpoint of ['/api/reviews','/api/image-components','/api/assignments','/api/assignments/undo'])test('navigation waits for direct component/transfer write '+endpoint,async()=>{
  const h=harness(),gate=deferred(),reads=[];
  h.context.fetch=async(url,options)=>{
    if(options.method==='POST'){await gate.promise;return response({});}
    reads.push(url);return response({id:'B',images:[],reviews:[]});
  };
  const saving=h.run(`api('${endpoint}',{})`),loading=h.run("load('B')");
  await tick();const before=reads.length;gate.resolve();await Promise.all([saving,loading]);
  assert.equal(before,0);assert.deepEqual(reads,['/api/products/B']);
});

test('a later deliberate product choice is possible after a failed queue finishes',async()=>{
  const h=harness(),s=server(h);s.failFirst();const saving=h.choose('decision','include');s.gate.resolve();await saving;
  await h.choose('status','in_progress');assert.equal(s.writes.length,2);assert.equal(h.run("data('product','A').status"),'in_progress');
});

test('a draft started while export is waiting prevents exporting unsaved work',async()=>{
  const h=harness(),s=server(h),underlying=h.context.fetch;let exported=false;
  h.context.fetch=async(url,options)=>{if(url==='/api/export'){exported=true;return response({});}return underlying(url,options);};
  const button=h.node('#export-run'),event={target:{closest:selector=>selector==='.select-box'?null:button}};
  const saving=h.choose('decision','include'),exporting=h.listeners.click[0](event);
  h.run("state.dirty.add('product-notes')");s.gate.resolve();await Promise.all([saving,exporting]);
  assert.equal(exported,false);assert.match(h.node('#export-result').textContent,/unsaved/);
});

test('repeated export clicks do not create duplicate bundles',async()=>{
  const h=harness(),gate=deferred();let exports=0;
  h.context.fetch=async()=>{exports++;await gate.promise;return response({download_url:'/test',path:'test'});};
  const button=h.node('#export-run'),event={target:{closest:selector=>selector==='.select-box'?null:button}};
  const first=h.listeners.click[0](event),second=h.listeners.click[0](event);await tick();gate.resolve();await Promise.all([first,second]);
  assert.equal(exports,1);assert.equal(button.disabled,false);
});
