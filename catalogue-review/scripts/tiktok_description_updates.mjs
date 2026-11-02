import fs from 'node:fs/promises';
import path from 'node:path';

const custom = 'All designs can be customised. Completely new commissions can also be created in collaboration with designer Sally Price.';
const variation = 'Each piece is handmade. The surface-effect pattern will vary and will differ from the photographs.';
const norm = value => String(value).replace(/\s+/g, ' ').trim();

// UI-only continuation. The caller supplies the existing browser and product
// list tab; there are no page requests, hidden state reads or guessed edit URLs.
export function tiktokDescriptionWorkflow({browser, listTab, directory, catalogue, manifest}) {
  const receiptPath = path.join(directory, 'tiktok-copy-receipts.json');
  const records = new Map(catalogue.records.map(record => [record.catalogue_id, record]));
  const read = async file => JSON.parse(await fs.readFile(file, 'utf8'));
  const write = async (file, value) => {
    await fs.writeFile(file + '.tmp', JSON.stringify(value, null, 2) + '\n');
    await fs.rename(file + '.tmp', file);
  };
  async function saveReceipt(receipt) {
    const rows = await read(receiptPath);
    const index = rows.findIndex(row => row.product_id === receipt.product_id);
    if (index < 0) rows.push(receipt); else rows[index] = {...rows[index], ...receipt};
    if (new Set(rows.map(row => row.product_id)).size !== rows.length) throw Error('Duplicate TikTok product ID');
    await write(receiptPath, rows);
  }
  async function protection(tab) {
    return {
      inputs: await tab.playwright.locator('input:not([type="file"])').evaluateAll(elements => elements.filter(element => element.value !== '' || element.checked).map(element => ({
        id: element.id, type: element.type, value: element.value, checked: element.checked,
      }))),
      photos: await tab.playwright.locator('[id^="main_image_item_"]').evaluateAll(elements => elements.map(element => ({
        id: element.id,
        images: Array.from(element.querySelectorAll('img')).map(image => {
          const source = image.getAttribute('src') || '';
          // CDN query signatures and edge hostnames are not photo identity.
          return source.replace(/^https?:\/\/[^/]+/, '').split('?')[0];
        }).filter(source => source && !source.includes('image-upload-placeholder-')),
      })).filter(item => item.images.length)),
    };
  }
  function intended(before, record) {
    let result = before.trim();
    if (!/gypsum-based material/i.test(result)) result += '\n\nMaterial: Made from a gypsum-based material.';
    if (record.surface_effect && !/surface effect[^\n]*applied/i.test(result)) result += '\n\nSurface effect: A decorative surface effect is applied to create the finish shown.';
    if (record.surface_effect && !result.includes(variation)) result += '\n\n' + variation;
    if (!result.includes(custom)) result += '\n\n' + custom;
    const companion = record.description_text.split('\n').find(line => line.startsWith('Companion pieces:'));
    if (companion && !result.includes(companion)) result += '\n\n' + companion;
    return result;
  }
  async function inspect(tab, expectedSku) {
    const editor = tab.playwright.locator('div.ProseMirror[contenteditable]');
    try {
      await editor.waitFor({state: 'visible', timeoutMs: 20000});
    } catch (error) {
      // Hydration can replace the editor after it first becomes visible.
      // Recover only the read; no save action is repeated here.
      await tab.playwright.domSnapshot();
      if (!await editor.isVisible()) throw error;
    }
    const before = await protection(tab);
    if (!before.inputs.some(input => input.id.startsWith('skus') && input.value === expectedSku)) {
      throw Error('TikTok editor SKU mismatch: ' + expectedSku);
    }
    const description = await editor.innerText();
    if (!description.trim()) throw Error('Blank TikTok description: ' + expectedSku);
    return {editor, before, description};
  }
  async function update(entry) {
    const existing = (await read(receiptPath)).find(row => row.product_id === entry.product_id);
    if (existing) return {sku: entry.sku, status: existing.status, skipped: true};
    const intentPath = path.join(directory, 'tiktok-description-intent-' + entry.product_id + '.json');
    const oldIntent = await read(intentPath).catch(error => {
      if (error.code === 'ENOENT') return null;
      throw error;
    });
    if (oldIntent) throw Error('Reconcile interrupted TikTok edit before continuing: ' + entry.product_id + ' / ' + oldIntent.phase);
    const record = records.get(entry.catalogue_id);
    if (!record || record.sku !== entry.sku) throw Error('Catalogue identity mismatch: ' + entry.sku);
    const allTab = listTab.playwright.getByRole('tab', {name: 'All', exact: true});
    if (await allTab.getAttribute('aria-selected') !== 'true') await allTab.click();
    const search = listTab.playwright.getByRole('textbox', {name: 'Product name, ID or SKU', exact: true});
    await search.fill(entry.product_id);
    await search.press('Enter');
    const row = listTab.playwright.getByRole('row').filter({hasText: 'ID:' + entry.product_id});
    await row.or(listTab.playwright.getByText('No matching results', {exact:true})).waitFor({state:'visible',timeoutMs:15000});
    if (!await row.isVisible()) {
      // TikTok excludes draft-only records from its All tab. Use the native
      // Draft search and the same exact ID/SKU; never create a replacement.
      await listTab.playwright.getByRole('tab', {name:'Draft',exact:true}).click();
      await search.fill(entry.product_id);
      await search.press('Enter');
      await row.waitFor({state:'visible',timeoutMs:15000});
    }
    const rowText = await row.innerText();
    if (!rowText.includes('Seller SKU: ' + entry.sku)) throw Error('TikTok list SKU mismatch: ' + entry.sku);
    const state = ['Live', 'Deactivated', 'Draft', 'Rejected'].find(value => new RegExp('\\n' + value + '\\n').test(rowText));
    if (!state) throw Error('Unresolved TikTok publication state: ' + rowText);
    const priorTabs = new Set((await browser.tabs.list()).map(tab => tab.id));
    // The filtered table changes its layout after hydration. Read its fresh
    // native row before clicking the first Action button (the observed pencil).
    const ax = await listTab.getAXState({disableDiffing:true,emit:false});
    const marker = 'Seller SKU: ' + entry.sku;
    const markerAt = ax.indexOf(marker);
    const action = markerAt >= 0 ? ax.slice(markerAt).match(/\n\s+(\d+) button(?:\n|\r)/) : null;
    if (!action) throw Error('Native TikTok row edit control was not found');
    // Focus the identified row's edit control and activate it from the
    // keyboard; this avoids a moving table's mouse hit target.
    await row.getByRole('button').first().press('Enter');
    await listTab.getAXState({emit:false});
    const opened = (await browser.tabs.list()).filter(tab => !priorTabs.has(tab.id) &&
      (tab.url?.includes('/product/edit/' + entry.product_id) || tab.url?.includes('/product/edit-draft/' + entry.product_id)));
    if (opened.length !== 1) throw Error('Could not identify the exact TikTok editor tab: ' + entry.sku);
    const tab = await browser.tabs.get(opened[0].id);
    const journalPath = path.join(directory, 'tiktok-description-intent-' + entry.product_id + '.json');
    try {
      const {editor, before, description} = await inspect(tab, entry.sku);
      const expected = intended(description, record);
      const base = {at: new Date().toISOString(), sku: entry.sku, catalogue_id: entry.catalogue_id,
        product_id: entry.product_id, edit_url: opened[0].url, stateBefore: state,
        before: description, after: expected, protectionBefore: before,
        customisation: true, variation: !!record.surface_effect,
        companion: record.description_text.includes('Companion pieces:')};
      if (norm(description) === norm(expected)) {
        await saveReceipt({...base, status: 'ALREADY_PRESENT_REOPENED', protectedInputsUnchanged: true});
        await tab.close();
        return {sku: entry.sku, status: 'ALREADY_PRESENT_REOPENED'};
      }
      const snapshot = await tab.playwright.domSnapshot();
      if (snapshot.includes('current listing information is from the draft you saved before') && state === 'Live') {
        throw Error('Live record has an existing separate draft; preserve it for reconciliation: ' + entry.sku);
      }
      if (await editor.getAttribute('contenteditable') !== 'true') throw Error('Description is read-only: ' + entry.sku);
      await write(journalPath, {...base, phase: 'READY_TO_EDIT'});
      await editor.fill(expected);
      await tab.playwright.getByRole('heading', {name: 'Product details', exact: true}).click();
      if (norm(await editor.innerText()) !== norm(expected)) throw Error('TikTok did not retain entered copy');
      if (JSON.stringify(await protection(tab)) !== JSON.stringify(before)) throw Error('A protected TikTok field changed before save');
      const mode = state === 'Live' ? 'Update' : 'Save as draft';
      await write(journalPath, {...base, phase: 'SUBMITTING_ONCE', mode});
      await tab.playwright.getByRole('button', {name: mode, exact: true}).click();
      if (state === 'Live') {
        const suggestion = tab.playwright.getByRole('dialog', {name:/issues may need optimisation/});
        await tab.playwright.getByText('Product submitted',{exact:true}).or(suggestion).waitFor({state:'visible',timeoutMs:20000});
        if (await suggestion.isVisible()) {
          const recommendation = await suggestion.innerText();
          if (!recommendation.includes('Number of images') || !recommendation.includes('Upload at least 5 product images')) {
            throw Error('A new TikTok recommendation needs inspection: '+recommendation);
          }
          // Optional photo-count recommendation only. Preserve approved photos.
          await suggestion.getByRole('button',{name:'Submit',exact:true}).click();
        }
        await tab.playwright.getByText('Product submitted', {exact: true}).waitFor({state: 'visible', timeoutMs: 20000});
        const outcome = await tab.playwright.domSnapshot();
        if (!outcome.includes('Changes were submitted for review')) throw Error('Unexpected TikTok update result');
        await saveReceipt({...base, status: 'SUBMITTED_FOR_REVIEW', protectedInputsUnchanged: true,
          outcome: 'Changes submitted for review; existing live information preserved until approval.'});
      } else {
        if (state !== 'Draft') await tab.playwright.getByText(/current listing information is from the draft you saved before/).waitFor({state:'visible',timeoutMs:20000});
        else await tab.playwright.getByRole('button',{name:'Save as draft',exact:true}).waitFor({state:'visible',timeoutMs:20000});
        await tab.reload();
        const saved = await inspect(tab, entry.sku);
        if (norm(saved.description) !== norm(expected)) throw Error('TikTok saved draft copy mismatch');
        if (JSON.stringify(saved.before) !== JSON.stringify(before)) throw Error('TikTok saved draft protected field mismatch');
        await saveReceipt({...base, verified_at:new Date().toISOString(), status:'DRAFT_SAVED_REOPENED',
          description:saved.description,protectedInputsUnchanged:true,publication:'NOT_ACTIVATED'});
      }
      await write(journalPath, {...base, phase:'RECEIPT_SAVED', mode});
      await tab.close();
      return {sku:entry.sku,status:state==='Live'?'SUBMITTED_FOR_REVIEW':'DRAFT_SAVED_REOPENED'};
    } catch (error) {
      await tab.markHandoff();
      throw error;
    }
  }
  async function next(count=3) {
    const done = new Set((await read(receiptPath)).map(row=>row.product_id));
    const results=[];
    for (const entry of manifest.records.filter(row=>!done.has(row.product_id)).slice(0,count)) results.push(await update(entry));
    return results;
  }
  async function verifyPending(count=3) {
    const pending=(await read(receiptPath)).filter(row=>row.status==='SUBMITTED_FOR_REVIEW').slice(0,count);
    const results=[];
    if (!pending.length) return results;
    await browser.nameSession('🗿 Catalogue descriptions');
    const tab=await browser.tabs.new();
    for (const row of pending) {
      try {
        await tab.goto(row.edit_url);
        const saved=await inspect(tab,row.sku);
        if(norm(saved.description)!==norm(row.after)) {
          results.push({sku:row.sku,status:'PUBLIC_REVIEW_PENDING'});
        } else {
          if(JSON.stringify(saved.before)!==JSON.stringify(row.protectionBefore))throw Error('TikTok live protected field mismatch: '+row.sku);
          const snapshot=await tab.playwright.domSnapshot();
          if(!snapshot.includes('Live" [level=1]'))throw Error('TikTok live state not confirmed: '+row.sku);
          await saveReceipt({...row,verified_at:new Date().toISOString(),status:'SAVED_REOPENED_LIVE',description:saved.description,protectedInputsUnchanged:true});
          results.push({sku:row.sku,status:'SAVED_REOPENED_LIVE'});
        }
      } catch(error) {await tab.markHandoff();throw error;}
    }
    await tab.close();
    return results;
  }
  return {next,update,verifyPending};
}
