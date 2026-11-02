// Run only in cua_repl with its documented browser/native handles.
// Update existing draft colour fields only. Never submit a listing.
import fs from 'node:fs/promises';

export function chairishColourWorkflow({tab, native, directory}) {
  const planPath = `${directory}/chairish-colour-plan.json`;
  const receiptPath = `${directory}/chairish-colour-receipts.json`;
  const intentPath = `${directory}/chairish-colour-intent.json`;
  const read = async p => JSON.parse(await fs.readFile(p, 'utf8'));
  const write = async (p, value) => {
    await fs.writeFile(p + '.tmp', JSON.stringify(value, null, 2) + '\n');
    await fs.rename(p + '.tmp', p);
  };
  const indexFor = (ax, predicate) => {
    const line = ax.split('\n').find(predicate);
    const value = Number(line?.trim().match(/^\d+/)?.[0]);
    if (!value) throw Error('Expected native control unavailable');
    return value;
  };
  const snapshot = () => tab.playwright.evaluate(() => {
    const get = id => document.getElementById(id)?.value;
    const pill = id => Array.from(document.getElementById(id)?.closest('.form-group')
      ?.querySelectorAll('.pill-container .pill-text') || []).map(x => x.innerText);
    return {
      sku:get('id_sku'), title:get('id_title'), description:get('id_description'), price:get('id_price'),
      fields:Array.from(document.querySelectorAll('input[id], textarea[id], select[id]'))
        .filter(e => e.type !== 'hidden' && !e.id.startsWith('id_pickup_') &&
          e.id !== 'id_primary_color_code' && !e.classList.contains('autocomplete-placeholder'))
        .map(e => ({id:e.id,value:e.value,checked:['checkbox','radio'].includes(e.type)?e.checked:null})),
      taxonomy:Object.fromEntries(['id_categories','id_styles','id_materials','id_brands',
        'id_artists','id_designers','id_styled_after','id_art_subjects','id_colors'].map(id=>[id,pill(id)])),
      photos:Array.from(document.querySelectorAll('img[id^="product-image-thumb-"]')).map(e=>({id:e.id,url:e.src})),
      colour:pill('id_primary_color_code'),
      state:document.body.innerText.match(/Listing is currently\s+(\w+)/)?.[1]?.toLowerCase(),
    };
  });
  const protectedData = ({colour,...rest}) => rest;
  const assertProtected = (before, after) => {
    if (JSON.stringify(protectedData(before)) !== JSON.stringify(protectedData(after))) {
      throw Error('Unrelated draft field changed; stop and reconcile');
    }
  };
  const validate = (r, s) => {
    if (s.sku !== r.sku || s.title.toLowerCase() !== r.title.toLowerCase() ||
        s.description !== r.description || s.price !== r.price ||
        s.photos.length !== r.photo_count || s.state !== 'draft') {
      throw Error('Draft identity/source mismatch: ' + r.sku);
    }
  };
  const open = async r => {
    if (await tab.url() !== r.url) await native.goto(r.url);
    await native.getAXState({emit:false});
    let s = await snapshot();
    if (!s.sku || !s.title || !s.photos.length) {
      await native.getAXState({emit:false,disableDiffing:true});
      s = await snapshot();
    }
    validate(r,s);
    return s;
  };
  async function record(r,before,after,changed) {
    assertProtected(before,after);
    if (after.colour.length !== 1 || after.colour[0] !== r.colour_label) {
      throw Error('Saved colour differs from plan');
    }
    const rows = await read(receiptPath).catch(()=>[]);
    const receipt = {sku:r.sku,id:r.native_id,url:r.url,at:new Date().toISOString(),
      source_colour:r.colour_source,colour:r.colour_label,changed,
      protected_fields_unchanged:true,status:'SAVED_REOPENED_DRAFT_ONLY',before,after};
    const previous = rows.findIndex(x=>x.sku===r.sku);
    if (previous>=0) rows[previous]=receipt; else rows.push(receipt);
    await write(receiptPath,rows);
    await write(intentPath,{sku:r.sku,phase:'VERIFIED',at:receipt.at});
    return {sku:r.sku,colour:r.colour_label,changed,verified:true};
  }
  async function next({pauseAfterSave=false}={}) {
    const plan=await read(planPath), receipts=await read(receiptPath).catch(()=>[]);
    const pending=await read(intentPath).catch(()=>null);
    if (pending && pending.phase!=='VERIFIED') throw Error('Reconcile current intent before another edit');
    const r=plan.records.find(x=>!receipts.some(y=>y.sku===x.sku));
    if (!r) return {complete:true,count:receipts.length};
    const before=await open(r);
    if (before.colour.length) {
      if (JSON.stringify(before.colour)!==JSON.stringify([r.colour_label])) throw Error('Existing colour conflict');
      return record(r,before,before,false);
    }
    await write(intentPath,{sku:r.sku,id:r.native_id,phase:'EDITING',before,at:new Date().toISOString()});
    let ax=await native.getAXState({emit:false,disableDiffing:true});
    await native.click(indexFor(ax,l=>l.includes('ID: id_primary_color_code')));
    await native.pressKey(null,'super+a');
    await native.typeText(null,r.query);
    await native.getAXState({emit:false});
    const option=tab.playwright.locator('.primary_color_code .menu-suggestion-list .menu-choice')
      .filter({has:tab.playwright.getByText(r.colour_label,{exact:true}),visible:true});
    await option.waitFor({state:'visible',timeoutMs:10000});
    if (await option.count()!==1) throw Error('Ambiguous colour choice');
    await option.locator('.checkbox-input').click();
    await native.getAXState({emit:false});
    const staged=await snapshot();
    assertProtected(before,staged);
    if (JSON.stringify(staged.colour)!==JSON.stringify([r.colour_label])) throw Error('Colour not selected');
    await write(intentPath,{sku:r.sku,id:r.native_id,phase:'SAVE_REQUESTED',before,at:new Date().toISOString()});
    ax=await native.getAXState({emit:false,disableDiffing:true});
    await tab.playwright.expectNavigation(
      () => tab.playwright.locator('button.btn-primary.btn-minor')
        .filter({hasText:/^Save$/,visible:true}).first().click(),
      {waitUntil:'domcontentloaded',timeoutMs:20000,url:r.url});
    await native.getAXState({emit:false});
    if (pauseAfterSave) return {sku:r.sku,phase:'SAVE_REQUESTED'};
    await native.reload();
    try {
      await tab.playwright.locator('.primary_color_code .pill-container .pill-text')
        .filter({hasText:new RegExp('^' + r.colour_label.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '$')})
        .waitFor({state:'visible',timeoutMs:10000});
    } catch (error) {
      // The first GET can race the draft save. Reopen once and reconcile
      // the immutable draft identity; never resend a write on uncertainty.
      if (!/selector deadline exceeded|locator\.waitFor\(visible\) timed out/i.test(String(error))) throw error;
      return reconcile();
    }
    const after=await open(r);
    return record(r,before,after,true);
  }
  async function reconcile() {
    const intent=await read(intentPath);
    const r=(await read(planPath)).records.find(x=>x.sku===intent.sku);
    if (!r || !intent.before) throw Error('No reconcilable record');
    if (await tab.url()===r.url) await native.reload();
    const after=await open(r);
    assertProtected(intent.before,after);
    if (JSON.stringify(after.colour)===JSON.stringify([r.colour_label])) return record(r,intent.before,after,true);
    if (after.colour.length===0) {
      await write(intentPath,{sku:r.sku,phase:'VERIFIED',at:new Date().toISOString(),note:'Save not retained; safe to retry this same native draft'});
      return {sku:r.sku,retained:false,retryAllowed:true};
    }
    throw Error('Saved colour conflicts with plan');
  }
  return {next,reconcile,snapshot};
}
