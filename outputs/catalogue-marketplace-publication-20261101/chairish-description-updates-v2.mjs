// Import only inside cua_repl. Remote reads and writes use the documented UI API.
// Updates descriptions on bound existing drafts; never creates or submits listings.
import fs from 'node:fs/promises';

export function chairishDescriptionUpdates({tab, root}) {
  const directory = `${root}/catalogue-copy-disclosures`;
  const intentPath = `${directory}/chairish-copy-intent.json`;
  const receiptsPath = `${directory}/chairish-copy-receipts.json`;
  const read = async p => JSON.parse(await fs.readFile(p, 'utf8'));
  const write = async (p, data) => {
    await fs.writeFile(p + '.tmp', JSON.stringify(data, null, 2) + '\n');
    await fs.rename(p + '.tmp', p);
  };
  const snapshot = () => tab.playwright.evaluate(() => ({
    sku: document.querySelector('#id_sku')?.value,
    description: document.querySelector('#id_description')?.value,
    state: document.body.innerText.match(/Listing is currently\s+(\w+)/)?.[1],
    other: {
      fields: Array.from(document.querySelectorAll('input[id],textarea[id],select[id]'))
        .filter(e => e.id !== 'id_description' && e.type !== 'hidden' &&
          e.getBoundingClientRect().width > 0)
        .map(e => ({id:e.id,type:e.type,value:e.value,
          ...(e.type === 'checkbox' || e.type === 'radio' ? {checked:e.checked} : {})})),
      pills: Array.from(document.querySelectorAll('.pill-container .pill-text')).map(e=>e.innerText),
      photos: Array.from(document.querySelectorAll('img[id^="product-image-thumb-"]'))
        .map(e=>({id:e.id,url:e.src})),
    },
  }));
  async function open(binding, record, reload=false) {
    if (await tab.url() !== binding.url) await tab.goto(binding.url);
    else if (reload) await tab.reload();
    await tab.playwright.locator('#id_description').waitFor({state:'visible',timeoutMs:12000});
    const pattern = new RegExp('^'+record.title.slice(0,32).replace(/[.*+?^${}()|[\]\\]/g,'\\$&'),'i');
    await tab.playwright.getByText(pattern).filter({visible:true}).first()
      .waitFor({state:'visible',timeoutMs:12000});
    await tab.playwright.domSnapshot();
    const data=await snapshot();
    if(data.sku!==binding.sku || data.state!=='DRAFT') throw Error('Wrong product or state: '+binding.sku);
    return data;
  }
  async function run(maxCount=6) {
    const records=(await read(`${root}/chairish-current/prepared-native-drafts.json`)).records;
    const bindings=await read(`${root}/chairish-current/draft-receipts.json`);
    const receipts=await read(receiptsPath).catch(()=>[]);
    const pending=await read(intentPath).catch(()=>null);
    if(pending && !receipts.some(r=>r.sku===pending.sku)) {
      const record=records.find(r=>r.sku===pending.sku);
      const current=await open(pending,record,true);
      if(![pending.before,pending.after].includes(current.description) || JSON.stringify(current.other)!==JSON.stringify(pending.other))
        throw Error('Reconcile interrupted Chairish description: '+pending.sku);
      if(current.description===pending.after) {
        receipts.push({...pending,status:'SAVED_REOPENED_DRAFT',at:new Date().toISOString()});
        await write(receiptsPath,receipts);
      } else {
        await write(intentPath,{...pending,phase:'RECONCILED_UNCHANGED_SAFE_TO_EDIT',at:new Date().toISOString()});
      }
    }
    const completed=[],started=Date.now();
    for(const binding of bindings) {
      if(receipts.some(r=>r.sku===binding.sku))continue;
      const record=records.find(r=>r.sku===binding.sku);
      if(!record || String(record.native_id)!==String(binding.id))throw Error('Missing native binding');
      const before=await open(binding,record);
      const prior=await read(`${root}/chairish-current/readback-${binding.sku}.json`);
      if(before.description!==prior.description && before.description!==record.description)
        throw Error('Native description changed since prior readback: '+binding.sku);
      if(!record.description.includes('designer Sally Price'))throw Error('Missing source customisation');
      const intent={sku:binding.sku,id:binding.id,url:binding.url,before:before.description,
        after:record.description,other:before.other,phase:'PREPARED',at:new Date().toISOString()};
      await write(intentPath,intent);
      if(before.description!==record.description) {
        // Chairish can show a Playwright-filled value without retaining it in
        // its save model. Native typing plus blur is the verified input path.
        const ax=await tab.getAXState({emit:false,disableDiffing:true});
        const line=ax.split('\n').find(l=>l.includes('ID: id_description,'));
        const index=Number(line?.trim().match(/^(\d+)/)?.[1]);
        if(!index)throw Error('Description editor unavailable');
        await tab.click(index);
        await tab.pressKey(null,'super+a');
        await tab.typeText(null,record.description);
        await tab.pressKey(null,'Tab');
        await tab.getAXState({emit:false});
        await write(intentPath,{...intent,phase:'SAVE_REQUESTED'});
        await tab.playwright.getByRole('button',{name:'Save',exact:true}).first().click();
        await tab.playwright.getByText(/Your changes have been saved/).waitFor({state:'visible',timeoutMs:15000});
        await tab.playwright.domSnapshot();
        if(!await tab.playwright.getByRole('button',{name:'Save',exact:true}).first().isEnabled())
          throw Error('Save still pending; preserve current form');
      }
      const saved=await open(binding,record,true);
      if(saved.description!==record.description || JSON.stringify(saved.other)!==JSON.stringify(before.other))
        throw Error('Saved description or other fields differ: '+binding.sku);
      receipts.push({...intent,phase:'VERIFIED',status:'SAVED_REOPENED_DRAFT',at:new Date().toISOString()});
      await write(receiptsPath,receipts); completed.push(binding.sku);
      if(completed.length>=maxCount || Date.now()-started>40000)break;
    }
    return {saved_this_batch:completed,total_saved:receipts.length,total:bindings.length};
  }
  return {run};
}
