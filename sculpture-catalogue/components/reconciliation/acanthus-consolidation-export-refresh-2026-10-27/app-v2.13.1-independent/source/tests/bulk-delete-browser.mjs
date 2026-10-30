// Isolated QA: every deletion endpoint is intercepted; no native Dropbox calls.
import { chromium } from '/Users/tprice/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs';
import fs from 'node:fs/promises';
const base='http://127.0.0.1:8768',pid='BSI-C02D6DF365D3';
const ids=['id:cnqzTNngPVsAAAAAAAt4Uw','id:cnqzTNngPVsAAAAAAAt4DA','id:cnqzTNngPVsAAAAAAAt-hQ'];
const out='/Users/tprice/Library/Application Support/BoldstoneReview-QA-bulk-delete-20261025/qa';
await fs.mkdir(out,{recursive:true});
const browser=await chromium.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true});
const page=await browser.newPage({viewport:{width:1440,height:1080}}),checks=[],errors=[],requests=[];
page.on('pageerror',e=>errors.push(e.message));
page.on('dialog',async d=>{errors.push('Unexpected dialog: '+d.message());await d.dismiss();});
const product=await (await page.request.get(base+'/api/products/'+pid)).json();
const images=Object.fromEntries(product.images.map(a=>[a.id,a]));
const plans=new Map(),batches=new Map();let mode='success',releasePrepare=null,executeCalls=0;
const ok=(value,label)=>{if(!value)throw Error(label);checks.push(label);};
await page.route('**/api/deletions/**',async route=>{
  const action=new URL(route.request().url()).pathname.split('/').at(-1),body=route.request().postDataJSON();
  requests.push({action,body});
  const reply=async result=>route.fulfill({json:result});
  if(action==='prepare'){
    if(mode==='preparation-failure')return route.fulfill({status:409,json:{error:'File revision changed'}});
    if(mode==='delayed-prepare')await new Promise(resolve=>{releasePrepare=resolve;});
    const image=images[body.asset_id],keeper=images[body.keeper_id],operation_id='qa-'+plans.size;
    const file=a=>({id:a.id,name:a.name,path:'/BOLDSTONE MASTER/Products/01 Wall Sculptures/Test/'+a.name,revision:'reviewed-qa-revision',bytes:a.original.bytes,modified:'2026-10-25T12:00:00Z',sharing:{links:[{url:'https://www.dropbox.com/test-review',name:'Parent folder',direct:false}],explicit_members:false}});
    const plan={operation_id,file:file(image),keeper:keeper?file(keeper):null,reason:body.reason,context:{products:[{name:product.name,choice:{data:{uses:['advertising']}}}],aliases:[image.id]},expires_at:Date.now()/1000+600};
    plans.set(operation_id,plan);return reply(plan);
  }
  if(action==='prepare-batch'){
    const batch={batch_id:'batch-'+batches.size,operation_ids:body.operation_ids,files:body.operation_ids.map(id=>({id:plans.get(id).file.id,revision:plans.get(id).file.revision})),state:'prepared'};
    batches.set(batch.batch_id,batch);return reply(batch);
  }
  if(action==='execute-batch'){
    executeCalls++;
    const batch=batches.get(body.batch_id);
    ok(JSON.stringify(body.confirm_files)===JSON.stringify(batch.files)&&body.confirmed===true,'Confirmation sends the entire reviewed ID/revision list');
    if(mode==='execute-rejection')return route.fulfill({status:409,json:{error:'A selected image changed. Review again.'}});
    batch.state=mode==='uncertain'?'partial':mode==='lost-response'?'executing':'deleted';
    batch.results=batch.operation_ids.map((id,index)=>({operation_id:id,file_id:plans.get(id).file.id,state:mode==='uncertain'?(index===0?'deleted':index===1?'uncertain':'not_started'):mode==='lost-response'?(index===0?'executing':'not_started'):'deleted'}));
    if(mode==='lost-response')return route.abort();
    return reply(batch);
  }
  if(action==='batch-status')return reply(batches.get(body.batch_id));
  throw Error('Unexpected deletion endpoint: '+action);
});
const selection=id=>page.locator(`[data-select-image="${id}"]`);
async function select(selected){
  if(await page.locator('#clear-selection').isVisible())await page.locator('#clear-selection').click();
  for(const id of selected)await selection(id).check();
  await page.locator('#bulk-delete').click();
}
async function unwanted(){
  for(const field of await page.locator('[data-bulk-delete-reason]').all())await field.selectOption('unwanted');
}
async function review(){
  await page.getByRole('button',{name:'Review selected files',exact:true}).click();
  await page.locator('#bulk-delete-confirm-form').waitFor();
}
async function confirm(){
  await page.locator('#bulk-delete-confirm').check();
  await page.locator('#bulk-delete-confirm-form button[type=submit]').click();
  await page.locator('#bulk-delete-done').waitFor();
}
try{
  await page.goto(base+'/#'+pid+'?scope=all');await selection(ids[0]).waitFor();
  ok(await page.locator('#bulk-bar').isHidden(),'Selection bar is hidden without a selection');
  await select(ids.slice(0,2));
  ok(await page.locator('#bulk-count').innerText()==='2 selected','Selected-image count is accurate');
  ok(await page.locator('.bulk-delete-item').count()===2,'One review lists exactly the two selected files');
  ok((await page.locator('#bulk-bar button').allTextContents()).join('|').includes('Move / copy…|Delete…|Clear'),'Delete button sits between Move / copy and Clear');
  for(const select of await page.locator('[data-bulk-delete-keeper]').all()){
    const values=await select.locator('option').evaluateAll(options=>options.map(o=>o.value));
    ok(!ids.slice(0,2).some(id=>values.includes(id))&&values.includes(ids[2]),'All selected files are excluded from keeper choices');
  }
  await page.getByRole('button',{name:'Review selected files',exact:true}).click();
  ok(requests.length===0,'Missing keepers prevent preparation');
  for(const select of await page.locator('[data-bulk-delete-keeper]').all())await select.selectOption(ids[2]);
  ok(await page.getByText('Keep this file',{exact:true}).count()===2,'Each chosen keeper has a picture');
  await review();
  ok(await page.locator('#bulk-delete-confirm-form button[type=submit]').isDisabled(),'Batch execution requires explicit final confirmation');
  const facts=await page.locator('.delete-facts').allTextContents();
  ok(ids.slice(0,2).every(id=>facts.some(f=>f.includes(id)&&f.includes('reviewed-qa-revision'))),'Exact native file IDs and revisions appear for both files');
  ok(await page.getByText('1 shared or parent-folder link(s)',{exact:true}).count()===2,'Sharing is reviewed for every file');
  await page.screenshot({path:out+'/selected-delete-review.png',fullPage:true});
  await page.locator('#bulk-delete-close').click();
  ok(executeCalls===0,'Closing the reviewed batch deletes nothing');
  ok(await page.evaluate(()=>state.dirty.size===0),'Deletion controls do not create unsaved image edits');

  // Unsupported sources are explicit; selected exact-byte aliases cannot be keepers.
  await page.evaluate(id=>{state.current.images.find(a=>a.id===id).source='Shopify';},ids[1]);
  await select(ids.slice(0,2));
  ok((await page.locator('.bulk-delete-skipped').innerText()).includes(images[ids[1]].name),'Non-Dropbox selection is listed as not deletable');
  ok(await page.locator('.bulk-delete-item').count()===1,'Only Dropbox originals enter the deletion review');
  await page.locator('#bulk-delete-close').click();
  await page.evaluate(([target,alias])=>{state.current.images.find(a=>a.id===alias).source='Dropbox';state.current.images.find(a=>a.id===target).duplicates=[{id:alias}];},[ids[0],ids[2]]);
  await select(ids.slice(0,2));
  ok(!(await page.locator('[data-bulk-delete-keeper="0"] option').evaluateAll(os=>os.map(o=>o.value))).includes(ids[2]),'Selected-file aliases are excluded from keeper choices');
  await page.locator('#bulk-delete-close').click();
  await page.reload();await selection(ids[0]).waitFor();

  mode='preparation-failure';await select(ids.slice(0,2));await unwanted();
  await page.getByRole('button',{name:'Review selected files',exact:true}).click();
  await page.locator('#bulk-delete-result').filter({hasText:'Nothing has been deleted'}).waitFor();
  ok(executeCalls===0,'Failed metadata preparation never executes a deletion');
  await page.locator('#bulk-delete-close').click();

  mode='delayed-prepare';await select(ids.slice(0,2));await unwanted();
  await page.getByRole('button',{name:'Review selected files',exact:true}).click();
  for(let i=0;i<50&&!releasePrepare;i++)await new Promise(r=>setTimeout(r,20));
  ok(!!releasePrepare,'Preparation is in flight for cancellation test');
  await page.locator('#bulk-delete-close').click();releasePrepare();mode='success';
  await page.waitForTimeout(100);
  ok(await page.locator('#delete-dialog').isHidden()&&executeCalls===0,'Closing an in-flight review cannot reopen it or delete files');

  await select(ids.slice(0,2));await unwanted();await review();
  await page.locator('#bulk-delete-back').click();
  ok(await page.locator('#bulk-delete-choice-form').isVisible(),'Back allows editing the selection review before confirmation');
  await review();await confirm();
  ok((await page.locator('.bulk-delete-status').allTextContents()).every(s=>s.includes('Deleted — absence verified')),'Successful results are reported per reviewed file');
  ok(await page.locator('#bulk-bar').isHidden(),'Verified deletions clear the selected bar');
  await page.locator('#bulk-delete-done').click();

  mode='uncertain';await select(ids);await unwanted();await review();await confirm();
  const statuses=await page.locator('.bulk-delete-status').allTextContents();
  ok(statuses[0].includes('Deleted')&&statuses[1].includes('unconfirmed')&&statuses[2].includes('Not attempted'),'Partial results distinguish deleted, uncertain and unattempted files');
  ok(await page.locator('#bulk-count').innerText()==='2 selected','Files without verified deletion remain selected');
  ok(await page.getByRole('button',{name:/Delete \d files from Dropbox/}).count()===0,'Partial batch has no destructive retry button');
  await page.locator('#bulk-delete-done').click();

  mode='execute-rejection';await select(ids.slice(0,2));await unwanted();await review();await confirm();
  ok((await page.locator('.bulk-delete-status').allTextContents()).every(s=>s.includes('Not attempted')),'Rejected batch confirmation reports files not attempted');
  await page.locator('#bulk-delete-done').click();

  mode='lost-response';await select(ids.slice(0,2));await unwanted();await review();
  const before=executeCalls;await confirm();
  ok(executeCalls===before+1&&requests.at(-1).action==='batch-status','Lost response triggers one read-only status check and no deletion retry');
  ok((await page.locator('#bulk-delete-result').innerText()).includes('still processing'),'A running batch is not falsely reported as completed');
  await page.locator('#bulk-delete-done').click();

  mode='success';
  for(const width of [1440,390,320]){
    await page.setViewportSize({width,height:1080});await select(ids.slice(0,2));
    ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Selection bar and dialog fit '+width+'px viewport');
    ok(await page.locator('#delete-dialog').evaluate(d=>d.scrollWidth<=d.clientWidth),'Deletion dialog has no horizontal overflow at '+width+'px');
    if(width===390)await page.screenshot({path:out+'/selected-delete-mobile.png',fullPage:true});
    await page.locator('#bulk-delete-close').click();
  }
  ok(errors.length===0,'No browser exceptions or unexpected discard prompts');
  await fs.writeFile(out+'/browser-checks.json',JSON.stringify({status:'PASS',checks,errors,intercepted_requests:requests,simulated_execute_requests:executeCalls,native_delete_calls:0},null,2));
  console.log(JSON.stringify({status:'PASS',checks:checks.length,simulated_execute_requests:executeCalls,native_delete_calls:0}));
}finally{await browser.close();}
