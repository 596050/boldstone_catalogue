const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),test=require('node:test');

function harness(){
  const nodes=new Map(),listeners={},timers=[];
  const node=s=>{if(!nodes.has(s))nodes.set(s,{innerHTML:'',textContent:'',value:'',open:false,disabled:false,scrollTop:0,
    close(){this.open=false;},showModal(){this.open=true;},addEventListener(){},classList:{toggle(){}},querySelector:()=>null,querySelectorAll:()=>[]});return nodes.get(s);};
  const context=vm.createContext({console,URL,URLSearchParams,
    FormData:class{constructor(form){this.form=form;}entries(){return Object.entries(this.form.values||{});}[Symbol.iterator](){return this.entries()[Symbol.iterator]();}},
    document:{querySelector:s=>s.includes('dialog[open]')?null:node(s),querySelectorAll:()=>[],addEventListener:(kind,f)=>(listeners[kind]||=[]).push(f)},
    window:{addEventListener(){},confirm:()=>true,scrollY:0,scrollTo(){}},location:{hash:''},history:{replaceState(){}},
    localStorage:{getItem:()=>null,setItem(){}},setTimeout:f=>{timers.push(f);return timers.length;},clearTimeout(){},setInterval(){},clearInterval(){}});
  const run=s=>vm.runInContext(s,context),base=path.resolve(__dirname,'../static');
  for(const name of ['app.js','image-tools.js','sync-tools.js','jobs.js'])run(fs.readFileSync(path.join(base,name),'utf8').replace(/\nboot\(\);\s*$/,'\n'));
  run(`state.pid='A';state.request=1;state.boot={csrf_token:'test-only',products:[],families:[],image_types:{},dropbox_sync:{generation:1}};
    state.current={id:'A',name:'A',images:[],fields:[]};dropboxShownGeneration=1;
    scheduleCoverageRefresh=()=>{};renderGrid=()=>{};renderMain=()=>{};renderList=()=>{};toast=()=>{};syncCanRefresh=()=>!state.dirty.size&&!state.saving&&!state.selected.size;`);
  return {context,run,node,nodes,listeners,timers};
}
const response=value=>({ok:true,json:async()=>value});
const tick=()=>new Promise(setImmediate);
const boot=()=>({products:[{id:'A',review:{version:0,data:{}}}],families:[],assignments:[],dropbox_sync:{generation:2},image_types:{}});

for(const [first,second] of [
  ['refreshDropboxView({generation:2})','refreshNativeView()'],
  ['refreshNativeView()','refreshDropboxView({generation:2})'],
  ['refreshNativeView()','refreshAfterTransfer()'],
])test(first+' cannot roll back a newer '+second+' response',async()=>{
  const h=harness();let release,reads=0;
  h.context.api=async url=>{
    if(url==='/api/bootstrap')return boot();
    if(++reads===1)return new Promise(resolve=>{release=resolve;});
    return {id:'A',name:'Latest sculpture',images:[],reviews:[{kind:'image',product_id:'A',item_id:'one',version:3,data:{uses:['listing']}}]};
  };
  const old=h.run(first);await tick();
  await h.run(second);
  release({id:'A',name:'Stale sculpture',images:[],reviews:[{kind:'image',product_id:'A',item_id:'one',version:2,data:{uses:[]}}]});
  await old;
  assert.equal(h.run('state.current.name'),'Latest sculpture');
  assert.equal(h.run("review('image','A','one').version"),3);
});

test('a failed newer refresh does not discard an older successful refresh',async()=>{
  const h=harness();let release,reads=0;
  h.context.api=async url=>{
    if(url==='/api/bootstrap')return boot();
    if(++reads===1)return new Promise(resolve=>{release=resolve;});
    throw Error('Temporary read error');
  };
  const old=h.run('refreshNativeView()');await tick();
  await assert.rejects(h.run('refreshDropboxView({generation:2})'),/Temporary read error/);
  release({id:'A',name:'Available update',images:[],reviews:[]});await old;
  assert.equal(h.run('state.current.name'),'Available update');
});

