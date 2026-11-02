// Import only inside cua_repl. Every remote read/write uses its documented UI API.
import fs from 'node:fs/promises';

export function wescoverDescriptionUpdates({tab, root}) {
  const directory = `${root}/catalogue-copy-disclosures`;
  const intentPath = `${directory}/wescover-copy-intent.json`;
  const receiptsPath = `${directory}/wescover-copy-receipts.json`;
  const descriptionName = 'Materials, function, size, style and the story behind this piece— this helps with SEO!';
  const read = async p => JSON.parse(await fs.readFile(p, 'utf8'));
  const write = async (p, data) => {
    await fs.writeFile(p + '.tmp', JSON.stringify(data, null, 2) + '\n');
    await fs.rename(p + '.tmp', p);
  };
  const otherFields = () => tab.playwright.evaluate(() => ({
    fields: Array.from(document.querySelectorAll('input,textarea,select'))
      .filter(e => e.name && e.name !== 'description' && e.type !== 'hidden' &&
        e.getBoundingClientRect().width > 0 && !/^[0-9a-f]{8}-/.test(e.name))
      .map(e => ({name:e.name, type:e.type, value:e.value,
        ...(e.type === 'checkbox' || e.type === 'radio' ? {checked:e.checked} : {})})),
    images: Array.from(document.querySelectorAll('img')).map(e => e.src)
      .filter(src => src.includes('wescover-imported/')),
  }));
  async function open(binding) {
    const target = new URL(binding.url);
    if (target.searchParams.get('item') === 'new' || target.searchParams.get('product') === 'new') {
      throw Error('Resolve the existing native edit link before changing this product: ' + binding.sku);
    }
    if (await tab.url() !== binding.url) await tab.goto(binding.url);
    await tab.playwright.getByRole('textbox',{name:'e.g. AE-TG-LT-W7-BL',exact:true})
      .waitFor({state:'visible',timeoutMs:12000});
    await tab.playwright.locator('input[name="sku"][value="'+binding.sku+'"]')
      .waitFor({state:'visible',timeoutMs:12000});
    await tab.playwright.domSnapshot();
    const sku = await tab.playwright.getByRole('textbox',{name:'e.g. AE-TG-LT-W7-BL',exact:true}).evaluate(e=>e.value);
    if (sku !== binding.sku) throw Error('Wrong native product: ' + binding.sku);
  }
  function updatedText(before, record) {
    let text = before;
    for (const label of ['Custom design','Companion pieces']) {
      const line = record.description_text.split('\n').find(l=>l.startsWith(label+':'));
      if (!line) continue;
      const regex = new RegExp('^'+label+':[^\\n]*','m');
      text = regex.test(text) ? text.replace(regex, line) : text.trimEnd()+'\n\n'+line;
    }
    if (record.surface_effect) {
      const line = record.description_text.split('\n').find(l=>l.startsWith('Surface effect:'));
      if (!line?.includes('will differ from the photographs')) throw Error('Missing source variation');
      if (!/^Surface effect:[^\n]*/m.test(text)) throw Error('Missing existing effect statement: '+record.sku);
      text = text.replace(/^Surface effect:[^\n]*/m, line);
    }
    if (!text.includes('designer Sally Price')) throw Error('Missing customisation');
    return text;
  }
  async function run(maxCount=6) {
    const records = (await read(`${root}/current-prepared-catalogue.json`)).records;
    const originalBindings = await read(`${root}/wescover-current/enrichment-receipts.json`);
    const resolvedBindings = await read(`${root}/wescover-current/verified-edit-bindings.json`)
      .catch(error => { if (error.code === 'ENOENT') return []; throw error; });
    const bindings = originalBindings.map(binding => {
      const resolved = resolvedBindings.find(row => row.sku === binding.sku);
      if (resolved && resolved.title !== binding.title) throw Error('Resolved title mismatch: ' + binding.sku);
      return resolved ? {...binding, url: resolved.url} : binding;
    });
    const receipts = await read(receiptsPath).catch(()=>[]);
    const pending = await read(intentPath).catch(()=>null);
    if (pending && !receipts.some(r=>r.sku===pending.sku)) {
      await open(pending);
      const current = await tab.playwright.getByRole('textbox',{name:descriptionName,exact:true}).evaluate(e=>e.value);
      if (current !== pending.after) throw Error('Reconcile interrupted Wescover description: '+pending.sku);
      if (pending.other && JSON.stringify(await otherFields()) !== JSON.stringify(pending.other)) throw Error('Other fields changed');
      receipts.push({...pending, status:'SAVED_REOPENED_PENDING_GLOBAL_SUBMIT',at:new Date().toISOString()});
      await write(receiptsPath,receipts);
    }
    const completed=[]; const started=Date.now();
    for (const binding of bindings) {
      if (receipts.some(r=>r.sku===binding.sku)) continue;
      const record=records.find(r=>r.sku===binding.sku); if(!record)throw Error('Missing catalogue SKU');
      await open(binding);
      const before=await tab.playwright.getByRole('textbox',{name:descriptionName,exact:true}).evaluate(e=>e.value);
      const after=updatedText(before,record), other=await otherFields();
      const intent={sku:binding.sku,url:binding.url,before,after,other,phase:'PREPARED',at:new Date().toISOString()};
      await write(intentPath,intent);
      if(before!==after){
        const editor = tab.playwright.getByRole('textbox',{name:descriptionName,exact:true});
        await editor.fill(after);
        await editor.press('Tab');
        if (await editor.evaluate(e=>e.value) !== after) throw Error('Description input did not retain the change');
        await write(intentPath,{...intent,phase:'SAVE_REQUESTED'});
        await tab.playwright.getByRole('button',{name:'Save',exact:true}).click();
        await tab.playwright.getByRole('button',{name:'Submit',exact:true}).waitFor({state:'visible',timeoutMs:15000});
        await tab.playwright.domSnapshot();
        await open(binding);
      }
      const saved=await tab.playwright.getByRole('textbox',{name:descriptionName,exact:true}).evaluate(e=>e.value);
      if(saved!==after || JSON.stringify(await otherFields())!==JSON.stringify(other)) throw Error('Saved description/other-field mismatch: '+binding.sku);
      receipts.push({...intent,phase:'VERIFIED',status:'SAVED_REOPENED_PENDING_GLOBAL_SUBMIT',at:new Date().toISOString()});
      await write(receiptsPath,receipts); completed.push(binding.sku);
      if(completed.length>=maxCount || Date.now()-started>40000)break;
    }
    return {saved_this_batch:completed,total_saved:receipts.length,total:bindings.length};
  }
  return {run};
}
