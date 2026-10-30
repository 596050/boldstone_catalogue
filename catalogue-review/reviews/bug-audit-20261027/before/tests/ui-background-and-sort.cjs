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

test('mixed selection shows queued original and reviews only the free file',async()=>{
  const h=harness();
  h.context.api=async()=>({jobs:[],active_count:1,deletion_activity:{'id:busy':{file_id:'id:busy',name:'Busy.jpg',state:'queued',kind:'delete',job_id:'existing'}}});
  h.run(`state.current.images=[{id:'id:busy',name:'Busy.jpg',source:'Dropbox'},{id:'id:free',name:'Free.jpg',source:'Dropbox'}];state.selected=new Set(['id:busy','id:free']);`);
  await h.run('openBulkDelete()');
  assert.equal(h.run('bulkDeletion.entries.length'),1);assert.equal(h.run('bulkDeletion.entries[0].image.id'),'id:free');
  assert.match(h.node('#delete-dialog').innerHTML,/Busy.jpg - Queued/);
  assert.match(h.node('#delete-dialog').innerHTML,/Review 1 selected Dropbox file/);
  assert.equal(h.run('bulkDeleteKeepers(bulkDeletion).length'),0);
});

test('single busy original shows existing job instead of another delete form',async()=>{
  const h=harness();let calls=0;
  h.context.api=async()=>{calls++;return {jobs:[],active_count:1,deletion_activity:{'id:busy':{file_id:'id:busy',name:'Busy.jpg',state:'running',kind:'delete'}}};};
  h.run(`state.current.images=[{id:'id:busy',name:'Busy.jpg',source:'Dropbox'}];`);
  await h.run("openDelete('id:busy')");
  assert.match(h.node('#delete-dialog').innerHTML,/Busy.jpg - Running/);
  assert.doesNotMatch(h.node('#delete-dialog').innerHTML,/delete-choice-form/);assert.equal(calls,1);
});

test('selection containing only busy files cannot offer a zero-file confirmation',async()=>{
  const h=harness();
  h.context.api=async()=>({jobs:[],active_count:1,deletion_activity:{'id:busy':{file_id:'id:busy',name:'Busy.jpg',state:'queued',kind:'delete'}}});
  h.run(`state.current.images=[{id:'id:busy',name:'Busy.jpg',source:'Dropbox'}];state.selected.add('id:busy');`);
  await h.run('openBulkDelete()');
  assert.match(h.node('#delete-dialog').innerHTML,/No additional files to delete/);
  assert.doesNotMatch(h.node('#delete-dialog').innerHTML,/type="submit"/);
});

test('closed deletion preflight cannot overwrite a new dialog',async()=>{
  const h=harness();let release;
  h.context.api=()=>new Promise(resolve=>{release=resolve;});
  h.run(`state.current.images=[{id:'id:free',name:'Free.jpg',source:'Dropbox'}];state.selected=new Set(['id:free']);`);
  const pending=h.run('openBulkDelete()');h.run('closeBulkDelete()');
  h.node('#delete-dialog').innerHTML='New review';h.node('#delete-dialog').open=true;
  release({jobs:[],active_count:0,deletion_activity:{}});await pending;
  assert.equal(h.node('#delete-dialog').innerHTML,'New review');assert.equal(h.run('bulkDeletion'),null);
});

test('uncertain job becoming completed refreshes again and clears deleted selection',async()=>{
  const h=harness();let result,refreshes=0;
  h.context.api=async()=>result;h.context.syncCanRefresh=()=>true;h.context.refreshNativeView=async()=>{refreshes++;};
  h.run("state.selected.add('id:one');");
  result={jobs:[{id:'job',kind:'delete_batch',state:'uncertain',updated_at:'1',progress:{results:[{file_id:'id:one',state:'uncertain'}]}}],active_count:0};
  await h.run('pollNativeJobs()');assert.equal(refreshes,1);
  result={jobs:[{id:'job',kind:'delete_batch',state:'completed',updated_at:'2',progress:{results:[{file_id:'id:one',state:'deleted'}]}}],active_count:0};
  await h.run('pollNativeJobs()');assert.equal(refreshes,2);assert.equal(h.run("state.selected.has('id:one')"),false);
});

