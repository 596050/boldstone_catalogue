// Execute only in cua_repl against native eBay draft pages.
// Updates verified catalogue facts on existing drafts; never publishes.
import fs from 'node:fs/promises';

export function ebayDraftSpecifics({tab, plan, directory}) {
  const journalPath = `${directory}/ebay-sapr-specifics-receipts.json`;
  const intentPath = `${directory}/ebay-sapr-specifics-intent.json`;
  const normalise = value => value.trim().replace(/\s+/g, ' ');
  const write = async (path, data) => {
    await fs.writeFile(path + '.tmp', JSON.stringify(data, null, 2) + '\n');
    await fs.rename(path + '.tmp', path);
  };
  const readJson = async (path, fallback) => {
    try { return JSON.parse(await fs.readFile(path, 'utf8')); }
    catch (error) { if (error.code === 'ENOENT') return fallback; throw error; }
  };
  async function read() {
    await tab.playwright.getByRole('textbox', {name:'Custom label (SKU)', exact:true})
      .waitFor({state:'visible', timeoutMs:15000});
    let snapshot = await tab.playwright.domSnapshot();
    if (snapshot.includes('img "Loading"')) {
      await tab.playwright.getByRole('img', {name:'Loading', exact:true}).first()
        .waitFor({state:'hidden',timeoutMs:15000});
      snapshot = await tab.playwright.domSnapshot();
    }
    if (snapshot.includes('img "Loading"')) throw Error('Draft is still loading');
    if (!snapshot.includes('heading "Complete your listing"')) throw Error('Not a draft editor');
    const data = await tab.playwright.evaluate(() => ({
      fields: Object.fromEntries(Array.from(document.querySelectorAll('button[name^="attributes."]'))
        .map(e => [e.name.slice('attributes.'.length), e.innerText.trim()])),
      photos: Array.from(document.querySelectorAll('button[aria-label^="Edit or view photo"]'))
        .map(e => e.style.backgroundImage),
    }));
    for (const [key, label] of Object.entries({sku:'Custom label (SKU)', title:'Item title', price:'Item price', quantity:'Quantity'})) {
      data[key] = await tab.playwright.getByRole('textbox', {name:label,exact:true}).evaluate(e=>e.value);
    }
    data.description = normalise(await tab.playwright.frameLocator('#se-rte-frame__summary')
      .getByRole('textbox', {name:'Description',exact:true}).innerText());
    const start = snapshot.indexOf('heading "Delivery details"');
    const end = snapshot.indexOf('heading "Item disclosures"');
    if (start < 0 || end < start || !data.photos.length || data.photos.some(x=>!x))
      throw Error('Protected draft evidence incomplete');
    data.delivery = normalise(snapshot.slice(start,end).replace(/ \[active\]/g,''));
    data.url = await tab.url();
    return data;
  }
  function validate(record, data) {
    const params = new URL(data.url).searchParams;
    const nativeId = params.get('draftId') || params.get('draft_id');
    if (data.sku!==record.sku || data.title!==record.title || Number(data.price)!==Number(record.price) ||
        nativeId!==record.native_id) throw Error('Native identity mismatch '+record.sku);
    if ((data.description.match(/designer Sally Price/g)||[]).length!==1)
      throw Error('Existing description disclosure mismatch '+record.sku);
  }
  function preserved(before, after, fields) {
    for (const key of ['sku','title','price','quantity','description','photos','delivery'])
      if (JSON.stringify(key==='delivery' ? before[key].replace('heading "Domestic shipping"','heading "Domestic postage"') : before[key])!==
          JSON.stringify(key==='delivery' ? after[key].replace('heading "Domestic shipping"','heading "Domestic postage"') : after[key]))
        throw Error('Protected '+key+' changed');
    const untouched = data => Object.fromEntries(Object.entries(data.fields).filter(([key])=>!(key in fields)));
    if (JSON.stringify(untouched(before))!==JSON.stringify(untouched(after))) throw Error('Other item specifics changed');
  }
  async function setField(field,value) {
    // The native attribute name and exact current value are checked before edits.
    const control = tab.playwright.locator(`button[name="attributes.${field}"]`);
    await control.press('Enter');
    await tab.playwright.getByRole('textbox',{name:'Search or enter your own. Search results appear below',exact:true}).fill(value);
    const snapshot = await tab.playwright.domSnapshot();
    if (field==='Artist') {
      if (!snapshot.includes(`menuitemcheckbox "${value}"`)) throw Error('Artist custom option missing');
      await tab.playwright.getByRole('menuitemcheckbox',{name:value,exact:true}).click();
    } else if(snapshot.includes(`button "Add custom value ${value}"`)) {
      await tab.playwright.getByRole('button',{name:`Add custom value ${value}`,exact:true}).click();
    } else if(snapshot.includes(`menuitemradio "${value}"`)) {
      await tab.playwright.getByRole('menuitemradio',{name:value,exact:true}).click();
    } else throw Error('Exact dimension option missing '+field);
    if(await control.getAttribute('aria-expanded')==='true') await control.press('Escape');
    if(normalise(await control.innerText())!==value) throw Error('Field input mismatch '+field);
  }
  async function finish(record, before, changes, journal) {
    const after = await read(); validate(record,after); preserved(before,after,record.fields);
    for(const [key,value] of Object.entries(record.fields))
      if(after.fields[key]!==value) throw Error('Saved field mismatch '+record.sku+' '+key);
    const receipt={sku:record.sku,native_id:record.native_id,url:record.url,fields:record.fields,
      changed_fields:changes,at:new Date().toISOString(),status:'DRAFT_SAVED_AND_REOPENED',before,after};
    const index=journal.findIndex(r=>r.sku===record.sku);
    if(index<0)journal.push(receipt);else journal[index]=receipt;
    await write(journalPath,journal);
    await write(intentPath,{sku:record.sku,status:'VERIFIED',at:receipt.at});
    return receipt;
  }
  async function run(limit=4) {
    const journal=await readJson(journalPath,[]),started=Date.now(),results=[];
    const pending=await readJson(intentPath,null);
    if(pending && pending.status!=='VERIFIED') throw Error('Unreconciled intent '+pending.sku+'; use reconcile');
    for(const record of plan) {
      if(journal.some(r=>r.sku===record.sku))continue;
      if(await tab.url()!==record.url)await tab.goto(record.url);
      const before=await read();validate(record,before);
      const changes=Object.entries(record.fields).filter(([field,value])=>before.fields[field]!==value);
      if(changes.some(([field])=>before.fields[field]))throw Error('Existing nonempty fact needs review '+record.sku);
      await write(intentPath,{sku:record.sku,status:'PREPARED',record,before,changes,at:new Date().toISOString()});
      for(const [field,value] of changes)await setField(field,value);
      const staged=await read();validate(record,staged);preserved(before,staged,record.fields);
      for(const [field,value]of Object.entries(record.fields))if(staged.fields[field]!==value)throw Error('Staged mismatch');
      if(changes.length) {
        await write(intentPath,{sku:record.sku,status:'SAVE_REQUESTED',record,before,changes,at:new Date().toISOString()});
        await tab.playwright.expectNavigation(()=>tab.playwright.getByRole('button',{name:'Save for later',exact:true}).press('Enter'),
          {url:'https://www.ebay.co.uk/sh/lst/drafts',timeoutMs:20000,waitUntil:'domcontentloaded'});
        if(!((await tab.playwright.domSnapshot()).includes('link "sapr_2972 View profile"')))throw Error('Account mismatch on draft list');
        await tab.goto(record.url);
      }
      const receipt=await finish(record,before,changes,journal);
      results.push({sku:record.sku,changed:receipt.changed_fields.length});
      if(results.length>=limit || Date.now()-started>40000)break;
    }
    return {verified:journal.length,total:plan.length,processed:results};
  }
  async function reconcile() {
    const pending=await readJson(intentPath,null);
    if(!pending || pending.status==='VERIFIED')return {pending:false};
    if(pending.status!=='SAVE_REQUESTED')throw Error('Unsaved draft state: inspect current editor before continuing');
    await tab.goto(pending.record.url);
    const journal=await readJson(journalPath,[]);
    const receipt=await finish(pending.record,pending.before,pending.changes,journal);
    return {verified:journal.length,sku:receipt.sku,reconciled:true};
  }
  return {run,reconcile,read};
}