for(const refresh of ['refreshDropboxView({generation:2})','refreshNativeView()']){
  test(refresh+' removes an obsolete component page without fetching its deleted endpoint',async()=>{
    const h=harness(),calls=[];let renders=0;
    const fresh=boot();fresh.products=[{id:'B',review:{version:0,data:{}}}];
    h.context.renderMain=()=>{renders++;};
    h.context.api=async url=>{calls.push(url);if(url!=='/api/bootstrap')throw Error('Unknown sculpture');return fresh;};
    await h.run(refresh);
    assert.deepEqual(calls,['/api/bootstrap']);
    assert.equal(h.run('state.boot.products[0].id'),'B');
    assert.equal(h.run('state.current'),null);
    assert.match(h.node('#main').innerHTML,/removed from the active catalogue/);
    assert.equal(renders,0);
  });
  for(const tab of ['specs','listing'])test(refresh+' redraws clean '+tab+' fields after source changes',async()=>{
    const h=harness();let renders=0;h.run(`state.tab='${tab}';`);
    h.context.renderMain=()=>{renders++;};
    h.context.api=async url=>url==='/api/bootstrap'?boot():{id:'A',name:'Updated sculpture',images:[],fields:[],reviews:[]};
    await h.run(refresh);
    assert.equal(h.run('state.current.name'),'Updated sculpture');
    assert.equal(renders,1);
  });
  test(refresh+' defers a removed-component update if editing starts during the read',async()=>{
    const h=harness();let release;
    const fresh=boot();fresh.products=[];
    h.context.api=async()=>new Promise(resolve=>{release=resolve;});
    const pending=h.run(refresh);h.run("state.dirty.add('field-Depth');");release(fresh);await pending;
    assert.equal(h.run('state.current.name'),'A');
    assert.equal(h.run("state.dirty.has('field-Depth')"),true);
    assert.doesNotMatch(h.node('#main').innerHTML,/removed from the active catalogue/);
  });
}

test('failed automatic Dropbox status polls show an error while keeping the saved gallery',async()=>{
  const h=harness();
  h.run(`dropboxLatestStatus={enabled:true,generation:1,state:'checking',last_checked:'2026-10-28T12:00:00Z'};`);
  h.context.api=async()=>{throw Error('Server unavailable');};
  await h.run('pollDropboxSync()');
  assert.match(h.node('#dropbox-sync-status').textContent,/status unavailable/);
  assert.match(h.node('#dropbox-sync-status').title,/last received catalogue/);
  assert.equal(h.node('#dropbox-sync-now').disabled,false);
  assert.equal(h.run('state.current.name'),'A');
  h.context.api=async()=>({enabled:true,generation:1,state:'ready',last_checked:'2026-10-28T12:01:00Z'});
  await h.run('pollDropboxSync()');
  assert.match(h.node('#dropbox-sync-status').textContent,/Dropbox checked/);
  assert.equal(h.run('dropboxSyncError'),'');
});

test('Dropbox retry status exposes the next check time without inventing a successful refresh',()=>{
  const h=harness();
  h.run(`renderDropboxSync({enabled:true,state:'error',generation:1,error:'Image refresh cleanup is retrying',retry_at:2000000000});`);
  assert.equal(h.node('#dropbox-sync-status').textContent,'Dropbox: retrying');
  assert.match(h.node('#dropbox-sync-status').title,/Next check at/);
});

for(const refresh of ['refreshDropboxView({generation:2})','refreshNativeView()']){
  test(refresh+' does not overwrite a save that completed during its reads',async()=>{
    const h=harness();let release;
    h.context.fetch=async(url,options)=>{
      if(options.method==='POST'){const body=JSON.parse(options.body);return response({kind:body.kind,product_id:body.product_id,item_id:body.item_id,version:2,data:body.data});}
      return url==='/api/bootstrap'?response(boot()):new Promise(resolve=>{release=value=>resolve(response(value));});
    };
    const pending=h.run(refresh);await tick();
    await h.run(`save('image','A','one',{decision:'reviewed',uses:['listing','advertising']})`);
    release({id:'A',name:'stale',images:[],reviews:[{kind:'image',product_id:'A',item_id:'one',version:1,data:{decision:'reviewed',uses:[]}}]});
    await pending;
    assert.equal(h.run("review('image','A','one').version"),2);
    assert.equal(h.run('state.current.name'),'A');
  });
}

test('transfer refresh cannot overwrite a different sculpture or clear its selection',async()=>{
  const h=harness();let release;
  h.context.api=async url=>url==='/api/bootstrap'?boot():new Promise(resolve=>{release=resolve;});
  const pending=h.run('refreshAfterTransfer()');await tick();
  h.run(`state.pid='B';state.request=2;state.current={id:'B',name:'B',images:[]};state.selected.add('new-image');`);
  release({id:'A',name:'Wrong sculpture',images:[],reviews:[]});await pending;
  assert.equal(h.run('state.current.name'),'B');assert.equal(h.run("state.selected.has('new-image')"),true);
});

