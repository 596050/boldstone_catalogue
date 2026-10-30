const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),test=require('node:test');
const tick=()=>new Promise(setImmediate);
function harness(){
  const nodes=new Map(),listeners={},messages=[];
  const node=s=>{if(!nodes.has(s))nodes.set(s,{innerHTML:'',textContent:'',open:false,disabled:false,checked:true,scrollTop:0,
    dataset:{},isConnected:true,close(){this.open=false;},showModal(){this.open=true;},addEventListener(){},
    classList:{toggle(){}},querySelector:()=>null,querySelectorAll:()=>[]});return nodes.get(s);};
  const context=vm.createContext({console,URL,URLSearchParams,
    document:{querySelector:node,querySelectorAll:()=>[],addEventListener:(k,f)=>(listeners[k]||=[]).push(f)},
    window:{addEventListener(){},confirm:()=>true,scrollY:0,scrollTo(){}},location:{hash:''},history:{replaceState(){}},
    localStorage:{getItem:()=>null,setItem(){}},setTimeout(){},clearTimeout(){},setInterval(){},clearInterval(){}});
  const run=s=>vm.runInContext(s,context);
  for(const file of ['app.js','image-tools.js','delete-tools.js','bulk-delete.js','jobs.js'])
    run(fs.readFileSync(path.resolve(__dirname,'../static',file),'utf8').replace(/\nboot\(\);\s*$/,'\n'));
  const old={operation_id:'op-one',file_id:'id:one',state:'uncertain',file:{id:'id:one',name:'one.jpg',path:'/BOLDSTONE MASTER/one.jpg',revision:'1'},result:{message:'Old pending result'}};
  context.fixtureOld=old;
  run(`state.pid='A';state.request=1;state.current={images:[]};state.boot={products:[],families:[],operations:[],deletions:[fixtureOld]};syncCanRefresh=()=>false;`);
  context.toast=(m,error)=>messages.push({m,error});
  const click=async props=>{
    const button={id:'',dataset:{},disabled:false,isConnected:true,hasAttribute:()=>false,...props};
    const event={target:{closest:s=>s==='.select-box'?null:button}};
    await Promise.all((listeners.click||[]).map(fn=>fn(event)));return button;
  };
  const fresh={...old,state:'present',result:{message:'Verified present',presence_verified:true}};
  context.api=async(url,body)=>{
    if(url==='/api/deletions/check')return {operation_id:fresh.operation_id,...fresh.result,state:fresh.state};
    if(url==='/api/deletions/history')return [fresh];
    if(url==='/api/bootstrap')return {products:[],families:[],deletions:[fresh]};
    throw Error('Unexpected route '+url);
  };
  return {run,context,node,messages,click,fresh,old};
}

test('history Check status displays its new result while the modal stays open',async()=>{
  const h=harness();h.run('showDeletionHistory()');
  await h.click({dataset:{checkDeletion:'op-one'}});
  assert.equal(h.node('#history-dialog').open,true);
  assert.match(h.node('#history-dialog').innerHTML,/File present - ready for a new review/);
  assert.doesNotMatch(h.node('#history-dialog').innerHTML,/Old pending result/);
  assert.equal(h.run('nativeViewNeedsRefresh'),true);
});

test('a status check cannot reopen closed history',async()=>{
  const h=harness();let release;const api=h.context.api;
  h.context.api=(url,body)=>url==='/api/deletions/check'?new Promise(r=>release=r):api(url,body);
  h.run('showDeletionHistory()');const pending=h.click({dataset:{checkDeletion:'op-one'}});await tick();
  h.node('#history-dialog').close();release({operation_id:'op-one',state:'present',presence_verified:true});await pending;
  assert.equal(h.node('#history-dialog').open,false);
});

test('a late status check cannot replace newly opened transfer history',async()=>{
  const h=harness();let release;const api=h.context.api;
  h.context.api=(url,body)=>url==='/api/deletions/check'?new Promise(r=>release=r):api(url,body);
  h.run('showDeletionHistory()');const pending=h.click({dataset:{checkDeletion:'op-one'}});await tick();
  h.node('#history-dialog').close();h.run('showTransferHistory()');
  release({operation_id:'op-one',state:'present',presence_verified:true});await pending;
  assert.equal(h.node('#history-dialog').open,true);assert.match(h.node('#history-dialog').innerHTML,/Transfer history/);
});

test('opening deletion history is immediately closable and its delayed load stays closed',async()=>{
  const h=harness();let release;
  h.context.api=()=>new Promise(r=>release=r);
  const pending=h.click({id:'delete-history'});await tick();
  assert.equal(h.node('#history-dialog').open,true);
  h.node('#history-dialog').close();release([h.fresh]);await pending;
  assert.equal(h.node('#history-dialog').open,false);
});

test('history refresh updates only history, retaining newer catalogue and saved edits',async()=>{
  const h=harness();let release;
  h.context.api=()=>new Promise(r=>release=r);
  const pending=h.click({id:'delete-history'});await tick();
  h.run(`state.boot.products=[{id:'new',name:'New catalogue'}];state.boot.csrf_token='new-session';state.dirty.add('field-Depth');`);
  release([h.fresh]);await pending;
  assert.equal(h.run('state.boot.products[0].id'),'new');assert.equal(h.run('state.boot.csrf_token'),'new-session');
  assert.equal(h.run("state.dirty.has('field-Depth')"),true);
});

