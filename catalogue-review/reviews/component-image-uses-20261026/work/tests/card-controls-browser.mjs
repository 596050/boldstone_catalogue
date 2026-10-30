// Isolated QA only. The deletion execute endpoint is never called against Dropbox.
import { chromium } from '/Users/tprice/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs';
import fs from 'node:fs/promises';
const base='http://127.0.0.1:8768',pid='BSI-C02D6DF365D3';
const aid='id:cnqzTNngPVsAAAAAAAt4Uw',keeper='id:cnqzTNngPVsAAAAAAAt-hQ';
const out='/Users/tprice/Library/Application Support/BoldstoneReview-QA-delete-controls-20261025/qa';
await fs.mkdir(out,{recursive:true});
const browser=await chromium.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true});
const page=await browser.newPage({viewport:{width:1440,height:1080}}),checks=[],errors=[],dialogs=[];
let deleteRequests=0;
page.on('pageerror',e=>errors.push(e.message));
page.on('dialog',async d=>{dialogs.push(d.message());await d.accept();});
await page.route('**/api/deletions/execute',async route=>{deleteRequests++;await route.abort();});
const ok=(v,label)=>{if(!v)throw Error(label);checks.push(label);};
const card=()=>page.locator('.image-card').filter({has:page.locator(`[data-quick=listing][data-id="${aid}"]`)});
const current=async()=>await (await page.request.get(base+'/api/products/'+encodeURIComponent(pid))).json();
const choice=async()=>{const p=await current();return p.reviews.find(r=>r.kind==='image'&&r.item_id===aid)?.data||{};};
const toggle=async use=>{await card().locator(`[data-quick=${use}]`).click();await page.waitForFunction(()=>!document.querySelector('[data-quick][disabled]'));};
const open=async()=>{await card().getByRole('button',{name:'Review ↗',exact:true}).click();};
const close=async()=>{await page.getByRole('button',{name:'Close image',exact:true}).click();await page.locator('#image-dialog').waitFor({state:'hidden'});};
const save=async form=>{await page.locator(form).getByRole('button',{name:'Save all image changes',exact:true}).click();await page.locator(form+' .save-state').filter({hasText:'All image changes saved'}).waitFor();};
try{
  await page.goto(base+'/#'+pid+'?scope=all',{waitUntil:'networkidle'});
  await page.locator('#image-grid').waitFor();
  await open();await close();ok(dialogs.length===0,'Untouched image detail closes without discard warning');
  let d=await choice();if(!d.uses?.includes('listing'))await toggle('listing');
  d=await choice();if(!d.uses?.includes('advertising'))await toggle('advertising');
  ok((await choice()).uses.includes('listing')&&(await choice()).uses.includes('advertising'),'Listing and advertising are saved together');
  ok(await card().locator('[data-quick=listing]').getAttribute('aria-pressed')==='true'&&await card().locator('[data-quick=advertising]').getAttribute('aria-pressed')==='true','Both purpose buttons show selected state');
  await page.reload({waitUntil:'networkidle'});
  ok(await card().locator('[data-quick=advertising]').getAttribute('aria-pressed')==='true','Both selections persist after reload');
  await toggle('listing');d=await choice();ok(!d.uses.includes('listing')&&d.uses.includes('advertising'),'Turning Listing off keeps advertising');
  await toggle('listing');await open();await page.locator('#image-form input[name=primary]').check();await save('#image-form');await close();
  await toggle('advertising');d=await choice();ok(d.primary&&d.uses.includes('listing')&&!d.uses.includes('advertising'),'Turning Ads off preserves listing primary');
  await toggle('advertising');
  await open();await page.locator('#image-form input[name=alt]').fill('QA alternate text');await page.locator('#asset-form input[name=tags]').fill('qa-both-save');
  await save('#asset-form');await close();ok(dialogs.length===0,'Saving tags also saves image choices; close has no discard prompt');
  let p=await current();ok(p.reviews.find(r=>r.kind==='image'&&r.item_id===aid).data.alt==='QA alternate text'&&p.reviews.find(r=>r.kind==='asset'&&r.item_id===aid).data.tags.includes('qa-both-save'),'Both forms persisted through one Save button');
  await open();const alt=page.locator('#image-form input[name=alt]'),before=await alt.inputValue();await alt.fill('temporary unsaved value');await alt.fill(before);await close();ok(dialogs.length===0,'Edit then revert does not warn');
  await open();await page.locator('#image-form input[name=alt]').fill('actually unsaved');await close();ok(dialogs.length===1,'Actual unsaved change still asks before discarding');
  await open();await page.locator('#image-form input[name=alt]').fill('QA saved image-side');await page.locator('#asset-form input[name=tags]').fill('qa-image-side-save');await save('#image-form');await close();ok(dialogs.length===1,'Image-side Save also saves shared tags without later warning');
  let failed=false;
  await page.route('**/api/reviews',async route=>{
    if(!failed&&route.request().postDataJSON()?.kind==='asset'){failed=true;await route.fulfill({status:500,contentType:'application/json',body:JSON.stringify({error:'QA simulated tag save failure'})});}
    else await route.continue();
  });
  await open();await page.locator('#image-form input[name=alt]').fill('QA saved before tag failure');await page.locator('#asset-form input[name=tags]').fill('qa-unsaved-tag');
  await page.locator('#image-form').getByRole('button',{name:'Save all image changes'}).click();
  await page.locator('#toast').filter({hasText:'QA simulated tag save failure'}).waitFor();
  await close();ok(dialogs.length===2,'Partial save failure leaves genuinely unsaved tags protected by warning');
  ok((await choice()).alt==='QA saved before tag failure','Successful image save is retained when tag save fails');
  await page.unroute('**/api/reviews');
  await open();await page.getByRole('button',{name:'Delete file…',exact:true}).click();
  ok(await page.locator('#delete-dialog').isVisible(),'Delete file has a separate review dialog');
  await page.locator('#delete-keeper').selectOption(keeper);
  ok(await page.locator('#delete-keeper-preview img').isVisible(),'Keeper appears alongside deletion candidate');
  await page.getByRole('button',{name:'Review deletion',exact:true}).click();
  await page.locator('#delete-confirm-form').waitFor({timeout:180000});
  ok(await page.getByRole('button',{name:'Delete this file from Dropbox',exact:true}).isDisabled(),'Native metadata review still requires exact confirmation');
  ok((await page.locator('.delete-facts').innerText()).includes(aid),'Live Dropbox stable file ID appears in confirmation');
  await page.locator('#delete-confirm').check();
  ok(await page.getByRole('button',{name:'Delete this file from Dropbox',exact:true}).isEnabled(),'Confirmation enables only the reviewed file action');
  await page.screenshot({path:out+'/deletion-review.png',fullPage:true});
  await page.getByRole('button',{name:'Close deletion review',exact:true}).click();
  ok(deleteRequests===0,'Preparing and cancelling deletion never calls the delete endpoint');
  for(const width of [1440,390,320]){
    await page.setViewportSize({width,height:1080});
    ok(await card().locator('.quick-actions button').evaluateAll(bs=>bs.every(b=>b.scrollWidth<=b.clientWidth)),'Card controls fit at '+width+'px');
    ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'No horizontal overflow at '+width+'px');
  }
  await page.screenshot({path:out+'/card-toggles-mobile.png',fullPage:true});
  ok(errors.length===0,'No browser errors');
  await fs.writeFile(out+'/browser-checks.json',JSON.stringify({status:'PASS',checks,errors,dialogs,deleteRequests},null,2));
  console.log(JSON.stringify({status:'PASS',checks:checks.length,deleteRequests,dialogs:dialogs.length}));
}finally{await browser.close();}
