// All review writes are made against a separate QA database on port 8768.
import { chromium } from '/Users/tprice/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs';
import fs from 'node:fs/promises';
const base='http://127.0.0.1:8768',pid='BSI-C02D6DF365D3';
const out='/Users/tprice/Library/Application Support/BoldstoneReview-QA-family-coverage-20261025/qa';
await fs.mkdir(out,{recursive:true});
const browser=await chromium.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true});
const page=await browser.newPage({viewport:{width:1440,height:1080}}),checks=[],errors=[];let nativeCalls=0;
page.on('pageerror',e=>errors.push(e.message));page.on('dialog',async d=>{errors.push('Unexpected dialog: '+d.message());await d.dismiss();});
await page.route('**/api/deletions/**',async route=>{nativeCalls++;await route.abort();});
const ok=(v,label)=>{if(!v)throw Error(label);checks.push(label);};
const data=async()=>await (await page.request.get(base+'/api/coverage')).json();
const family=()=>page.locator('.family-heading[data-family="Acanthus"]');
async function waitCoverage(n){await page.waitForFunction(([id,n])=>state.boot.coverage.products[id].in_situ.count===n,[pid,n]);}
try{
  await page.goto(base+'/#'+pid);await page.locator('#image-scope-summary').waitFor();
  const initial=(await data()).products[pid];
  ok(await page.locator('.family-heading').count()===58,'Selector groups all 58 catalogue families');
  ok(await page.locator('#image-grid .image-card').count()===4,'Flower default scope contains its four assigned Dropbox images');
  const summary=await page.locator('#image-scope-summary').innerText();
  ok(summary.includes('8 retained associations')&&summary.includes('4 in This sculpture')&&summary.includes('4 related candidates (Squarespace)'),'Eight-versus-four count is explained with the correct source');
  ok((await page.locator('#product-coverage').innerText()).includes('3/2 in situ'),'Individual checklist uses three distinct assigned in-situ images');
  await page.locator('[data-image-scope="related"]').click();
  ok(await page.locator('#image-grid .image-card').count()===4,'Related-candidate shortcut opens the four other images');
  ok((await page.locator('#image-grid .source-pill').allTextContents()).every(s=>s==='Squarespace'),'Related images are labelled Squarespace');
  await page.locator('[data-image-scope="all"]').click();
  ok(await page.locator('#image-grid .image-card').count()===8,'Show-all shortcut displays all retained images');
  await family().click();await page.locator('.family-table').first().waitFor();
  ok(await page.locator('h1').innerText()==='Acanthus','Family heading opens a family overview');
  ok((await page.locator('.family-stats').innerText()).includes('10\nIndividual options'),'Family overview reports all ten Acanthus options');
  ok(await page.locator('.family-table').nth(1).locator('tbody tr').count()===4,'White checklist groups by four existing component identities');
  ok((await page.locator('.family-table').nth(1).innerText()).includes('title omits “White”'),'Existing White folder is a title issue, not a missing component');
  await page.screenshot({path:out+'/acanthus-family-desktop.png',fullPage:true});
  await page.reload();await page.locator('.family-table').first().waitFor();
  ok(await page.locator('h1').innerText()==='Acanthus','Family deep link survives reload');
  await page.locator('#search').fill('Flower');
  ok(await page.locator('.family-heading').count()===1&&await page.locator('.product-link').count()===1,'Searching preserves the matching family heading');
  await page.locator('#search').fill('');
  await page.locator('.family-table').first().getByRole('link',{name:'Acanthus Flower',exact:true}).click();
  await page.locator('#product-coverage').waitFor();
  await page.getByRole('link',{name:'Review in-situ images →',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('#image-role')?.value==='in_situ'&&document.querySelectorAll('#image-grid .image-card').length===3);
  ok(await page.locator('#image-grid .image-card').count()===3,'Checklist action filters the three in-situ images for that sculpture');

  // Excluding two assigned images updates product, family and selector coverage.
  for(const id of initial.in_situ.image_ids.slice(0,2)){
    await page.locator(`[data-quick="exclude"][data-id="${id}"]`).click();
    await page.waitForFunction(()=>!document.querySelector('[data-quick][disabled]'));
  }
  await waitCoverage(1);
  ok((await page.locator('#product-coverage').innerText()).includes('1/2 in situ · need 1'),'Product checklist refreshes after exclusions');
  ok((await page.locator(`.product-link[data-product="${pid}"]`).innerText()).includes('1/2 in situ'),'Sidebar status refreshes after exclusions');
  await family().click();await page.locator('.family-table').first().waitFor();
  const row=page.locator('.family-table').first().locator('tbody tr').filter({has:page.getByRole('link',{name:'Acanthus Flower',exact:true})});
  ok((await row.innerText()).includes('need 1'),'Family table reflects the same updated gap');
  await row.getByRole('link',{name:'Acanthus Flower',exact:true}).click();

  // Multi-tag edits change the coverage source, then title edits resolve only naming.
  const remaining=initial.in_situ.image_ids[2];
  await page.locator(`[data-image-types="${remaining}"]`).click();
  await page.locator('#asset-form input[name=image_type][value=in_situ]').uncheck();
  await page.locator('#asset-form').getByRole('button',{name:'Save all image changes',exact:true}).click();
  await page.locator('#asset-form .save-state').filter({hasText:'All image changes saved'}).waitFor();
  await page.getByRole('button',{name:'Close image',exact:true}).click();await waitCoverage(0);
  ok((await page.locator('#product-coverage').innerText()).includes('0/2 in situ · need 2'),'Changing image tags updates the in-situ shortfall');
  await page.locator('[data-tab=listing]').click();
  const form=page.locator('[data-field="Name"]');
  await form.locator('select[name=decision]').selectOption('edit');
  await form.locator('textarea[name=value]').fill('Acanthus Flower — White');
  await form.getByRole('button',{name:'Save item',exact:true}).click();
  await page.waitForFunction(id=>state.boot.coverage.products[id].white_evidence==='named_white',pid);
  ok((await page.locator('#product-coverage').innerText()).includes('Plain White entry present'),'Saved White title resolves the naming indicator');
  await family().click();await page.locator('.family-table').first().waitFor();
  const whiteRow=page.locator('.family-table').nth(1).locator('tbody tr').filter({has:page.getByRole('link',{name:'Acanthus Flower — White',exact:true})});
  ok((await whiteRow.innerText()).includes('Plain White entry present'),'Family White checklist reflects the saved title');
  for(const width of [1440,390,320]){
    await page.setViewportSize({width,height:1080});
    ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Family overview fits '+width+'px viewport');
    if(width===390)await page.screenshot({path:out+'/family-mobile.png',fullPage:true});
  }
  await page.locator('#library-view').click();await page.locator('#image-grid').waitFor();
  ok((await page.locator('h1').innerText()).includes('Every image'),'Image library remains accessible from family overview');
  ok(errors.length===0,'No browser errors or unintended discard dialogs');
  ok(nativeCalls===0,'Family and coverage workflows call no native deletion endpoints');
  await fs.writeFile(out+'/browser-checks.json',JSON.stringify({status:'PASS',checks,errors,native_calls:nativeCalls,scope:'QA database only'},null,2));
  console.log(JSON.stringify({status:'PASS',checks:checks.length,native_calls:nativeCalls}));
}finally{await browser.close();}