test('history read errors are caught and leave a visible retry action',async()=>{
  const h=harness();h.context.api=async()=>{throw Error('Connection unavailable');};
  await h.click({id:'delete-history'});
  assert.equal(h.node('#history-dialog').open,true);
  assert.match(h.node('#history-status').textContent,/Connection unavailable/);
  assert.match(h.node('#history-dialog').innerHTML,/Refresh history/);
});

test('an older history snapshot cannot replace a completed status check',async()=>{
  const h=harness();let release,reads=0;const api=h.context.api;
  h.context.api=(url,body)=>url==='/api/deletions/history'&&++reads===1?new Promise(r=>release=r):api(url,body);
  const initial=h.run('openDeletionHistory()');await tick();
  await h.click({dataset:{checkDeletion:'op-one'}});
  release([h.old]);await initial;
  assert.match(h.node('#history-dialog').innerHTML,/File present - ready for a new review/);
  assert.equal(h.run('state.boot.deletions[0].state'),'present');
});

test('a successful status check remains visible if its follow-up history fetch fails',async()=>{
  const h=harness(),api=h.context.api;
  h.context.api=(url,body)=>url==='/api/deletions/history'?Promise.reject(Error('Connection unavailable')):api(url,body);
  h.run('showDeletionHistory()');await h.click({dataset:{checkDeletion:'op-one'}});
  assert.match(h.node('#history-dialog').innerHTML,/File present - ready for a new review/);
  assert.match(h.node('#history-status').textContent,/Could not refresh history/);
  assert.equal(h.messages.filter(x=>x.error).length,0);
});

test('reopening deletion history during a check still receives the completed result',async()=>{
  const h=harness();let release,finished=false;
  h.context.api=(url,body)=>url==='/api/deletions/check'?new Promise(r=>{release=()=>{finished=true;r({operation_id:'op-one',state:'present',presence_verified:true});};}):Promise.resolve([finished?h.fresh:h.old]);
  h.run('showDeletionHistory()');const pending=h.click({dataset:{checkDeletion:'op-one'}});await tick();
  h.node('#history-dialog').close();await h.run('openDeletionHistory()');
  release();await pending;
  assert.equal(h.node('#history-dialog').open,true);
  assert.match(h.node('#history-dialog').innerHTML,/File present - ready for a new review/);
});

test('a completed transfer undo cannot close a newer history window',async()=>{
  const h=harness();let release;h.context.api=()=>new Promise(r=>release=r);
  h.run('showTransferHistory()');const pending=h.click({dataset:{undoTransfer:'transfer-one'}});await tick();
  h.node('#history-dialog').close();h.run('showDeletionHistory()');release({});await pending;
  assert.equal(h.node('#history-dialog').open,true);assert.match(h.node('#history-dialog').innerHTML,/Deletion history/);
});

for(const lost of [false,true])for(const state of ['cancelled','completed','uncertain'])test(`bulk confirmation ${lost?'recovered after a lost response':'response'} reports ${state}, not queued`,async()=>{
  const h=harness(),job={id:'delete-batch-b1',state,files:[{id:'id:one'}]};
  h.run(`bulkDeletion={phase:'review',entries:[],skipped:[],busy:[],plan:{batch_id:'b1',files:[{id:'id:one',revision:'1'}]}};renderBulkDelete=()=>{};`);
  h.context.api=async()=>{if(lost)throw Error('Response lost');return job;};
  h.context.trackNativeJob=async()=>{};h.context.findNativeJob=async()=>job;
  await h.run('executeBulkDeletion()');
  const text=h.messages.map(x=>x.m).join(' ');
  assert.match(text,state==='cancelled'?/cancelled/i:state==='completed'?/finished|completed/i:/check|unconfirmed/i);
  assert.doesNotMatch(text,/is queued|Deletion queued/i);
});

for(const lost of [false,true])test(`single-file ${lost?'recovered':'returned'} cancellation does not claim the file is queued`,async()=>{
  const h=harness(),job={id:'delete-op-one',state:'cancelled',files:[{id:'id:one'}]};
  h.run(`deletePlan={operation_id:'op-one',file:{id:'id:one'}};`);
  h.context.form={querySelector:()=>({disabled:false})};
  h.context.api=async()=>{if(lost)throw Error('Response lost');return job;};
  h.context.trackNativeJob=async()=>{};h.context.findNativeJob=async()=>job;
  await h.run('executeDeletion(form)');
  assert.match(h.messages.map(x=>x.m).join(' '),/cancelled/i);
  assert.doesNotMatch(h.messages.map(x=>x.m).join(' '),/Deletion queued/i);
});

test('Review remaining files creates its saved review without reopening a closed Jobs window',async()=>{
  const h=harness();let release,opened=0;h.node('#jobs-dialog').open=true;
  h.context.api=()=>new Promise(r=>release=r);h.context.pollNativeJobs=async()=>({});
  h.context.openSavedDeletionReview=async()=>{opened++;};
  const pending=h.click({dataset:{reviewJobRemaining:'old-job'}});await tick();
  h.node('#jobs-dialog').close();release({id:'review-saved',kind:'delete_review',state:'queued'});await pending;
  assert.equal(opened,0);assert.equal(h.node('#jobs-dialog').open,false);
});