test('jobs loading state does not briefly claim no jobs exist and concurrent polls await one request',async()=>{
  const h=harness();let release,calls=0;
  h.context.api=()=>{calls++;return new Promise(resolve=>{release=resolve;});};
  h.run('renderNativeJobs()');assert.match(h.node('#jobs-dialog').innerHTML,/Loading current jobs/);
  assert.doesNotMatch(h.node('#jobs-dialog').innerHTML,/No background jobs yet/);
  const first=h.run('pollNativeJobs()'),second=h.run('refreshDeletionActivity()');assert.equal(calls,1);
  release({jobs:[],active_count:0,deletion_activity:{'id:test':{state:'queued'}}});
  await first;assert.equal((await second)['id:test'].state,'queued');
});

test('lost queue response checks fresh status when a prior poll predates the commit',async()=>{
  const h=harness();let calls=0;
  h.context.api=async()=>({jobs:++calls===1?[]:[{id:'job',state:'queued'}],active_count:0});
  assert.equal((await h.run("findNativeJob('job')")).id,'job');assert.equal(calls,2);
});

test('failed preflight offers retry and never presents a deletion confirmation',async()=>{
  const h=harness();h.context.api=async()=>{throw Error('offline');};
  h.run(`state.current.images=[{id:'id:free',name:'Free.jpg',source:'Dropbox'}];state.selected=new Set(['id:free']);`);
  await h.run('openBulkDelete()');assert.equal(h.run('bulkDeletion.phase'),'check_failed');
  assert.match(h.node('#delete-dialog').innerHTML,/Try again/);assert.doesNotMatch(h.node('#delete-dialog').innerHTML,/bulk-delete-confirm-form/);
});

test('filename progress distinguishes verified files from the current pending batch',()=>{
  const h=harness();
  const html=h.run(`filenameProgressHTML({state:'running',correct:3892,total:6205,percent:62.7,pass_name:'Original pass',stage:'Dropbox is processing the current batch',batch_number:4,batch_files:1000,batch_state:'processing',batch_elapsed_seconds:970,heartbeat_age_seconds:42,heartbeat_stale:false})`);
  assert.match(html,/3,892 of 6,205 filenames verified/);assert.match(html,/value="3892"/);
  assert.match(html,/4 - 1,000 files/);assert.match(html,/16m 10s/);assert.match(html,/42s ago/);
});

test('completed filename progress remains visible after writer reservation is released',()=>{
  const h=harness();
  const html=h.run(`filenameJobSection({reservation:null,filename_job:{state:'completed',stage:'Filename renaming complete',correct:6000,total:6000,percent:100,pass_name:'Final verification'}})`);
  assert.match(html,/Filename renaming complete/);assert.match(html,/6,000 of 6,000/);
  assert.doesNotMatch(html,/Current batch/);
});

test('filename progress updates while deletion File results are expanded without replacing them',async()=>{
  const h=harness();h.node('#jobs-dialog').open=true;h.node('#jobs-dialog').querySelector=()=>({open:true});
  h.node('#jobs-dialog').innerHTML='Expanded results retained';
  h.context.api=async()=>({jobs:[],active_count:1,reservation:{label:'Dropbox filename renaming'},filename_job:{state:'running',correct:10,total:20,percent:50,stage:'Checking the completed batch'}});
  await h.run('pollNativeJobs()');
  assert.equal(h.node('#jobs-dialog').innerHTML,'Expanded results retained');
  assert.match(h.node('#filename-job-section').innerHTML,/10 of 20 filenames verified/);
});
