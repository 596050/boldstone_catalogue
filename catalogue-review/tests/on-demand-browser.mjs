// Opt-in read-only smoke test of the running app and its Dropbox connection.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
if(process.env.REVIEW_LIVE_READ!=='1')throw Error('Set REVIEW_LIVE_READ=1 for live read-only checks.');
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE||'playwright');
const base=process.env.REVIEW_TEST_URL||'http://127.0.0.1:8767';
const browser=await chromium.launch({headless:true,...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{})});
const page=await browser.newPage({viewport:{width:1440,height:1080}});
page.setDefaultTimeout(60000);
const errors=[],writes=[],images=[];
page.on('pageerror',e=>errors.push(e.message));
page.on('request',r=>{if(r.method()!=='GET')writes.push(new URL(r.url()).pathname);});
page.on('response',r=>{if(new URL(r.url()).pathname==='/api/image')images.push({url:r.url(),status:r.status(),cache:r.headers()['cache-control']});});
try{
  const before=await(await page.request.get(base+'/api/bootstrap')).json();
  const product=before.products.find(p=>p.name==='Acanthus Flower White')||before.products.find(p=>p.family==='Acanthus');
  assert(product,'Acanthus component must be available');
  await page.goto(base+'/#'+product.id,{waitUntil:'domcontentloaded'});
  await page.locator('#image-grid .image-card').first().waitFor();
  await page.waitForFunction(()=>Array.from(document.querySelectorAll('#image-grid .image-card img')).some(img=>img.complete&&img.naturalWidth>0));
  await page.locator('#image-grid .image-card .image-stage').first().click();
  await page.locator('#image-dialog[open]').waitFor();
  await page.waitForFunction(()=>{const img=document.querySelector('.detail-photo-view img');return img?.complete&&img.naturalWidth>0;});
  const detail=await page.locator('.detail-photo-view img').evaluate(img=>({width:img.naturalWidth,height:img.naturalHeight,src:img.getAttribute('src'),fallback:img.dataset.thumbnailFallback||false}));
  assert(!detail.fallback,'First original should load without a thumbnail fallback');
  assert(!detail.src.includes('size=thumb'));
  assert(images.some(r=>!r.url.includes('size=thumb')&&r.status===200&&r.cache==='private, no-store'));
  assert(images.some(r=>r.url.includes('size=thumb')&&r.status===200));
  await page.locator('#image-dialog .close').click();
  const after=await(await page.request.get(base+'/api/bootstrap')).json();
  assert.equal(after.saved_decisions,before.saved_decisions);
  assert.deepEqual(errors,[]);
  assert(!writes.some(p=>p==='/api/reviews'||p.startsWith('/api/deletions')||p==='/api/image-components'));
  const result={status:'PASS',product:product.name,detail,thumbnailResponses:images.filter(r=>r.url.includes('size=thumb')&&r.status===200).length,pageErrors:errors,reviewWrites:0,dropboxMutations:0};
  if(process.env.REVIEW_TEST_OUTPUT)await fs.writeFile(process.env.REVIEW_TEST_OUTPUT,JSON.stringify(result,null,2));
  console.log(JSON.stringify(result,null,2));
}finally{await browser.close();}
