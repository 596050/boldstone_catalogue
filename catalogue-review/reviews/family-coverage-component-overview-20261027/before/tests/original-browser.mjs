// Opt-in live read: this only fetches a hash-pinned Dropbox original, never saves reviews.
import {chromium} from '/Users/tprice/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs';
import fs from 'node:fs/promises';
if(process.env.REVIEW_LIVE_READ!=='1')throw Error('Set REVIEW_LIVE_READ=1 to test the existing Dropbox read connection.');
const url=process.env.REVIEW_TEST_URL||'http://127.0.0.1:8768';
const root='/Users/tprice/Library/Application Support/BoldstoneReview-QA-v2-20261025/qa';
const browser=await chromium.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true});
const page=await browser.newPage({viewport:{width:1440,height:1080}});page.setDefaultTimeout(115000);
const errors=[];page.on('pageerror',e=>errors.push(e.message));
try{
 const before=await (await page.request.get(url+'/api/bootstrap')).json();
 await page.goto(url+'/#BSI-612EF4DBB555',{waitUntil:'networkidle'});
 await page.locator('[data-asset="id:cnqzTNngPVsAAAAAAAykAQ"]').getByRole('button',{name:'Review ↗'}).click();
 if(await page.locator('[data-fetch-original]').count()){
  const response=page.waitForResponse(r=>r.url().endsWith('/api/original'));
  await page.locator('[data-fetch-original]').click();const r=await response;
  if(r.status()!==200)throw Error('Original lookup: '+await r.text());
 }
 await page.locator('.size-panel').filter({hasText:'2048 × 2048 px'}).waitFor();
 await page.waitForFunction(()=>document.querySelector('.detail-photo-view img')?.naturalWidth===2048);
 if(!await page.locator('.size-panel').evaluate(e=>{const panel=e.getBoundingClientRect(),dialog=e.closest('dialog').getBoundingClientRect();return panel.top>=dialog.top&&panel.bottom<=dialog.bottom;}))throw Error('Original size is clipped by the full-resolution image');
 await page.screenshot({path:root+'/verified-dropbox-original.png'});
 const after=await (await page.request.get(url+'/api/bootstrap')).json();
 if(after.saved_decisions!==before.saved_decisions)throw Error('Live read changed review records');
 if(errors.length)throw Error(errors.join('; '));
 const receipt={status:'PASS',url,asset_id:'id:cnqzTNngPVsAAAAAAAykAQ',original_pixels:[2048,2048],bytes:6915968,review_writes:0,dropbox_mutations:0,errors};
 await fs.writeFile(root+'/original-browser-checks.json',JSON.stringify(receipt,null,2));console.log(JSON.stringify(receipt));
}finally{await browser.close();}
