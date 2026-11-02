// Native UI only. Updates existing drafts; never presses Submit.
import fs from 'node:fs/promises';

export function chairishFulfilmentWorkflow({tab, native, snapshot, directory}) {
  const planPath = `${directory}/chairish-fulfilment-plan.json`;
  const receiptPath = `${directory}/chairish-fulfilment-receipts.json`;
  const intentPath = `${directory}/chairish-fulfilment-intent.json`;
  const read = async p => JSON.parse(await fs.readFile(p, 'utf8'));
  const write = async (p, data) => {
    await fs.writeFile(p + '.tmp', JSON.stringify(data, null, 2) + '\n');
    await fs.rename(p + '.tmp', p);
  };
  const value = (s, id) => s.fields.find(f => f.id === id)?.value;
  const protectedData = s => ({...s, description: undefined,
    fields: s.fields.filter(f => !['id_description', 'id_period_made', 'id_lead_time'].includes(f.id))});
  const check = (before, after) => {
    if (JSON.stringify(protectedData(before)) !== JSON.stringify(protectedData(after))) {
      throw Error('Unrelated Chairish field changed; reconcile before continuing');
    }
  };
  const identity = (r, s) => {
    if (s.sku !== r.sku || s.title.toLowerCase() !== r.title.toLowerCase() ||
        s.price !== r.price || s.photos.length !== r.photo_count || s.state !== 'draft' ||
        ![r.before_description, r.description].includes(s.description)) {
      throw Error('Draft identity/source mismatch: ' + r.sku);
    }
    if (!['', 'NOT_MADE'].includes(value(s, 'id_period_made')) ||
        !['', 'W2'].includes(value(s, 'id_lead_time'))) {
      throw Error('Existing production field conflicts with source: ' + r.sku);
    }
  };
  const open = async r => {
    if (await tab.url() !== r.url) await native.goto(r.url);
    await native.getAXState({emit: false});
    const s = await snapshot();
    identity(r, s);
    return s;
  };
  const matches = (r, s) => s.description === r.description &&
    value(s, 'id_period_made') === 'NOT_MADE' && value(s, 'id_lead_time') === 'W2';
  async function record(r, before, after) {
    check(before, after);
    if (!matches(r, after)) throw Error('Saved fulfilment differs from source');
    const receipts = await read(receiptPath).catch(() => []);
    const receipt = {catalogue_id:r.catalogue_id, sku:r.sku, id:r.native_id, url:r.url,
      at:new Date().toISOString(), source_availability:r.availability,
      source_lead_time:r.source_lead_time, status:'SAVED_REOPENED_DRAFT_ONLY',
      protected_fields_unchanged:true, before, after};
    const i = receipts.findIndex(x => x.sku === r.sku);
    if (i < 0) receipts.push(receipt); else receipts[i] = receipt;
    await write(receiptPath, receipts);
    await write(intentPath, {sku:r.sku, phase:'VERIFIED', at:receipt.at});
    return {sku:r.sku, period:'Made to order', lead_time:'14 days', verified:true};
  }
  async function save(r) {
    await tab.playwright.expectNavigation(() => tab.playwright.locator('button.btn-primary.btn-minor')
      .filter({hasText:/^Save$/, visible:true}).first().click(),
      {waitUntil:'domcontentloaded', timeoutMs:20000, url:r.url});
    await native.getAXState({emit:false});
  }
  async function next() {
    const plan = await read(planPath);
    const receipts = await read(receiptPath).catch(() => []);
    const pending = await read(intentPath).catch(() => null);
    if (pending && pending.phase !== 'VERIFIED') throw Error('Reconcile pending draft first');
    const r = plan.records.find(x => !receipts.some(y => y.sku === x.sku));
    if (!r) return {complete:true,count:receipts.length};
    const before = await open(r);
    if (matches(r,before)) return record(r,before,before);
    await write(intentPath,{sku:r.sku,phase:'EDITING',before,at:new Date().toISOString()});
    if (value(before,'id_period_made') !== 'NOT_MADE') {
      await tab.playwright.getByLabel('Period Made',{exact:true}).selectOption('NOT_MADE');
      await native.getAXState({emit:false});
    }
    // The lead-time control is exposed after the first save of this period.
    if (!await tab.playwright.getByLabel('Lead Time / Time to Ship',{exact:true}).isVisible()) {
      await write(intentPath,{sku:r.sku,phase:'PERIOD_SAVE_REQUESTED',before,at:new Date().toISOString()});
      await save(r);
    }
    await tab.playwright.getByLabel('Lead Time / Time to Ship',{exact:true}).selectOption('W2');
    const ax = await native.getAXState({emit:false,disableDiffing:true});
    const descriptionLine = ax.split('\n').find(x => x.includes('ID: id_description'));
    const descriptionIndex = Number(descriptionLine?.trim().match(/^\d+/)?.[0]);
    if (!descriptionIndex) throw Error('Native description control unavailable');
    await native.click(descriptionIndex);
    await native.pressKey(null,'super+a');
    // Chairish's editor model requires native input followed by blur.
    await native.typeText(null,r.description);
    await native.pressKey(null,'Tab');
    await native.getAXState({emit:false});
    const staged = await snapshot();
    check(before,staged);
    if (!matches(r,staged)) throw Error('Production settings not selected');
    await write(intentPath,{sku:r.sku,phase:'SAVE_REQUESTED',before,at:new Date().toISOString()});
    await save(r);
    await native.reload();
    const after = await open(r);
    if (!matches(r,after)) return reconcile();
    return record(r,before,after);
  }
  async function reconcile() {
    const intent = await read(intentPath);
    const r = (await read(planPath)).records.find(x => x.sku === intent.sku);
    if (!r || !intent.before) throw Error('No reconcilable draft');
    if (await tab.url() === r.url) await native.reload();
    const after = await open(r);
    check(intent.before,after);
    if (matches(r,after)) return record(r,intent.before,after);
    // Both writes are idempotent updates to this same known native draft.
    await write(intentPath,{sku:r.sku,phase:'VERIFIED',at:new Date().toISOString(),
      note:'Verified partial draft state; same draft may continue',original_before:intent.before});
    return {sku:r.sku,partial:true,retryAllowed:true};
  }
  return {next,reconcile};
}
