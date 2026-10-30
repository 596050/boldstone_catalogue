const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),test=require('node:test');
function harness(){
  const nodes=new Map(),listeners={},timers=[];
  const node=s=>{if(!nodes.has(s))nodes.set(s,{innerHTML:'',textContent:'',open:false,checked:true,disabled:false,scrollTop:0,
    close(){this.open=false;},showModal(){this.open=true;},addEventListener(){},classList:{toggle(){}},querySelector:()=>null,querySelectorAll:()=>[]});return nodes.get(s);};
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

test('still-present files show a fresh review route and safe error details',()=>{
  const h=harness();
  h.run(`nativeJobsLoaded=true;nativeJobStatus={jobs:[{id:'old-job',kind:'delete',label:'Delete 1 reviewed file',state:'needs_review',updated_at:'2026-10-27T17:00:00Z',files:[{id:'id:one',name:'one.jpg'}],can_review_remaining:true,progress:{results:[{file_id:'id:one',state:'present',delete_error:{error_code:'RateLimitError',request_id:'request-123'}}]}}]};renderNativeJobs();`);
const html=h.node('#jobs-dialog').innerHTML;
  assert.match(html,/File present - ready for a new review/);
  assert.match(html,/Review remaining files/);
  assert.match(html,/RateLimitError/);assert.match(html,/request-123/);
  assert.doesNotMatch(html,/data-check-job=/);
});

test('worker errors update Jobs and the navbar even when saved jobs have not changed',()=>{
  const h=harness();
  h.run(`nativeJobsLoaded=true;nativeJobStatus={jobs:[]};`);
  const before=h.run('nativeJobsSignature()');
  h.run(`nativeJobStatus.worker={state:'retrying',error:'OperationalError: disk I/O error',retry_at:2000000000};renderNativeJobs();renderNativeJobButton();`);
  assert.notEqual(before,h.run('nativeJobsSignature()'));
  assert.match(h.node('#jobs-dialog').innerHTML,/File jobs are retrying after a local server error/);
  assert.match(h.node('#jobs-dialog').innerHTML,/uncertain deletions and moves are not repeated/);
  assert.match(h.node('#jobs-count').textContent,/!/);
  h.run(`nativeJobStatus.worker={state:'running',error:''};renderNativeJobs();renderNativeJobButton();`);
  assert.doesNotMatch(h.node('#jobs-dialog').innerHTML,/disk I\/O error/);
  assert.doesNotMatch(h.node('#jobs-count').textContent,/!/);
});

test('stopped organisation jobs show current image and folder links with escaped names',()=>{
  const h=harness();
  h.run(`nativeJobsLoaded=true;nativeJobStatus={jobs:[{id:'old-move',kind:'organise',state:'needs_review',
    label:'Old filename.jpg',updated_at:'2026-10-29',files:[],result:{},asset_id:'id:one',message:'Choose components',
    image:{id:'id:one',name:'Current <photo>.jpg',url:'https://www.dropbox.com/preview/current.jpg',folder_url:'https://www.dropbox.com/home/current'}}]};renderNativeJobs();`);
  const html=h.node('#jobs-dialog').innerHTML;
  assert.match(html,/Current &lt;photo&gt;.jpg/);
  assert.match(html,/href="https:\/\/www.dropbox.com\/preview\/current.jpg"/);
  assert.match(html,/href="https:\/\/www.dropbox.com\/home\/current"/);
  assert.match(html,/Choose components/);
});

test('planning again immediately tracks the returned job even while an older poll is in flight',async()=>{
  const h=harness();let tracked=null;const messages=[];
  h.context.api=async()=>({id:'replacement',kind:'organise',state:'queued',label:'Photo.jpg'});
  h.context.trackNativeJob=async job=>{tracked=job;};
  h.context.pollNativeJobs=async()=>null;
  h.context.toast=message=>messages.push(message);
  h.context.renderNativeJobs=()=>{};
  const button={disabled:false,dataset:{replanJob:'old'},hasAttribute:()=>false};
  await h.listeners.click.at(-1)({target:{closest:()=>button}});
  assert.equal(tracked?.id,'replacement');
  assert.equal(button.disabled,false);
  assert.match(messages.join(' '),/queued|Jobs/);
});

test('a poll started before queueing cannot erase the newly returned job',async()=>{
  const h=harness();let release,reads=0;
  const job={id:'new-move',kind:'organise',state:'queued',label:'Photo.jpg',updated_at:'2026-10-29T15:00:00Z'};
  h.context.queuedJob=job;
  h.context.api=async()=>{
    reads++;
    if(reads===1)return new Promise(resolve=>{release=resolve;});
    return {jobs:[job],active_count:1};
  };
  const stale=h.run('pollNativeJobs()');
  const tracking=h.run('trackNativeJob(queuedJob)');
  release({jobs:[],active_count:0});
  await Promise.all([stale,tracking]);
  assert.equal(h.run('nativeJobStatus.jobs[0]?.id'),'new-move');
  assert.equal(reads,2);
});

test('later verified deletion clears attention while preserving its original attempt explanation',()=>{
  const h=harness();
  h.run(`nativeJobsLoaded=true;nativeJobStatus={jobs:[{id:'old-job',kind:'delete',label:'Delete 1 reviewed file',state:'completed',updated_at:'2026-10-27T17:00:00Z',files:[{id:'id:one',name:'one.jpg'}],progress:{results:[{file_id:'id:one',state:'deleted',resolved_by_operation_id:'new-operation'}]}}]};renderNativeJobs();renderNativeJobButton();`);
  assert.match(h.node('#jobs-dialog').innerHTML,/Completed by a later confirmed deletion/);
  assert.match(h.node('#jobs-dialog').innerHTML,/1 of 1 verified/);
  assert.doesNotMatch(h.node('#jobs-dialog').innerHTML,/data-review-job-remaining=/);
  assert.equal(h.node('#jobs-count').textContent,'0');
});

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

test('updated original SHA invalidates a ready similarity order even with the same preview marker',()=>{
  const h=harness();
  h.run(`state.current.images=[{id:'A',original:{sha256:'old'}},{id:'B'}];
    state.imageSort=[{key:'similarity',direction:'asc'}];sortImages(state.current.images);
    similarityJobs.set(state.sortJobKey,{state:'ready',order:['B','A'],analysed:2,total:2,missing_ids:[]});`);
  const before=h.run('state.sortJobKey');
  h.run("state.current.images[0].original.sha256='new';sortImages(state.current.images);");
  assert.notEqual(h.run('state.sortJobKey'),before);
  assert.equal(h.run('similarityJobs.get(state.sortJobKey).state'),'queued');
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
  h.context.api=async url=>url==='/api/bootstrap'?{assignments:[],products:[{id:h.run('state.pid')}]}:new Promise(resolve=>{release=resolve;});
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

test('rename recovery is offered only when the server confirms an unattempted rejection',()=>{
  const h=harness();
  h.run(`nativeJobsLoaded=true;nativeJobStatus={jobs:[{id:'rejected',kind:'delete',state:'needs_review',label:'Delete image',updated_at:'2026-10-27',files:[],can_resume_rename:true}],deletion_activity:{}};renderNativeJobs();`);
  assert.match(h.node('#jobs-dialog').innerHTML,/Resume after verified rename/);
  h.run(`nativeJobStatus.jobs[0].state='uncertain';nativeJobStatus.jobs[0].can_resume_rename=false;renderNativeJobs();`);
  assert.doesNotMatch(h.node('#jobs-dialog').innerHTML,/Resume after verified rename/);
  assert.match(h.node('#jobs-dialog').innerHTML,/Check result/);
});

test('file results show current and originally reviewed names with verified rename evidence',()=>{
  const h=harness();
  const html=h.run(`deletionResultHTML({files:[{id:'id:one',name:'old.jpg'}]},{file_id:'id:one',state:'deleted',rename_reconciliation:{current_name:'new<&>.jpg',reviewed_name:'old.jpg'}})`);
  assert.match(html,/new&lt;&amp;&gt;\.jpg/);assert.match(html,/Reviewed as: old.jpg/);
  assert.match(html,/Deleted - absence verified/);assert.match(html,/original deletion confirmation retained/);
});

test('rename recovery can finish after the jobs modal closes without reopening it',async()=>{
  const h=harness(),calls=[];let release;
  h.context.api=async(url,body)=>{calls.push({url,body});return url==='/api/jobs/resume-rename'?new Promise(resolve=>{release=resolve;}):{jobs:[],deletion_activity:{}};};
  const button={dataset:{resumeRenameJob:'old-job'},id:'',disabled:false,hasAttribute:()=>false};
  h.node('#jobs-dialog').open=true;
  const pending=h.listeners.click.map(f=>f({target:{closest:()=>button}}));
  await new Promise(setImmediate);assert.equal(button.disabled,true);
  h.node('#jobs-dialog').close();release({id:'replacement',state:'queued'});await Promise.all(pending);
  assert.equal(h.node('#jobs-dialog').open,false);assert.equal(button.disabled,false);
  assert.equal(calls.filter(c=>c.url==='/api/jobs/resume-rename').length,1);
  assert.equal(calls[0].body.job_id,'old-job');
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

test('expanded deletion results keep updating without losing expansion, focus or scroll',async()=>{
  const h=harness(),dialog=h.node('#jobs-dialog');dialog.open=true;dialog.scrollTop=120;
  let expanded={open:true,closest:()=>({dataset:{jobId:'job'}})},focused=false,html='';
  const summary={focus:()=>{focused=true;}};
  const section={dataset:{jobId:'job'},querySelector:()=>summary};
  dialog.querySelectorAll=selector=>selector==='.native-job details[open]'?(expanded.open?[expanded]:[]):
    selector==='.native-job details'?[expanded]:selector==='.native-job'?[section]:[];
  Object.defineProperty(dialog,'innerHTML',{get:()=>html,set:value=>{html=value;expanded={open:false,closest:()=>section};dialog.scrollTop=0;}});
  h.context.document.activeElement={tagName:'SUMMARY',attributes:[],closest:selector=>selector==='[data-job-id]'?section:dialog};
  let done=false;
  h.context.api=async()=>({jobs:[{id:'job',kind:'delete_batch',state:done?'completed':'running',label:'Delete 2 files',files:[],progress:{results:[
    {file_id:'one',state:done?'deleted':'executing'},{file_id:'two',state:done?'deleted':'not_started'}]}}],active_count:done?0:1});
  await h.run('pollNativeJobs()');assert.match(html,/0 of 2 verified/);
  done=true;await h.run('pollNativeJobs()');
  assert.match(html,/2 of 2 verified/);assert.match(html,/Completed/);
  assert.equal(expanded.open,true);assert.equal(dialog.scrollTop,120);assert.equal(focused,true);
});

test('stopped filename worker is attention, not an active running job',()=>{
  const h=harness();
  h.run(`nativeJobStatus={jobs:[{state:'queued'}],active_count:1,reservation:{active:true},filename_job:{state:'needs_review'}};renderNativeJobButton();`);
  assert.equal(h.node('#jobs-count').textContent,'1 ! 1');
  assert.equal(h.node('#jobs-open').title,'0 running · 1 queued · 1 need attention');
  const html=h.run(`filenameProgressHTML({state:'needs_review',correct:5994,total:5994,percent:100,final_checks:'failed',verification_errors:[{check:'original_shared_link_retained',count:6}],stage:'Final filename checks need review'})`);
  assert.match(html,/Needs review - 6 failed/);assert.doesNotMatch(html,/Filename renaming complete/);
});

test('poll failure visibly marks cached job results as stale and success clears it',async()=>{
  const h=harness();h.node('#jobs-dialog').open=true;
  let failed=false;
  h.context.api=async()=>{if(failed)throw Error('offline');return {jobs:[],active_count:0};};
  await h.run('pollNativeJobs()');failed=true;await h.run('pollNativeJobs()');
  assert.match(h.node('#jobs-status').textContent,/offline.*last received status/);
  assert.match(h.node('#jobs-count').textContent,/!/);
  failed=false;await h.run('pollNativeJobs()');
  assert.doesNotMatch(h.node('#jobs-dialog').innerHTML,/last received status/);
  assert.equal(h.node('#jobs-count').textContent,'0');
});

test('dismissed warnings remain in history without an attention badge',()=>{
 const h=harness();h.run(`nativeJobStatus={jobs:[{id:'old',kind:'organise',label:'Stopped move',state:'needs_review',dismissed_at:'2026-10-28',updated_at:'2026-10-28',can_dismiss:true,files:[],result:{},message:'Folder ambiguous'}],dismissed_count:1};showDismissedJobs=true;renderNativeJobButton();renderNativeJobs();`);
 assert.equal(h.node('#jobs-count').textContent,'0');assert.match(h.node('#jobs-dialog').innerHTML,/Restore to list/);
 assert.match(h.node('#jobs-dialog').innerHTML,/Folder ambiguous/);assert.match(h.node('#jobs-dialog').innerHTML,/Clear finished jobs/);
});

test('own overview changes refresh a selected gallery without clearing its selections',async()=>{
 const h=harness();h.context.api=async url=>url==='/api/bootstrap'?{products:[],assignments:[],coverage:{}}:{images:[],reviews:[]};
 h.run(`state.selected.add('photo');state.tab='images';renderList=()=>{};renderMain=()=>{};captureGalleryPosition=()=>null;restoreGalleryPosition=()=>{};`);
 assert(await h.run('refreshNativeView({allowSelection:true})'));assert(h.run("state.selected.has('photo')"));
 h.run("state.dirty.add('draft')");assert.equal(await h.run('refreshNativeView({allowSelection:true})'),false);
});
