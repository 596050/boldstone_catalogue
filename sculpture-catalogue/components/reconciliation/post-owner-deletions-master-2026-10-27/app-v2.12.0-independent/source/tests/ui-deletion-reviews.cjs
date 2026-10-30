const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),test=require('node:test');
function harness(){
 const nodes=new Map(),listeners={};
 const node=s=>{if(!nodes.has(s))nodes.set(s,{innerHTML:'',textContent:'',open:true,checked:true,disabled:false,scrollTop:0,close(){this.open=false;},showModal(){this.open=true;},addEventListener(){},classList:{toggle(){}},querySelector:()=>null,querySelectorAll:()=>[]});return nodes.get(s);};
 const context=vm.createContext({console,URL,URLSearchParams,crypto:require('node:crypto').webcrypto,
 document:{querySelector:node,querySelectorAll:()=>[],addEventListener:(k,f)=>(listeners[k]||=[]).push(f)},window:{addEventListener(){},scrollY:0,scrollTo(){}},location:{hash:''},history:{replaceState(){}},localStorage:{getItem:()=>null,setItem(){}},setTimeout(){},clearTimeout(){},setInterval(){},clearInterval(){}});
 const run=s=>vm.runInContext(s,context);
 for(const f of ['app.js','image-tools.js','delete-tools.js','bulk-delete.js','jobs.js'])run(fs.readFileSync(path.resolve(__dirname,'../static',f),'utf8').replace(/\nboot\(\);\s*$/,'\n'));
 run(`state.boot={products:[],families:[]};state.pid='A';state.current={images:[]};toast=()=>{};syncCanRefresh=()=>false;`);
 const image=id=>({id,name:id+'.jpg',source:'Dropbox',original:{bytes:1},url:'',folder_url:''});
 const plan=id=>({operation_id:'op-'+id,file:{id,revision:'1',sharing:{links:[]},name:id+'.jpg',path:'/BOLDSTONE MASTER/'+id+'.jpg'},context:{products:[]}});
 const entry=(id,state='ready')=>({asset_id:id,name:id+'.jpg',reason:'unwanted',keeper_id:'',state,image:image(id),plan:state==='ready'?plan(id):null,error:state==='failed'?'Read failed':''});
 const job=(state='review_attention')=>({id:'review-123456789',kind:'delete_review',state,entries:[entry('id:ok'),entry('id:bad','failed')],counts:{ready:1,failed:1,skipped:0},total:2,checked:2});
 context.fixtureJob=job();context.fixtureImage=image;
 run(`bulkDeletion={phase:'choices',entries:[{image:fixtureImage('id:ok'),reason:'unwanted',keeper_id:'',plan:null}],skipped:[],busy:[],error:''};`);
 return {run,context,node,job,entry,image,plan};
}
test('queue selected checks once without holding the dialog or issuing per-file HTTP requests',async()=>{
 const h=harness(),requests=[];let release,tracked;
 h.context.api=async(url,body)=>{requests.push([url,body]);return new Promise(r=>release=r);};h.context.trackNativeJob=async j=>tracked=j;
 const pending=h.run('prepareBulkDeletion()');await h.run('prepareBulkDeletion()');
 h.run('closeBulkDelete()');release(h.job('running'));await pending;
 assert.equal(requests.length,1);assert.equal(requests[0][0],'/api/deletion-reviews');assert.equal(requests[0][1].entries.length,1);
 assert.equal(tracked.id,'review-123456789');assert.equal(h.node('#delete-dialog').open,false);
});
test('lost start response looks up the exact durable review without submitting again',async()=>{
 const h=harness(),calls=[];let post=0;
 h.context.api=async(url,body)=>{calls.push(url);if(body){post++;throw Error('Response lost');}return h.job();};h.context.trackNativeJob=async()=>{};
 await h.run('prepareBulkDeletion()');assert.equal(post,1);assert(calls[1].startsWith('/api/deletion-reviews/review-'));
 assert.equal(h.run('bulkDeletion.phase'),'checked');assert.equal(h.run('bulkDeletion.entries.length'),1);
});
test('failed checks are shown separately and never counted in the deletion confirmation',()=>{
 const h=harness();h.run('absorbDeletionReview(bulkDeletion,fixtureJob);renderBulkDelete();');
 const html=h.node('#delete-dialog').innerHTML;assert.match(html,/1 files ready for confirmation/);assert.match(html,/Continue with 1 checked files/);
 assert.match(html,/1 file\(s\) could not be checked/);assert.equal(h.run('bulkDeletion.entries[0].image.id'),'id:ok');
});
test('final confirmation includes the server checked subset and exact revisions only',async()=>{
 const h=harness();h.run('absorbDeletionReview(bulkDeletion,fixtureJob);bulkDeletion.review_id=fixtureJob.id;');
 h.context.api=async url=>url.endsWith('/plan')?{batch_id:'batch',files:[{id:'id:ok',revision:'1'}]}:h.job();
 await h.run('finalizeDeletionReview()');assert.equal(h.run('bulkDeletion.phase'),'review');assert.equal(h.run('bulkDeletion.plan.files.length'),1);
 assert.equal(h.run('bulkDeletion.plan.files[0].id'),'id:ok');assert.match(h.node('#delete-dialog').innerHTML,/I have checked all 1 items/);
});
test('late progress cannot overwrite a different review or reopen a closed dialog',async()=>{
 const h=harness();let release;h.context.api=async()=>new Promise(r=>release=r);
 h.run("bulkDeletion.phase='checking_files';bulkDeletion.review_id='review-123456789';");const pending=h.run('refreshBulkReview()');
 h.run("bulkDeletion={marker:'new',phase:'choices'};");release(h.job());await pending;assert.equal(h.run('bulkDeletion.marker'),'new');
});
test('progress polls use the compact job status while checks are running',async()=>{
 const h=harness();h.context.api=async()=>assert.fail('Unnecessary full-plan fetch');
 h.run("bulkDeletion.phase='checking_files';bulkDeletion.review_id=fixtureJob.id;fixtureJob.state='running';nativeJobStatus.jobs=[fixtureJob];");
 await h.run('refreshBulkReview()');assert.match(h.node('#delete-dialog').innerHTML,/2 of 2 files checked/);
});
test('large unwanted-image selections do not build a keeper menu for every file',()=>{
 const h=harness();h.run(`state.current.images=Array.from({length:400},(_,i)=>fixtureImage('id:'+i));bulkDeletion.entries=state.current.images.slice(0,181).map(image=>({image,reason:'unwanted',keeper_id:''}));renderBulkDelete();`);
 const html=h.node('#delete-dialog').innerHTML;assert.equal((html.match(/Choose the image to keep/g)||[]).length,181);
 assert(!html.includes('<option value="id:399"'));assert(html.length<500000);
});
test('failed progress refresh keeps the saved selection and an exit route',async()=>{
 const h=harness();h.context.api=async()=>{throw Error('Offline');};h.run("bulkDeletion.phase='checking_files';bulkDeletion.review_id='review-123456789';renderBulkDelete();");
 await h.run('refreshBulkReview()');assert.equal(h.run('bulkDeletion.entries.length'),1);assert.match(h.node('#bulk-delete-result').textContent,/remain saved/);assert.match(h.node('#delete-dialog').innerHTML,/bulk-delete-close/);
});
test('retry submits only the review ID and preserves the saved choices on the server',async()=>{
 const h=harness(),calls=[];h.run("absorbDeletionReview(bulkDeletion,fixtureJob);bulkDeletion.review_id=fixtureJob.id;");
 h.context.api=async(url,body)=>{calls.push([url,body]);return h.job('running');};h.context.trackNativeJob=async()=>{};
 await h.run('retryDeletionReview()');assert.equal(calls[0][0],'/api/deletion-reviews/retry');assert.deepEqual(JSON.parse(JSON.stringify(calls[0][1])),{review_id:'review-123456789'});
});
test('all failed checks offer retry without any deletion confirmation',()=>{
 const h=harness();h.context.fixtureJob={...h.job(),entries:[h.entry('id:bad','failed')],counts:{ready:0,failed:1,skipped:0},total:1,checked:1};
 h.run('absorbDeletionReview(bulkDeletion,fixtureJob);renderBulkDelete();');const html=h.node('#delete-dialog').innerHTML;
 assert.match(html,/bulk-review-retry/);assert(!html.includes('bulk-delete-confirm-form'));assert(!html.includes('bulk-review-finalize'));
});
