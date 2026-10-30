const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),test=require('node:test');
function harness(){
  const nodes=new Map(),listeners={},timers=[];
  const node=s=>{if(!nodes.has(s))nodes.set(s,{innerHTML:'',textContent:'',open:false,checked:true,disabled:false,scrollTop:0,
    close(){this.open=false;},showModal(){this.open=true;},addEventListener(){},classList:{toggle(){}},querySelector:()=>null});return nodes.get(s);};
  const context=vm.createContext({console,URL,URLSearchParams,ImageSort:require('../static/sort-core.js'),
    document:{querySelector:s=>s.includes('dialog[open]')?null:node(s),querySelectorAll:()=>[],addEventListener:(kind,f)=>(listeners[kind]||=[]).push(f)},
    window:{addEventListener(){},confirm:()=>true,scrollY:0,scrollTo(){}},location:{hash:''},history:{replaceState(){}},
    localStorage:{getItem:()=>null,setItem(){}},setTimeout:f=>{timers.push(f);return timers.length;},clearTimeout(){},setInterval(){},clearInterval(){}});
  const run=s=>vm.runInContext(s,context),base=path.resolve(__dirname,'../static');
  const load=name=>run(fs.readFileSync(path.join(base,name),'utf8').replace(/\nboot\(\);\s*$/,'\n'));
  load('app.js');load('image-tools.js');load('sort-tools.js');load('delete-tools.js');load('bulk-delete.js');load('jobs.js');
  run(`state.pid='A';state.request=1;state.boot={image_types:{},products:[],families:[]};state.current={images:[]};
       toast=()=>{};scheduleCoverageRefresh=()=>{};syncCanRefresh=()=>false;`);
  return {run,load,context,node,timers,listeners};
}

test('similarity includes all filtered images before pagination, keeps every image, and invalidates on filter change',async()=>{
  const h=harness(),requests=[];
  h.context.api=async(url,body)=>{requests.push(body);return {state:'ready',order:body.groups.flat().reverse(),analysed:120,total:120,missing_ids:[]};};
  h.run(`state.current.images=Array.from({length:120},(_,i)=>({id:'im'+String(i).padStart(3,'0'),name:'Image '+i,source:'Dropbox',association:{tier:'folder'},original:{dropbox_content_hash:'hash'+i}}));
    state.limit=24;state.imageSort=[{key:'similarity',direction:'asc'}];renderGrid=()=>{};`);
  assert.equal(h.run('filteredImages().length'),120);
  await h.timers.shift()();await new Promise(setImmediate);
  assert.equal(requests[0].groups[0].length,120);
  assert.equal(h.run('filteredImages().slice(0,state.limit)[0].id'),'im119');
  h.run('state.limit=48');
  assert.equal(h.run('filteredImages().slice(0,state.limit).length'),48);
  assert.equal(requests.length,1);
  h.run("state.imageSearch='Image 11';filteredImages();");await h.timers.shift()();await new Promise(setImmediate);
  assert.equal(requests[1].groups[0].length,11);
});

test('multi sort groups before similarity; later criteria order anchors and ties',()=>{
  const h=harness();
  h.run(`state.current.images=[{id:'A',name:'10',folder_label:'First',original:{bytes:10}},
    {id:'B',name:'2',folder_label:'First',original:{bytes:20}},{id:'C',name:'1',folder_label:'Second',original:{bytes:30}}];
    state.imageSort=[{key:'folder',direction:'asc'},{key:'similarity',direction:'asc'},{key:'bytes',direction:'desc'}];sortImages(state.current.images);`);
  assert.deepEqual(JSON.parse(h.run('state.sortJobKey'))[0],[['B','A'],['C']]);
});

test('close confirmed bulk dialog while queue response is pending; background job is retained and new dialog is not replaced',async()=>{
  const h=harness();let release,tracked;
  h.context.api=async()=>new Promise(resolve=>{release=resolve;});
  h.context.trackNativeJob=async job=>{tracked=job;};
  h.run(`bulkDeletion={phase:'review',entries:[],plan:{batch_id:'batch1',files:[]}};renderBulkDelete=()=>{};`);
  h.node('#delete-dialog').open=true;
  const pending=h.run('executeBulkDeletion()');
  h.run('closeBulkDelete()');assert.equal(h.node('#delete-dialog').open,false);
  h.run("bulkDeletion={phase:'choices',marker:'new review'};");h.node('#delete-dialog').open=true;
  release({id:'delete-batch-batch1',state:'queued'});await pending;
  assert.equal(h.node('#delete-dialog').open,true);assert.equal(h.run('bulkDeletion.marker'),'new review');
  assert.equal(tracked.id,'delete-batch-batch1');
});

test('single deletion response cannot close a subsequently opened bulk dialog',async()=>{
  const h=harness();let release;
  h.context.api=async()=>new Promise(resolve=>{release=resolve;});h.context.trackNativeJob=async()=>{};
  h.context.form={querySelector:()=>({disabled:false})};
  h.run("deletePlan={operation_id:'one',file:{id:'id:one'}};deletionView=1;");h.node('#delete-dialog').open=true;
  const pending=h.run('executeDeletion(form)');h.run('deletionView=2;');
  release({id:'delete-one',state:'queued'});await pending;assert.equal(h.node('#delete-dialog').open,true);
});

test('lost queue response discovers committed job without retrying deletion',async()=>{
  const h=harness();let calls=0;
  h.context.api=async()=>{calls++;throw Error('Connection lost');};h.context.findNativeJob=async()=>({state:'queued'});
  h.run(`bulkDeletion={phase:'review',entries:[],plan:{batch_id:'batch1',files:[]}};renderBulkDelete=()=>{};`);
  h.node('#delete-dialog').open=true;await h.run('executeBulkDeletion()');
  assert.equal(calls,1);assert.equal(h.node('#delete-dialog').open,false);
});

test('late background gallery refresh never overwrites a different product or unsaved edits',async()=>{
  const h=harness();let release;
  h.context.api=async url=>url==='/api/bootstrap'?{assignments:[]}:new Promise(resolve=>{release=resolve;});
  h.context.syncCanRefresh=()=>true;
  const pending=h.run('refreshNativeView()');await new Promise(setImmediate);
  h.run("state.pid='B';state.request=2;state.current={name:'New sculpture'};state.dirty.add('field-Name');");
  release({name:'Old sculpture',reviews:[]});await pending;
  assert.equal(h.run('state.current.name'),'New sculpture');assert.equal(h.run("state.dirty.has('field-Name')"),true);
});

test('closing bulk deletion uses no navigation/unload blocker',()=>{
  const h=harness();h.run("bulkDeletion={phase:'executing'};");h.node('#delete-dialog').open=true;
  h.run('closeBulkDelete()');assert.equal(h.node('#delete-dialog').open,false);assert.equal(h.run('bulkDeletion'),null);
  assert.doesNotMatch(fs.readFileSync(path.resolve(__dirname,'../static/bulk-delete.js'),'utf8'),/beforeunload/);
});
