// Use a separate QA server seeded with the Acanthus review, never the live review DB.
import { chromium } from '/Users/tprice/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs';
import fs from 'node:fs/promises';
const base='http://127.0.0.1:8768';
const out='/Users/tprice/Library/Application Support/BoldstoneReview-QA-acanthus-20261025/qa';
await fs.mkdir(out,{recursive:true});
const browser=await chromium.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true});
const page=await browser.newPage({viewport:{width:1440,height:1080}}),checks=[],errors=[];
page.on('pageerror',e=>errors.push(e.message));
const ok=(value,name)=>{if(!value)throw Error(name);checks.push(name);};
const go=async hash=>{await page.goto(base+'/#'+hash,{waitUntil:'networkidle'});await page.locator('#image-categories').waitFor();};
try {
  await go('BSI-9B2B466B38BE');
  ok(await page.locator('.image-card').count()===1,'Reviewed and excluded Bronze candidates stay out of the Pale Blue sculpture view');
  await page.locator('#image-scope').selectOption('related');
  ok(await page.locator('.image-card.excluded').count()===6,'All six wrong-finish associations remain inspectable in Related candidates');
  await page.reload({waitUntil:'networkidle'});
  ok(await page.locator('#image-scope').inputValue()==='related','Association scope survives a shared-route reload');
  await page.locator('#image-scope').selectOption('sculpture');
  await page.getByRole('button',{name:'Types',exact:true}).click();
  ok(await page.locator('#asset-form input[value=product]').isVisible(),'Types button opens the multi-select category controls');
  const positioned=await page.locator('#asset-form').evaluate(el=>{const r=el.getBoundingClientRect(),p=el.closest('.detail-controls').getBoundingClientRect();return r.top>=p.top-2&&r.top<p.bottom;});
  ok(positioned,'Types button scrolls the category controls into view');
  await page.locator('#asset-form input[value=workshop]').check();
  await page.locator('#asset-form').getByRole('button',{name:'Save all image changes'}).click();
  await page.locator('#asset-form .save-state').filter({hasText:'All image changes saved'}).waitFor();
  await page.getByRole('button',{name:'Close image',exact:true}).click();
  await page.locator('[data-category=workshop]').click();
  ok(await page.locator('.image-card').count()===1,'New multi-select category is immediately filterable');
  await page.reload({waitUntil:'networkidle'});
  ok(await page.locator('#image-role').inputValue()==='workshop'&&await page.locator('.image-card').count()===1,'Saved type and category route survive reload');
  await go('BSI-A9FE7D79863A?type=in_situ');
  ok(await page.locator('.image-card').count()===2,'In situ route exposes both Bronze courtyard images');
  await page.locator('[data-category=group]').click();
  ok(await page.locator('.image-card').count()===2,'The same courtyard images are available under Group / series');
  await page.screenshot({path:out+'/categories-desktop.png',fullPage:true});
  await go('BSI-2CA935C1A57A?use=listing');
  ok(await page.locator('.image-card').count()===6,'Gold Leaf listing filter contains the six saved selections');
  ok(await page.locator('.image-card').first().getAttribute('data-asset')==='id:cnqzTNngPVsAAAAAAAygNA','Saved primary appears first instead of the historical catalogue primary');
  await page.locator('[data-category=in_situ]').click();
  ok(await page.locator('.image-card').count()===1,'Category and listing-purpose filters combine');
  ok(await page.locator('[data-category=in_situ] span').innerText()==='1','Category counts respect the active purpose filter');
  await go('BSI-C02D6DF365D3?type=group');
  ok(await page.locator('.image-card').count()===2,'Both approved Dropbox garden group references are attached to Flower');
  await go('BSI-A9FE7D79863A?use=listing');
  for(const width of [1440,1024,390,320]) {
    await page.setViewportSize({width,height:1080});
    const geometry=await page.locator('.image-card').evaluateAll(cards=>cards.map(c=>{const bounds=c.getBoundingClientRect(),buttons=[...c.querySelectorAll('.quick-actions button')];return {rows:new Set(buttons.map(b=>Math.round(b.getBoundingClientRect().top))).size,inside:buttons.every(b=>{const r=b.getBoundingClientRect();return r.left>=bounds.left&&r.right<=bounds.right&&b.scrollWidth<=b.clientWidth;}),buttons:buttons.length};}));
    ok(geometry.every(g=>g.buttons===6&&g.rows===(width<=380?3:2)&&g.inside),'All six buttons fit inside each card at '+width+'px');
    ok(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),'No horizontal page overflow at '+width+'px');
    if(width===390)await page.screenshot({path:out+'/cards-mobile.png',fullPage:true});
  }
  ok(!errors.length,'No browser JavaScript errors');
  await fs.writeFile(out+'/acanthus-browser-checks.json',JSON.stringify({status:'PASS',checks,errors},null,2));
  console.log(JSON.stringify({status:'PASS',checks:checks.length,details:checks}));
} finally {await browser.close();}
