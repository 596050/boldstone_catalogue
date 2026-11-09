// Real-browser checks against a newly spawned, disposable, in-memory fake app.
// No existing server URL is accepted, and external network requests are blocked.
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';

let chromium;
try{({chromium}=await import(process.env.PLAYWRIGHT_MODULE||'playwright'));}
catch(error){throw new Error('Install Playwright or set PLAYWRIGHT_MODULE to its index.mjs before running browser-offline-smoke.mjs.',{cause:error});}
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
const output=process.env.REVIEW_BROWSER_OUTPUT||await fs.mkdtemp(path.join(os.tmpdir(),'boldstone-browser-checks-'));
await fs.mkdir(output,{recursive:true});
const python=process.env.REVIEW_BROWSER_PYTHON||path.join(root,'application/.venv/bin/python');
const child=spawn(python,[path.join(root,'catalogue-review/tests/isolated_jobs_server.py'),
  '--port','0','--cost-model','--gallery-layout','--component-controls','--browser-smoke'],{cwd:root,stdio:['ignore','pipe','pipe']});
let serverLog='',browser,page;
child.stderr.on('data',chunk=>{serverLog+=chunk;});
const checks=[],errors=[],blocked=[],apiFailures=[];
const report={status:'RUNNING',checks,errors,blocked_external_requests:blocked,api_failures:apiFailures,
  native:'in-memory fake only',live_dropbox_calls:0,output};