test('transfer refresh defers when fresh unsaved edits are started',async()=>{
  const h=harness();let release,renders=0;h.context.renderMain=()=>{renders++;};
  h.context.api=async url=>url==='/api/bootstrap'?boot():new Promise(resolve=>{release=resolve;});
  const pending=h.run('refreshAfterTransfer()');await tick();
  h.run(`state.tab='specs';state.dirty.add('field-Depth');`);
  release({id:'A',images:[],reviews:[]});await pending;
  assert.equal(renders,0);assert.equal(h.run("state.dirty.has('field-Depth')"),true);
  assert.equal(h.run('nativeViewNeedsRefresh'),true);
});

test('transfer refresh handles a family overview without requesting a product named __family__',async()=>{
  const h=harness(),calls=[];h.run("state.pid='__family__';state.family='Acanthus';");
  h.context.api=async url=>{calls.push(url);if(url.includes('/api/products/'))throw Error('Wrong endpoint');return boot();};
  await h.run('refreshAfterTransfer()');assert.deepEqual(calls,['/api/bootstrap']);
});

test('an old transfer response cannot close a newer transfer dialog',async()=>{
  const h=harness();let release;
  h.context.api=async()=>new Promise(resolve=>{release=resolve;});h.context.refreshAfterTransfer=async()=>{};
  h.context.form={id:'transfer-form',elements:{mode:{value:'copy'},target:{value:'B'}},querySelector:()=>({disabled:false})};
  h.nodes.set('#transfer-form',h.context.form);h.run("transferContexts.set(form,{pid:'A',request:1,ids:['one']});");h.node('#transfer-dialog').open=true;
  const pending=h.run('performTransfer(form)');await tick();
  h.node('#transfer-dialog').close();h.nodes.set('#transfer-form',{id:'transfer-form',marker:'new'});h.node('#transfer-dialog').open=true;
  h.run("state.dirty.add('transfer-form');");release({description:'Copied old image'});await pending;
  assert.equal(h.node('#transfer-dialog').open,true);assert.equal(h.run("state.dirty.has('transfer-form')"),true);
});

function specFixture(h,notes=false){
  const button={disabled:false},status={textContent:''},badge={},saved={textContent:'',previousElementSibling:{}};
  const card={querySelector:s=>s==='[data-field-badge]'?badge:s==='[data-listing-value]'?saved:null};
  const form={id:notes?'product-notes':'field-Depth',dataset:{field:'Depth'},values:notes?{notes:'First note'}:{decision:'edit',value:'4 cm'},
    elements:{notes:{value:'First note'}},querySelector:s=>s==='button[type=submit]'?button:s==='.save-state'?status:null,
    closest:()=>card,matches:()=>!notes};
  h.context.form=form;return {form,button,status,saved};
}
for(const notes of [false,true])test((notes?'product notes':'specification')+' edits made while saving remain unsaved',async()=>{
  const h=harness(),f=specFixture(h,notes);let release;
  h.context.save=async(kind,pid,item,values)=>new Promise(resolve=>{release=()=>resolve({version:1,data:values});});
  h.run(`state.dirty.add(form.id);`);const pending=h.run('submitForm(form)');
  if(notes){f.form.values.notes='Later note';f.form.elements.notes.value='Later note';}else f.form.values.value='5 cm';
  release({version:1,data:{}});await pending;
  assert.equal(h.run('state.dirty.has(form.id)'),true);assert.match(f.status.textContent,/unsaved|not saved/i);
  assert.equal(f.button.disabled,false);if(!notes)assert.equal(f.saved.textContent,'4 cm');
});

for(const refresh of ['refreshDropboxView({generation:2})','refreshAfterTransfer()'])test(refresh+' applies a fresh unchanged snapshot',async()=>{
  const h=harness();let renders=0;h.context.renderMain=()=>{renders++;};
  const fresh=boot();fresh.products=[{id:'A',review:{version:3,data:{notes:'Saved notes'}}}];
  h.context.api=async url=>url==='/api/bootstrap'?fresh:{id:'A',name:'Fresh',images:[],reviews:[]};
  await h.run(refresh);
  assert.equal(h.run('state.current.name'),'Fresh');assert.equal(renders,1);
  assert.equal(h.run("review('product','A').data.notes"),'Saved notes');
  if(refresh.includes('Dropbox'))assert.equal(h.run('dropboxShownGeneration'),2);
  else assert.equal(h.run('nativeViewNeedsRefresh'),false);
});

