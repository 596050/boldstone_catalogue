import fs from 'node:fs/promises';

// Runs only inside the approved CUA runtime. All remote operations are visible UI actions.
export function saatchiAlternativeWorkflow({tab, directory}) {
  const read = async name => JSON.parse(await fs.readFile(`${directory}/${name}`, 'utf8'));
  const write = async (name, value) => {
    const path = `${directory}/${name}`;
    await fs.writeFile(path + '.tmp', JSON.stringify(value, null, 2) + '\n');
    await fs.rename(path + '.tmp', path);
  };
  async function capture() {
    const intent = await read('current-alternative-creation-intent.json');
    const url = await tab.url();
    const id = url?.match(/\/studio\/art\/(\d+)\/overview/)?.[1];
    if (!id) throw Error('Save not confirmed; preserve form and reconcile before retrying');
    await tab.playwright.getByText(intent.title, {exact: true}).first()
      .waitFor({state: 'attached', timeoutMs: 10000});
    const snapshot = await tab.playwright.domSnapshot();
    if (!snapshot.includes(intent.title) || !snapshot.includes('Draft')) {
      throw Error('Saved title and draft state do not match creation intent');
    }
    const rows = await read('primary-draft-receipts.json');
    const selections = await read('listing-alternative-selection.json');
    const item = selections.find(x => x.sku === intent.sku);
    if (!item) throw Error('Unknown selected photo');
    const existing = rows.find(x => x.sku === item.sku || x.artwork_id === id);
    if (existing && (existing.sku !== item.sku || existing.artwork_id !== id)) {
      throw Error('Conflicting native SKU/artwork binding');
    }
    if (!existing) rows.push({sku: item.sku, catalogue_id: item.catalogue_id,
      title: item.title, artwork_id: id, url, primary_photo_id: item.photo.photo_id,
      primary_sha256: item.sha256, status: 'DRAFT_PRIMARY_ONLY_NOT_PUBLISHED',
      saved_utc: new Date().toISOString()});
    Object.assign(item, {status: 'DRAFT_PRIMARY_ONLY_NOT_PUBLISHED', artwork_id: id, native_url: url});
    await write('primary-draft-receipts.json', rows);
    await write('listing-alternative-selection.json', selections);
    await write('current-alternative-creation-intent.json', {...intent, phase: 'SAVED', artwork_id: id, url});
    await fs.writeFile(`${directory}/alternative-readback-${item.sku}.txt`, snapshot);
    return {sku: item.sku, artwork_id: id, status: item.status};
  }
  async function next() {
    const selections = await read('listing-alternative-selection.json');
    const rows = await read('primary-draft-receipts.json');
    const item = selections.find(x => !rows.some(r => r.sku === x.sku) && !x.artwork_id);
    if (!item) return {complete: true};
    const intent = await read('current-alternative-creation-intent.json').catch(() => null);
    if (intent && intent.phase !== 'SAVED') {
      throw Error('Unresolved save intent: reconcile ' + intent.sku + ' before another upload');
    }
    await tab.playwright.getByRole('link', {name: 'Artwork Uploader', exact: true}).click();
    await tab.playwright.domSnapshot();
    await tab.playwright.getByRole('textbox', {name: 'Enter title', exact: true}).fill(item.title);
    await tab.playwright.getByRole('button', {name: 'Next', exact: true}).first().click();
    await tab.playwright.domSnapshot();
    await tab.playwright.getByRole('button', {name: 'ADD PRIMARY IMAGE', exact: true}).click();
    await tab.playwright.domSnapshot();
    const chooserPromise = tab.playwright.waitForEvent('filechooser', {timeoutMs: 10000});
    await tab.playwright.locator('[data-type="browse-text"]').click();
    const chooser = await chooserPromise;
    await chooser.setFiles([item.path]);
    const dimensions = new RegExp(item.dimensions[0] + '\\s*[x×]\\s*' + item.dimensions[1]);
    try {
      await tab.playwright.getByText(dimensions).waitFor({state: 'attached', timeoutMs: 15000});
    } catch (error) {
      await tab.playwright.domSnapshot();
      // Some image uploads finish just after the locator deadline. Observe again;
      // never repeat the upload or a save to recover from a wait timeout.
      await tab.playwright.getByText(dimensions).waitFor({state: 'attached', timeoutMs: 10000});
    }
    await tab.playwright.domSnapshot();
    return finishCurrent();
  }
  async function finishCurrent() {
    const selections = await read('listing-alternative-selection.json');
    const title = await tab.playwright.getByRole('textbox', {name: 'Enter title', exact: true})
      .evaluate(element => element.value);
    const item = selections.find(x => x.title === title && !x.artwork_id);
    if (!item) throw Error('Current title is not an unsaved selected alternative');
    const snapshot = await tab.playwright.domSnapshot();
    if (!snapshot.includes(item.path.split('/').pop()) ||
        !snapshot.includes(`${item.dimensions[0]} x ${item.dimensions[1]} px`)) {
      throw Error('Current upload filename or dimensions do not match');
    }
    await tab.playwright.getByRole('dialog').getByRole('button', {name: 'Submit', exact: true}).click();
    await tab.playwright.domSnapshot();
    await tab.playwright.getByRole('button', {name: 'Next', exact: true}).last().click();
    await tab.playwright.domSnapshot();
    await write('current-alternative-creation-intent.json', {at: new Date().toISOString(),
      sku: item.sku, title: item.title, photo_id: item.photo.photo_id,
      sha256: item.sha256, phase: 'SAVE_REQUESTED'});
    await tab.playwright.expectNavigation(
      () => tab.playwright.getByRole('button', {name: 'SAVE & EXIT', exact: true}).click(),
      {waitUntil: 'domcontentloaded', timeoutMs: 20000});
    // Saving sometimes outlasts the browser's short locator deadline. Observe
    // the completion condition only; never send another save to recover.
    for (let attempt = 0; attempt < 4; attempt++) {
      if (/\/studio\/art\/\d+\/overview/.test(await tab.url())) return capture();
      try {
        await tab.playwright.getByRole('button', {name: 'Publish', exact: true})
          .waitFor({state: 'attached', timeoutMs: 10000});
      } catch (error) {
        const dialog = await tab.getJsDialog();
        if (dialog) return {sku: item.sku, status: 'SAVE_DIALOG_REQUIRES_INSPECTION'};
      }
    }
    if (/\/studio\/art\/\d+\/overview/.test(await tab.url())) return capture();
    return {sku: item.sku, status: 'SAVE_UNCONFIRMED_DO_NOT_RESUBMIT'};
  }
  return {next, capture, finishCurrent};
}