async function check(name,operation){await operation();checks.push(name);console.log('PASS '+name);}
try{
  const ready=await new Promise((resolve,reject)=>{
    let buffer='';const timer=setTimeout(()=>reject(new Error('The disposable browser fixture did not start.')),15000);
    child.once('error',error=>{clearTimeout(timer);reject(error);});
    child.once('exit',code=>{clearTimeout(timer);reject(new Error('The disposable fixture exited before readiness: '+code));});
    child.stdout.on('data',chunk=>{buffer+=chunk;for(const line of buffer.split('\n')){
      try{const record=JSON.parse(line);if(record.native==='in-memory fake only'&&record.url){clearTimeout(timer);resolve(record);return;}}catch{}
    }});
  });
  const base=new URL(ready.url).origin;
  assert.equal(new URL(base).hostname,'127.0.0.1');
  report.fixture_url=base;
  let executablePath=process.env.CHROME_PATH;
  const localChrome='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
  if(!executablePath)try{await fs.access(localChrome);executablePath=localChrome;}catch{}
  browser=await chromium.launch({headless:true,...(executablePath?{executablePath}:{})});
  const context=await browser.newContext({viewport:{width:1440,height:1080},acceptDownloads:true});
  await context.route('**/*',async route=>{
    const url=new URL(route.request().url());
    if(['http:','https:'].includes(url.protocol)&&url.origin!==base){blocked.push(url.origin);await route.abort();}
    else await route.continue();
  });
  page=await context.newPage();page.setDefaultTimeout(10000);
  page.on('pageerror',error=>errors.push(error.message));
  page.on('response',response=>{const url=new URL(response.url());if(url.pathname.startsWith('/api/')&&response.status()>=400)apiFailures.push({path:url.pathname,status:response.status()});});
  await page.goto(base+'/#L1',{waitUntil:'networkidle'});
  await check('gallery displays synthetic images and all fixture components',async()=>{
    await page.waitForFunction(()=>[...document.querySelectorAll('#image-grid img')].some(image=>image.complete&&image.naturalWidth>0));
    assert.equal(await page.locator('.product-link').count(),4);
    await page.screenshot({path:path.join(output,'review-desktop.png')});
  });
  await check('image and shared metadata save together and survive reload',async()=>{
    await page.locator('button[data-open-image="id:target"]').click();
    await page.locator('#image-form [name=alt]').fill('Offline browser QA image');
    await page.locator('#asset-form [name=tags]').fill('browser-smoke');
    await page.locator('#asset-form button[type=submit]').click();
    await page.locator('#asset-form .save-state').filter({hasText:'All image changes saved'}).waitFor();
    await page.getByRole('button',{name:'Close image',exact:true}).click();
    await page.reload({waitUntil:'networkidle'});
    await page.locator('button[data-open-image="id:target"]').click();
    assert.equal(await page.locator('#image-form [name=alt]').inputValue(),'Offline browser QA image');
    assert.equal(await page.locator('#asset-form [name=tags]').inputValue(),'browser-smoke');
    await page.getByRole('button',{name:'Close image',exact:true}).click();
  });
  await check('specification changes persist after a real browser reload',async()=>{
    await page.locator('[data-tab=specs]').click();
    const form=page.locator('form[data-field=Weight]');
    await form.locator('[name=decision]').selectOption('edit');
    await form.locator('[name=value]').fill('5 kg');
    await form.getByRole('button',{name:'Save item',exact:true}).click();
    await form.locator('.save-state').filter({hasText:'Saved locally'}).waitFor();
    await page.reload({waitUntil:'networkidle'});await page.locator('[data-tab=specs]').click();
    assert.equal(await page.locator('form[data-field=Weight] [name=value]').inputValue(),'5 kg');
  });
  await check('component cost preview and save use the entered amount',async()=>{
    await page.locator('[data-cost-product="L1"]').first().click();
    await page.locator('#cost-form [name=other_cost]').fill('8.25');
    await page.locator('[data-cost-preview]').click();
    await page.locator('#cost-result').filter({hasText:'£8.25'}).waitFor();
    await page.locator('#cost-form button[type=submit]').click();
    await page.locator('#toast').filter({hasText:'Costs and pricing saved'}).waitFor();
    await page.locator('[data-cost-close]').click();
  });
  await check('package quote saves and clears every unsaved-change marker',async()=>{
    await page.locator('[data-delivery-product="L1"]').first().click();
    for(const [name,value] of Object.entries({length_cm:45,width_cm:35,depth_cm:16,weight_kg:2,packaging_gbp:3.5}))
      await page.locator('#delivery-form [name='+name+']').fill(String(value));
    await page.locator('#delivery-result').filter({hasText:'£7.25'}).waitFor();
    await page.locator('#delivery-form button[type=submit]').click();
    await page.locator('#delivery-save-status').filter({hasText:'Package details saved'}).waitFor();
    await page.locator('[data-delivery-close]').click();
    assert.equal(await page.evaluate(()=>state.dirty.size),0);
  });
  await check('all specifications and component photo overview render',async()=>{
    await page.locator('#specifications-view').click();
    await page.locator('#specification-results .specification-family').waitFor();
    await page.locator('[data-component-overview="L1"]').first().click();
    await page.locator('#component-overview-content .overview-specs').waitFor();
    assert((await page.locator('#component-overview-content').innerText()).includes('5 kg'));
    await page.locator('#component-overview-close').click();
  });
  await check('export produces an accessible ZIP bundle',async()=>{
    await page.locator('#export-open').click();await page.locator('#export-run').click();
    const link=page.locator('#export-result a');await link.waitFor();
    const response=await page.request.get(base+await link.getAttribute('href'));
    assert.equal(response.status(),200);assert.equal((await response.body()).subarray(0,2).toString(),'PK');
    await page.getByRole('button',{name:'Close export',exact:true}).click();
  });
  await check('review pages fit desktop and narrow mobile viewports',async()=>{
    for(const width of [1440,390,320]){
      await page.setViewportSize({width,height:900});
      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Review overflow at '+width+'px');
    }
    await page.screenshot({path:path.join(output,'review-mobile.png')});
  });
  await check('standalone layout updates and exports the current rotated composition',async()=>{
    await page.goto(pathToFileURL(path.join(root,'Boldstone_Relief_Layout_Lab (1).html')).href);
    await page.locator('#axis').selectOption('column');
    await page.locator('#pw0').fill('200');await page.locator('#ph0').fill('500');
    await page.locator('[data-index="0"][data-field=rotate]').check();
    const pending=page.waitForEvent('download');await page.locator('#json').click();const download=await pending;
    const brief=JSON.parse(await fs.readFile(await download.path(),'utf8'));
    assert.equal(brief.arrangement,'column');assert.equal(brief.panels[0].rotation,90);
    assert.equal(brief.panels[0].width,500);assert.equal(brief.panels[0].height,200);
    await page.locator('#gap').fill('');assert(await page.locator('#json').isDisabled());
    await page.locator('#gap').fill('50');assert(await page.locator('#json').isEnabled());
    for(const width of [1440,390,320]){await page.setViewportSize({width,height:900});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Layout overflow at '+width+'px');}
    await page.screenshot({path:path.join(output,'layout-mobile.png')});
  });
  assert.deepEqual(errors,[]);assert.deepEqual(apiFailures,[]);assert.deepEqual(blocked,[]);
  report.status='PASS';console.log(JSON.stringify(report,null,2));
}catch(error){
  report.status='FAIL';report.error=error.stack||String(error);
  if(page)try{await page.screenshot({path:path.join(output,'failure.png')});}catch{}
  throw error;
}
finally{
  if(browser)await browser.close();
  if(child.exitCode===null&&child.signalCode===null){child.kill('SIGINT');await new Promise(resolve=>{child.once('exit',resolve);setTimeout(()=>{child.kill('SIGKILL');resolve();},5000).unref();});}
  await fs.writeFile(path.join(output,'browser-checks.json'),JSON.stringify(report,null,2));
  await fs.writeFile(path.join(output,'server.log'),serverLog);
}