test('a deferred transfer refresh retries once unsaved edits are finished',async()=>{
  const h=harness();let calls=0;
  h.context.api=async url=>{calls++;return url==='/api/bootstrap'?boot():{id:'A',name:'Fresh',images:[],reviews:[]};};
  h.run("state.dirty.add('field-Depth');");
  assert.equal(await h.run('refreshAfterTransfer()'),false);assert.equal(calls,0);
  h.run('state.dirty.clear();');assert.equal(await h.run('refreshNativeView()'),true);
  assert.equal(h.run('state.current.name'),'Fresh');assert.equal(h.run('nativeViewNeedsRefresh'),false);
});

test('failed writes invalidate pending reads without preventing the next refresh',async()=>{
  const h=harness();let release,first=true;
  h.context.fetch=async(url,options)=>{
    if(options.method==='POST')return {ok:false,status:409,json:async()=>({error:'Reload this image'})};
    if(url==='/api/bootstrap')return response(boot());
    if(first){first=false;return new Promise(resolve=>{release=value=>resolve(response(value));});}
    return response({id:'A',name:'Fresh',images:[],reviews:[]});
  };
  const pending=h.run('refreshDropboxView({generation:2})');await tick();
  await assert.rejects(h.run("save('image','A','one',{decision:'reviewed',uses:['listing']})"),/Reload/);
  release({id:'A',name:'Old',images:[],reviews:[]});await pending;
  assert.equal(h.run('state.current.name'),'A');assert.equal(h.run('state.saving'),0);
  assert.equal(h.run('dropboxShownGeneration'),1);
  await h.run('refreshDropboxView({generation:2})');assert.equal(h.run('state.current.name'),'Fresh');
});

for(const notes of [false,true])test((notes?'product notes':'specification')+' saves without newer edits become saved',async()=>{
  const h=harness(),f=specFixture(h,notes);h.context.save=async(kind,pid,item,values)=>({version:1,data:values});
  h.run('state.dirty.add(form.id);');await h.run('submitForm(form)');
  assert.equal(h.run('state.dirty.has(form.id)'),false);assert.match(f.status.textContent,/Saved locally/);
});

test('changing and reverting a value during its save does not create a false unsaved warning',async()=>{
  const h=harness(),f=specFixture(h);let release;
  h.context.save=async(kind,pid,item,values)=>new Promise(resolve=>{release=()=>resolve({version:1,data:values});});h.run('state.dirty.add(form.id);');
  const pending=h.run('submitForm(form)');f.form.values.value='5 cm';f.form.values.value='4 cm';
  release({version:1,data:{}});await pending;
  assert.equal(h.run('state.dirty.has(form.id)'),false);assert.match(f.status.textContent,/Saved locally/);
});

test('successful transfer clears transferred selection but retains unrelated selected images',async()=>{
  const h=harness();h.context.api=async()=>({description:'Copied'});h.context.refreshAfterTransfer=async()=>{};
  h.context.form={id:'transfer-form',elements:{mode:{value:'copy'},target:{value:'B'}},querySelector:()=>({disabled:false})};
  h.nodes.set('#transfer-form',h.context.form);h.node('#transfer-dialog').open=true;
  h.run("transferContexts.set(form,{pid:'A',request:1,ids:['one']});state.selected=new Set(['one','other']);state.dirty.add('transfer-form');");
  await h.run('performTransfer(form)');
  assert.equal(h.run("JSON.stringify([...state.selected])"),'["other"]');
  assert.equal(h.node('#transfer-dialog').open,false);assert.equal(h.run("state.dirty.has('transfer-form')"),false);
});

test('selection changed during a transfer is preserved when the response arrives',async()=>{
  const h=harness();let release;
  h.context.api=async()=>new Promise(resolve=>{release=resolve;});h.context.refreshAfterTransfer=async()=>{};
  h.context.form={id:'transfer-form',elements:{mode:{value:'copy'},target:{value:'B'}},querySelector:()=>({disabled:false})};
  h.nodes.set('#transfer-form',h.context.form);h.run("transferContexts.set(form,{pid:'A',request:1,ids:['one']});state.selected.add('one');");
  const pending=h.run('performTransfer(form)');h.run("state.selected.add('later');");
  release({description:'Copied'});await pending;
  assert.equal(h.run("JSON.stringify([...state.selected])"),'["one","later"]');
});
