// Load only inside cua_repl. All website interactions use its documented APIs.
// This workflow saves drafts only; it never clicks Submit or accepts terms.
import fs from 'node:fs/promises';

export function chairishWorkflow({tab, native, directory}) {
  const receiptsPath = `${directory}/draft-receipts.json`;
  const intentPath = `${directory}/creation-intent.json`;
  const read = async path => JSON.parse(await fs.readFile(path, 'utf8'));
  const write = async (path, value) => {
    await fs.writeFile(`${path}.tmp`, JSON.stringify(value, null, 2) + '\n');
    await fs.rename(`${path}.tmp`, path);
  };
  const records = async () => (await read(`${directory}/prepared-native-drafts.json`)).records;
  const visible = async locator => {
    try {
      await locator.waitFor({state: 'visible', timeoutMs: 10000});
    } catch (error) {
      await native.getAXState({emit: false});
      if (!await locator.isVisible()) throw error;
    }
  };
  const indexFor = (ax, predicate) => {
    const line = ax.split('\n').find(predicate);
    const index = Number(line?.trim().match(/^(\d+)/)?.[1]);
    if (!index) throw Error('Expected native control missing');
    return index;
  };

  async function capture(sku) {
    const url = `https://www.chairish.com/product/list?order_by=&query=${encodeURIComponent(sku)}&state=DRA`;
    if (await tab.url() !== url) await tab.goto(url);
    const row = tab.playwright.getByRole('row').filter({hasText: `SKU: ${sku}`});
    await visible(row);
    if (await row.count() !== 1) throw Error(`Ambiguous native SKU: ${sku}`);
    const href = await row.getByRole('link', {name: 'Edit', exact: true}).getAttribute('href');
    const id = href?.match(/^\/product\/(\d+)\/update$/)?.[1];
    if (!id) throw Error('No observed edit link');
    const rows = await read(receiptsPath);
    if (rows.some(r => (r.sku === sku && r.id !== id) || (r.id === id && r.sku !== sku))) {
      throw Error('Conflicting native binding');
    }
    let receipt = rows.find(r => r.sku === sku);
    if (!receipt) {
      receipt = {sku, id, url: 'https://www.chairish.com' + href, state: 'CREATED_PENDING_READBACK'};
      rows.push(receipt);
    }
    const intent = await read(intentPath).catch(() => null);
    if (intent?.sku === sku && intent.expected_primary_dom_id) {
      receipt.expected_primary_dom_id = intent.expected_primary_dom_id;
    }
    await write(receiptsPath, rows);
    if (intent?.sku === sku) await write(intentPath, {...intent, native_id: id, phase: 'BOUND_TO_NATIVE_ID'});
    return receipt;
  }

  async function verify(sku) {
    const rows = await read(receiptsPath);
    const receipt = rows.find(r => r.sku === sku);
    const record = (await records()).find(r => r.sku === sku);
    if (!receipt || !record) throw Error('Missing source or native binding');
    if (await tab.url() !== receipt.url) await tab.goto(receipt.url);
    await visible(tab.playwright.getByRole('textbox', {name: 'Category', exact: true}));
    // The empty form appears before Chairish hydrates the saved product. Its
    // title banner is populated from that product, unlike the static fields.
    // The banner truncates long names with a literal ellipsis. Full title and
    // SKU equality are checked below after this loading signal.
    const titlePattern = new RegExp('^' + record.title.slice(0, 32).replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'i');
    try {
      await tab.playwright.getByText(titlePattern).filter({visible: true}).first()
        .waitFor({state: 'visible', timeoutMs: 10000});
    } catch {
      // Some browser waits time out even when their diagnostic says visible.
      // Re-observe; the exact saved-field comparisons below remain mandatory.
      await native.getAXState({emit: false});
    }
    await native.getAXState({emit: false});
    const data = await tab.playwright.evaluate(() => ({
      title: document.querySelector('#id_title')?.value,
      description: document.querySelector('#id_description')?.value,
      sku: document.querySelector('#id_sku')?.value,
      price: document.querySelector('#id_price')?.value,
      photos: Array.from(document.querySelectorAll('img[id^="product-image-thumb-"]')).map(e => ({
        id: e.id, url: e.src, loaded: e.complete && e.naturalWidth > 0,
      })),
      state: document.body.innerText.match(/Listing is currently\s+(\w+)/)?.[1],
    }));
    const fields = {};
    for (const name of ['Category', 'Styles', 'Materials', 'Dominant Color']) {
      fields[name] = await tab.playwright.getByRole('textbox', {name, exact: true}).evaluate(e =>
        Array.from(e.closest('.form-group').querySelectorAll('.pill-container .pill-text')).map(x => x.innerText));
    }
    const expectedPrimary = receipt.expected_primary_dom_id || receipt.verified_primary_image_dom_id;
    if (data.sku !== sku || data.description !== record.description ||
        data.title.toLowerCase() !== record.title.toLowerCase() ||
        data.price !== record.draft_price_usd || data.photos.length !== record.photos.length ||
        fields.Category[0] !== 'Fine Art > Sculpture' ||
        !fields.Materials.includes('Sculpture Materials > Plaster') ||
        (expectedPrimary && data.photos[0]?.id !== expectedPrimary)) {
      await write(`${directory}/mismatch-${sku}.json`, {at: new Date().toISOString(), ...data, fields});
      throw Error(`Saved-field mismatch: ${sku}`);
    }
    const previewReady = data.photos.every(p => p.loaded);
    Object.assign(receipt, {
      state: previewReady ? `CORE_FIELDS_AND_${data.photos.length}_PHOTOS_SAVED_RELOAD_VERIFIED_REQUIRED_FIELDS_PENDING` : 'SAVED_PENDING_PREVIEW_READBACK',
      catalogue_selected_photo_count: (record.catalogue_selected_photos || record.photos).length,
      below_minimum_photo_ids: (record.selected_photos_below_native_minimum || []).map(p => p.id),
      over_limit_photo_ids: (record.additional_selected_photos_over_platform_limit || []).map(p => p.id),
      needs_second_photo: record.photos.length < 2,
      primary_reference_requires_review: !!record.primary_photo_requires_review,
    });
    if (expectedPrimary) receipt.verified_primary_image_dom_id = expectedPrimary;
    await write(`${directory}/readback-${sku}.json`, {
      at: new Date().toISOString(), ...data, selected_fields: fields,
      native_id: receipt.id, preview_ready: previewReady,
      catalogue_selected_photo_count: receipt.catalogue_selected_photo_count,
      below_minimum_photo_ids: receipt.below_minimum_photo_ids,
      over_limit_photo_ids: receipt.over_limit_photo_ids,
      required_before_publication: record.required_before_publication,
    });
    await write(receiptsPath, rows);
    return {sku, id: receipt.id, photos: data.photos.length, verified: previewReady,
            primaryVerified: !!expectedPrimary, title: data.title};
  }

  async function taxonomy() {
    for (const [name, id, query, label] of [
      ['Category', 'id_categories', 'Sculpture', 'Fine Art > Sculpture'],
      ['Materials', 'id_materials', 'Plaster', 'Sculpture Materials > Plaster'],
    ]) {
      const selected = () => tab.playwright.getByRole('textbox', {name, exact: true}).evaluate(e =>
        Array.from(e.closest('.form-group').querySelectorAll('.pill-container .pill-text')).map(x => x.innerText));
      if ((await selected()).includes(label)) continue;
      let ax = await native.getAXState({emit: false, disableDiffing: true});
      await native.click(indexFor(ax, l => l.includes(`ID: ${id}`)));
      await native.pressKey(null, 'super+a');
      await native.typeText(null, query);
      // Re-observe the native dropdown: browser visibility waits have timed out
      // while the option was visibly available. Selected-pill readback below
      // remains the authority for whether this actually chose the category.
      await tab.playwright.locator('.menu-suggestion-list').getByText(label, {exact: true}).first()
        .waitFor({state: 'attached', timeoutMs: 10000});
      ax = await native.getAXState({emit: false, disableDiffing: true});
      await native.click(indexFor(ax, l => l.trim().endsWith(`text ${label}`)));
      await native.getAXState({emit: false});
      if (!(await selected()).includes(label)) throw Error(`Taxonomy not selected: ${label}`);
    }
  }

  async function next({referencePrimaryDraftSku = null} = {}) {
    const rows = await read(receiptsPath);
    const oldIntent = await read(intentPath).catch(() => null);
    if (oldIntent && !rows.some(r => r.sku === oldIntent.sku)) {
      throw Error(`Reconcile interrupted creation before starting another: ${oldIntent.sku}`);
    }
    const record = (await records()).find(r =>
      (!referencePrimaryDraftSku || r.sku === referencePrimaryDraftSku) &&
      (!r.primary_photo_requires_review || r.sku === referencePrimaryDraftSku) && !rows.some(x => x.sku === r.sku));
    if (!record) return {noMoreEligibleRecords: true};
    const manifest = await read(`${directory}/photos/${record.sku}/manifest.json`);
    if (manifest.status === 'INCOMPLETE_DO_NOT_UPLOAD' || manifest.photo_errors?.length ||
        manifest.photos.length !== record.photos.length || !manifest.photos.length ||
        (manifest.primary_photo_requires_review && record.sku !== referencePrimaryDraftSku)) {
      throw Error(`Unresolved image preparation: ${record.sku}`);
    }
    let intent = {sku: record.sku, at: new Date().toISOString(), phase: 'CREATING_DRAFT', expected_photos: record.photos.length,
      primary_reference_requires_review: !!record.primary_photo_requires_review};
    await write(intentPath, intent);
    await tab.goto('https://www.chairish.com/product/create');
    let ax = await native.getAXState({emit: false, disableDiffing: true});
    for (const [id, value] of [['id_title', record.title], ['id_description', record.description],
                               ['id_sku', record.sku], ['id_price', record.draft_price_usd]]) {
      await native.click(indexFor(ax, l => l.includes(`ID: ${id}`) && !l.includes(`ID: ${id}_`)));
      await native.pressKey(null, 'super+a');
      await native.typeText(null, value);
      await native.pressKey(null, 'Tab');
    }
    ax = await native.getAXState({emit: false, disableDiffing: true});
    for (const [phase, photos] of [['primary', manifest.photos.slice(0, 1)], ['remaining', manifest.photos.slice(1)]]) {
      if (!photos.length) continue;
      const chooserPromise = tab.playwright.waitForEvent('filechooser', {timeoutMs: 10000})
        .then(chooser => ({chooser}), error => ({error: error.message}));
      await native.click(indexFor(ax, l => l.includes('button Upload image ADD UP TO 18 PHOTOS')));
      const result = await chooserPromise;
      if (!result.chooser) throw Error(result.error);
      await result.chooser.setFiles(photos.map(p => p.upload_path || p.path));
      const expectedCount = phase === 'primary' ? 1 : manifest.photos.length;
      try {
        await tab.playwright.locator('img[id^="product-image-thumb-"]').nth(expectedCount - 1)
          .waitFor({state: 'visible', timeoutMs: 20000});
      } catch (error) {
        await native.getAXState({emit: false});
        const observed = await tab.playwright.locator('img[id^="product-image-thumb-"]').evaluateAll(es =>
          es.map(e => e.complete && e.naturalWidth > 0));
        if (observed.length !== expectedCount || observed.some(loaded => !loaded)) throw error;
      }
      ax = await native.getAXState({emit: false, disableDiffing: true});
      if (phase === 'primary') {
        intent.expected_primary_dom_id = await tab.playwright.locator('img[id^="product-image-thumb-"]').first().getAttribute('id');
        await write(intentPath, intent);
      }
    }
    await taxonomy();
    const images = await tab.playwright.locator('img[id^="product-image-thumb-"]').evaluateAll(es =>
      es.map(e => ({id: e.id, loaded: e.complete && e.naturalWidth > 0})));
    if (images.length !== manifest.photos.length || images.some(e => !e.loaded)) throw Error('Uploads still incomplete; form preserved');
    // Chairish can ignore the first title edit during initial form hydration
    // even though the input displays it. Re-enter it once the gallery and
    // taxonomy are ready; independent saved-record readback still follows.
    ax = await native.getAXState({emit: false, disableDiffing: true});
    await native.click(indexFor(ax, l => l.includes('ID: id_title') && !l.includes('ID: id_title_')));
    await native.pressKey(null, 'super+a');
    await native.typeText(null, record.title);
    await native.pressKey(null, 'Tab');
    await native.getAXState({emit: false});
    const entered = await tab.playwright.evaluate(() => ({
      title: document.querySelector('#id_title')?.value,
      description: document.querySelector('#id_description')?.value,
      sku: document.querySelector('#id_sku')?.value,
      price: document.querySelector('#id_price')?.value,
    }));
    if (entered.title !== record.title || entered.description !== record.description ||
        entered.sku !== record.sku || entered.price !== record.draft_price_usd) {
      throw Error('Entered fields changed before Save; form preserved for recovery');
    }
    ax = await native.getAXState({emit: false, disableDiffing: true});
    intent.phase = 'READY_TO_SAVE';
    await write(intentPath, intent);
    await native.click(indexFor(ax, l => /\bbutton SAVE$/.test(l.trim())));
    intent.phase = 'SAVE_SENT';
    await write(intentPath, intent);
    await tab.playwright.waitForURL('https://www.chairish.com/product/list', {timeoutMs: 10000});
    await capture(record.sku);
    return verify(record.sku);
  }

  async function finishCurrent() {
    const intent = await read(intentPath);
    const record = (await records()).find(r => r.sku === intent.sku);
    if (!record || (await read(receiptsPath)).some(r => r.sku === intent.sku) ||
        await tab.url() !== 'https://www.chairish.com/product/create') {
      throw Error('Current form is not an unbound creation; reconcile its saved ID');
    }
    const data = await tab.playwright.evaluate(() => ({
      sku: document.querySelector('#id_sku')?.value,
      title: document.querySelector('#id_title')?.value,
      description: document.querySelector('#id_description')?.value,
      price: document.querySelector('#id_price')?.value,
      photos: Array.from(document.querySelectorAll('img[id^="product-image-thumb-"]')).map(e => ({id: e.id, loaded: e.complete && e.naturalWidth > 0})),
    }));
    if (data.sku !== record.sku || data.title.toLowerCase() !== record.title.toLowerCase() ||
        data.description !== record.description || data.price !== record.draft_price_usd ||
        data.photos.length !== record.photos.length || data.photos.some(p => !p.loaded) ||
        !intent.expected_primary_dom_id || data.photos[0].id !== intent.expected_primary_dom_id) {
      throw Error('Open form does not match complete upload intent');
    }
    await taxonomy();
    const ax = await native.getAXState({emit: false, disableDiffing: true});
    await write(intentPath, {...intent, phase: 'READY_TO_SAVE'});
    await native.click(indexFor(ax, l => /\bbutton SAVE$/.test(l.trim())));
    await write(intentPath, {...intent, phase: 'SAVE_SENT'});
    await tab.playwright.waitForURL('https://www.chairish.com/product/list', {timeoutMs: 10000});
    await capture(record.sku);
    return verify(record.sku);
  }
  async function repairGallery(sku) {
    const rows = await read(receiptsPath);
    const receipt = rows.find(r => r.sku === sku);
    const record = (await records()).find(r => r.sku === sku);
    const manifest = await read(`${directory}/photos/${sku}/manifest.json`);
    if (!receipt || !record || manifest.photo_errors?.length ||
        manifest.photos.length !== record.photos.length || !manifest.photos.length) {
      throw Error('Incomplete source or native binding for gallery repair');
    }
    if (await tab.url() !== receipt.url) await tab.goto(receipt.url);
    let ax = await native.getAXState({emit: false, disableDiffing: true});
    const observedSku = await tab.playwright.locator('#id_sku').evaluate(e => e.value);
    if (observedSku !== sku) throw Error('Wrong saved SKU; no gallery changes made');
    const journalPath = `${directory}/gallery-repair-${sku}.json`;
    const priorPhotos = await tab.playwright.locator('img[id^="product-image-thumb-"]').evaluateAll(es =>
      es.map(e => ({id: e.id, url: e.src})));
    let journal = {sku, native_id: receipt.id, at: new Date().toISOString(), prior_photos: priorPhotos,
      phase: 'REPLACING_DRAFT_GALLERY', expected_count: manifest.photos.length};
    await write(journalPath, journal);
    for (let remaining = priorPhotos.length; remaining > 0; remaining--) {
      await native.click(indexFor(ax, l => /\bbutton Delete image$/.test(l.trim())));
      ax = await native.getAXState({emit: false, disableDiffing: true});
      const count = await tab.playwright.locator('img[id^="product-image-thumb-"]').count();
      if (count !== remaining - 1) throw Error('Unexpected gallery removal result; inspect saved repair journal');
    }
    for (const [phase, photos] of [['primary', manifest.photos.slice(0, 1)], ['remaining', manifest.photos.slice(1)]]) {
      if (!photos.length) continue;
      const chooserPromise = tab.playwright.waitForEvent('filechooser', {timeoutMs: 10000})
        .then(chooser => ({chooser}), error => ({error: error.message}));
      await native.click(indexFor(ax, l => l.includes('button Upload image ADD UP TO 18 PHOTOS')));
      const result = await chooserPromise;
      if (!result.chooser) throw Error(result.error);
      await result.chooser.setFiles(photos.map(p => p.upload_path || p.path));
      const count = phase === 'primary' ? 1 : manifest.photos.length;
      await tab.playwright.locator('img[id^="product-image-thumb-"]').nth(count - 1)
        .waitFor({state: 'attached', timeoutMs: 20000});
      ax = await native.getAXState({emit: false, disableDiffing: true});
      if (phase === 'primary') {
        journal.expected_primary_dom_id = await tab.playwright.locator('img[id^="product-image-thumb-"]').first().getAttribute('id');
        await write(journalPath, journal);
      }
    }
    const complete = await tab.playwright.locator('img[id^="product-image-thumb-"]').evaluateAll(es =>
      es.map(e => e.complete && e.naturalWidth > 0));
    if (complete.length !== manifest.photos.length || complete.some(x => !x)) throw Error('Gallery still uploading; preserve form');
    ax = await native.getAXState({emit: false, disableDiffing: true});
    await native.click(indexFor(ax, l => /\bbutton SAVE$/.test(l.trim())));
    await tab.playwright.getByText(/Your changes have been saved/).waitFor({state: 'attached', timeoutMs: 10000});
    journal.phase = 'SAVED_AWAITING_READBACK';
    await write(journalPath, journal);
    receipt.expected_primary_dom_id = journal.expected_primary_dom_id;
    await write(receiptsPath, rows);
    await tab.reload();
    const result = await verify(sku);
    await write(journalPath, {...journal, phase: result.verified ? 'VERIFIED' : 'SAVED_PENDING_PREVIEWS'});
    return result;
  }
  async function completeDimensions(limit = 3) {
    const results = [];
    const source = await records();
    for (let n = 0; n < limit; n++) {
      const rows = await read(receiptsPath);
      const receipt = rows.find(r => {
        const current = source.find(x => x.sku === r.sku)?.structured_dimensions;
        return current && r.structured_dimensions_source !== JSON.stringify(current);
      });
      if (!receipt) break;
      const record = source.find(x => x.sku === receipt.sku);
      const plan = record.structured_dimensions;
      if (await tab.url() !== receipt.url) await tab.goto(receipt.url);
      await tab.playwright.domSnapshot();
      const observe = () => tab.playwright.evaluate(() => ({
        sku: document.querySelector('#id_sku')?.value,
        title: document.querySelector('#id_title')?.value,
        values: Object.fromEntries(['width', 'depth', 'height'].map(axis =>
          [axis, document.querySelector('#id_dimension_' + axis)?.value])),
        protected: {
          description: document.querySelector('#id_description')?.value,
          photos: Array.from(document.querySelectorAll('img[id^="product-image-thumb-"]')).map(e => e.id),
          commercialFields: Array.from(document.querySelectorAll('input,select,textarea'))
            .filter(e => e.id && /price|quantity|inventory|discount|shipping|pieces|period|condition/.test(e.id))
            .map(e => ({id: e.id, value: e.value,
              checked: ['radio', 'checkbox'].includes(e.type) ? e.checked : undefined})),
        },
      }));
      let before = await observe();
      if (before.sku !== record.sku) {
        const banner = new RegExp('^' + record.title.slice(0, 32).replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'i');
        await tab.playwright.getByText(banner).filter({visible: true}).first()
          .waitFor({state: 'attached', timeoutMs: 5000});
        await tab.playwright.domSnapshot();
        before = await observe();
      }
      if (before.sku !== record.sku) throw Error('Saved product has not loaded; no dimension changes made');
      const changed = [];
      for (const [axis, value] of Object.entries(plan.values)) {
        if (Number(before.values[axis]) === Number(value) && before.values[axis] !== '') continue;
        const input = tab.playwright.locator(`#id_dimension_${axis}`);
        await input.press('Meta+A');
        await input.pressSequentially(value);
        await input.press('Tab');
        changed.push(axis);
      }
      if (changed.length) {
        await tab.playwright.domSnapshot();
        const entered = await observe();
        if (entered.sku !== record.sku || Object.entries(plan.values).some(([axis, value]) =>
            Number(entered.values[axis]) !== Number(value))) throw Error('Dimension entry mismatch; form preserved');
        await tab.playwright.getByRole('button', {name: 'Save', exact: true}).first().click();
        await tab.playwright.getByText(/Your changes have been saved/).waitFor({state: 'attached', timeoutMs: 10000});
        // The toast can appear before the save handler has re-enabled the form.
        // Navigating in that interval raises an unsaved-changes dialog.
        await tab.playwright.getByRole('button', {name: 'Save', exact: true})
          .and(tab.playwright.locator('button:enabled')).first()
          .waitFor({state: 'attached', timeoutMs: 10000});
        await tab.playwright.domSnapshot();
        await tab.reload();
        await tab.playwright.domSnapshot();
      }
      let after = await observe();
      if (after.sku !== record.sku || Object.entries(plan.values).some(([axis, value]) =>
          Number(after.values[axis]) !== Number(value))) {
        // A reload can expose the static form before the saved values hydrate.
        // Wait for the product banner, then compare the exact values again.
        const banner = new RegExp('^' + record.title.slice(0, 32).replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'i');
        await tab.playwright.getByText(banner).filter({visible: true}).first()
          .waitFor({state: 'attached', timeoutMs: 5000});
        await tab.playwright.domSnapshot();
        after = await observe();
      }
      if (after.sku !== record.sku || Object.entries(plan.values).some(([axis, value]) =>
          Number(after.values[axis]) !== Number(value))) throw Error('Saved dimension mismatch: ' + record.sku);
      if (before.title !== after.title || JSON.stringify(before.protected) !== JSON.stringify(after.protected)) {
        await write(`${directory}/dimension-protection-mismatch-${record.sku}.json`, {before, after});
        throw Error('Non-dimension fields changed; stop and inspect: ' + record.sku);
      }
      receipt.structured_dimensions_source = JSON.stringify(plan);
      receipt.structured_dimensions_verified = plan.missing_axes.length === 0;
      receipt.structured_dimension_axes_pending = plan.missing_axes;
      await write(`${directory}/dimensions-readback-${record.sku}.json`, {
        at: new Date().toISOString(), native_id: receipt.id, plan, before, after, changed,
        other_fields_unchanged: true,
      });
      await write(receiptsPath, rows);
      results.push({sku: record.sku, updated_axes: changed, verified_axes: Object.keys(plan.values),
        pending_axes: plan.missing_axes});
    }
    return results;
  }
  return {capture, verify, next, taxonomy, finishCurrent, repairGallery, completeDimensions};
}
