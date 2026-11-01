// Execute inside CUA only; website access is through documented UI controls.
import fs from 'node:fs/promises';
import crypto from 'node:crypto';

export function saatchiGalleryWorkflow({tab, native, directory,
  intentFile = 'gallery-edit-intent.json', otherIntentFiles = []}) {
  const read = async name => JSON.parse(await fs.readFile(`${directory}/${name}`, 'utf8'));
  const optional = async name => read(name).catch(error => {
    if (error.code === 'ENOENT') return [];
    throw error;
  });
  const write = async (name, value) => {
    const path = `${directory}/${name}`;
    await fs.writeFile(path + '.tmp', JSON.stringify(value, null, 2) + '\n');
    await fs.rename(path + '.tmp', path);
  };
  const nativeClick = async label => {
    const state = await native.getAXState({emit: false, disableDiffing: true});
    const line = state.split('\n').find(l => l.trim().match(/^\d+ button /) && l.trim().endsWith(`button ${label}`));
    if (!line) throw Error('Native button not found: ' + label);
    await native.click(Number(line.trim().match(/^\d+/)[0]));
    await native.getAXState({emit: false});
  };
  const imageKeys = async id => tab.playwright.evaluate(id => {
    const urls = Array.from(document.images).map(e => e.getAttribute('src')).filter(s => s && s.includes(`/art/${id}/`));
    return Array.from(new Set(urls.map(s => s.split('?')[0].split('/').pop().replace(/-\d+\.(jpg|png)$/i, ''))));
  }, id);
  const recordFor = async sku => (await read('prepared-galleries.json')).records.find(r => r.sku === sku);

  async function capture() {
    const intent = await read(intentFile);
    const record = await recordFor(intent.sku);
    if (await tab.url() !== intent.overview_url) return {sku: intent.sku, status: 'SAVE_UNCONFIRMED_DO_NOT_REPEAT'};
    const titleVisible = await tab.playwright.evaluate(title =>
      document.body.innerText.split('\n').some(line => line.trim() === title), record.title);
    if (!titleVisible) return {sku: intent.sku, status: 'SAVE_UNCONFIRMED_DO_NOT_REPEAT'};
    const keys = await imageKeys(record.artwork_id);
    if (keys.length !== record.expected_photo_count || !intent.baseline_keys.every(k => keys.includes(k))) {
      await write(`gallery-mismatch-${record.sku}.json`, {intent, keys, expected: record.expected_photo_count});
      throw Error('Saved gallery count or prior photos changed: ' + record.sku);
    }
    const rows = await optional('gallery-completion-receipts.json');
    const receipt = {at: new Date().toISOString(), sku: record.sku, title: record.title,
      artwork_id: record.artwork_id, url: intent.overview_url, photos: keys.length,
      native_image_keys: keys, additional_photo_ids: record.additions.map(p => p.id),
      source_hashes: record.additions.map(p => ({id: p.id, sha256: p.sha256})),
      excluded_photo_ids: record.ineligible_selected_photos,
      overflow_photo_ids: (record.gallery_overflow || []).map(p => p.id),
      status: 'SAVED_OVERVIEW_GALLERY_READBACK_DRAFT_ONLY'};
    const previous = rows.findIndex(r => r.sku === record.sku);
    if (previous === -1) rows.push(receipt); else rows[previous] = receipt;
    await write('gallery-completion-receipts.json', rows);
    await write(intentFile, {...intent, phase: 'VERIFIED', native_image_keys: keys});
    return {sku: record.sku, photos: keys.length, completed_galleries: rows.length};
  }

  async function start() {
    const old = await optional(intentFile);
    if (old.phase && old.phase !== 'VERIFIED') throw Error('Reconcile unfinished gallery: ' + old.sku);
    const completed = await optional('gallery-completion-receipts.json');
    const reservations = await Promise.all(otherIntentFiles.map(optional));
    const reservedSkus = new Set(reservations.filter(r => r.phase && r.phase !== 'VERIFIED').map(r => r.sku));
    const unfinished = (await read('prepared-galleries.json')).records.filter(r => !completed.some(c => c.sku === r.sku));
    const record = unfinished.find(r => !reservedSkus.has(r.sku));
    if (!record) return unfinished.length ? {waiting_for_other_galleries: true, remaining: unfinished.length} : {complete: true, count: completed.length};
    const bindings = await read('primary-draft-receipts.json');
    bindings.push(await read('acanthus-created-draft.json'));
    const binding = bindings.find(r => r.sku === record.sku && r.artwork_id === record.artwork_id);
    if (!binding) throw Error('Missing verified overview URL');
    if (await tab.url() !== binding.url) await tab.goto(binding.url);
    await tab.playwright.getByText(record.title, {exact: true}).waitFor({state: 'visible', timeoutMs: 10000});
    await tab.playwright.domSnapshot();
    const baseline = await imageKeys(record.artwork_id);
    const increments = (await optional('gallery-increment-receipts.json')).filter(x => x.sku === record.sku);
    if (baseline.length !== 1 + increments.length) throw Error('Unexpected existing gallery; reconcile rather than duplicate');
    const intent = {at: new Date().toISOString(), sku: record.sku, artwork_id: record.artwork_id,
      overview_url: binding.url, phase: 'OPENING', baseline_keys: baseline,
      added_photo_ids: increments.map(p => p.photo_id), expected: record.expected_photo_count};
    await write(intentFile, intent);
    if (baseline.length === record.expected_photo_count) return capture();
    await tab.playwright.getByRole('button', {name: 'Edit', exact: true}).first().click();
    await tab.playwright.getByRole('textbox', {name: 'Enter title', exact: true})
      .waitFor({state: 'visible', timeoutMs: 10000});
    const title = await tab.playwright.getByRole('textbox', {name: 'Enter title', exact: true}).evaluate(e => e.value);
    if (title !== record.title) throw Error('Artwork title not loaded or mismatched');
    const state = await native.getAXState({emit: false, disableDiffing: true});
    const imageButton = state.split('\n').find(l => /button Images, Help:/.test(l));
    if (!imageButton) throw Error('Images accordion missing');
    if (imageButton.includes('Help: Expand')) {
      await native.click(Number(imageButton.trim().match(/^\d+/)[0]));
      await native.getAXState({emit: false});
    }
    await write(intentFile, {...intent, phase: 'ADDING', image_url: await tab.url()});
    return {sku: record.sku, expected: record.expected_photo_count, to_add: record.additions.length - increments.length};
  }

  async function addOne() {
    const intent = await read(intentFile);
    if (intent.phase !== 'ADDING') throw Error('Gallery is not ready for another photo');
    const record = await recordFor(intent.sku);
    if (await tab.url() !== intent.image_url) throw Error('Wrong image editor');
    const photo = record.additions.find(p => !intent.added_photo_ids.includes(p.id));
    if (!photo) return {sku: record.sku, ready_to_save: true};
    const hash = crypto.createHash('sha256').update(await fs.readFile(photo.path)).digest('hex');
    if (hash !== photo.sha256) throw Error('Upload bytes changed');
    let ax = await native.getAXState({emit: false, disableDiffing: true});
    if (!ax.includes('heading Upload Additional Image')) {
      await nativeClick('ADD ADDITIONAL IMAGE');
      ax = await native.getAXState({emit: false, disableDiffing: true});
    }
    if (!ax.includes('heading Upload Additional Image')) throw Error('Upload dialog did not open');
    await tab.playwright.domSnapshot();
    // Attach rejection handling immediately: a slow click can outlast the chooser
    // deadline, and an unhandled rejection would otherwise reset the CUA session.
    const chooserPromise = tab.playwright.waitForEvent('filechooser', {timeoutMs: 10000})
      .then(chooser => ({chooser}), error => ({error}));
    await tab.playwright.locator('[data-type="browse-text"]').click();
    const chooserResult = await chooserPromise;
    if (chooserResult.error) throw chooserResult.error;
    const chooser = chooserResult.chooser;
    await write(intentFile, {...intent, phase: 'PHOTO_UPLOADING', pending_photo_id: photo.id});
    await chooser.setFiles([photo.path]);
    return finishUpload();
  }

  async function finishUpload() {
    const intent = await read(intentFile);
    if (!['ADDING', 'PHOTO_UPLOADING'].includes(intent.phase)) throw Error('No resumable photo upload');
    const record = await recordFor(intent.sku);
    const photo = record.additions.find(p => p.id === intent.pending_photo_id) ||
      record.additions.find(p => !intent.added_photo_ids.includes(p.id));
    if (!photo) throw Error('No expected photo for this dialog');
    const dimensions = `${photo.dimensions[0]} x ${photo.dimensions[1]} px`;
    let ax;
    try { await tab.playwright.getByText(dimensions, {exact: true}).waitFor({state: 'visible', timeoutMs: 15000}); }
    catch (error) {
      ax = await native.getAXState({emit: false, disableDiffing: true});
      if (!ax.replace(/\s+/g, ' ').includes(dimensions)) throw error;
    }
    const snapshot = await tab.playwright.domSnapshot();
    if (!snapshot.includes(photo.path.split('/').pop())) throw Error('Uploaded filename does not match expected photo');
    await tab.playwright.getByRole('textbox', {name: 'Enter Caption', exact: true}).fill(photo.caption);
    await write(intentFile, {...intent, phase: 'PHOTO_SUBMITTING', pending_photo_id: photo.id});
    await nativeClick('Submit');
    ax = await native.getAXState({emit: false, disableDiffing: true});
    if (ax.includes('heading Additional Image') || ax.includes('heading Upload Additional Image')) {
      throw Error('Uploaded photo not committed; inspect pending photo before retrying');
    }
    await tab.playwright.domSnapshot();
    const next = {...intent, phase: 'ADDING', added_photo_ids: [...intent.added_photo_ids, photo.id]};
    delete next.pending_photo_id;
    await write(intentFile, next);
    return {sku: record.sku, staged_additions: next.added_photo_ids.length, total_additions: record.additions.length};
  }

  async function save() {
    const intent = await read(intentFile);
    const record = await recordFor(intent.sku);
    if (intent.phase !== 'ADDING' || intent.added_photo_ids.length !== record.additions.length) {
      throw Error('Do not save an incomplete or uncertain gallery');
    }
    const state = await native.getAXState({emit: false, disableDiffing: true});
    const nextButtons = state.split('\n').filter(l => l.trim().match(/^\d+ button Next$/));
    if (nextButtons.length !== 2) throw Error('Expected title and image Next buttons');
    await native.click(Number(nextButtons.at(-1).trim().match(/^\d+/)[0]));
    await native.getAXState({emit: false});
    await write(intentFile, {...intent, phase: 'SAVE_REQUESTED'});
    await nativeClick('SAVE & EXIT');
    // Observe only. A slow response must never trigger a repeated save.
    await native.getAXState({emit: false});
    return capture();
  }
  async function advance() {
    const intent = await optional(intentFile);
    if (!intent.phase || intent.phase === 'VERIFIED') return start();
    if (intent.phase === 'SAVE_REQUESTED') {
      await native.getAXState({emit: false});
      return capture();
    }
    if (intent.phase === 'PHOTO_UPLOADING') return finishUpload();
    if (intent.phase === 'ADDING') {
      const record = await recordFor(intent.sku);
      return intent.added_photo_ids.length === record.additions.length ? save() : addOne();
    }
    throw Error('Gallery phase needs inspection: ' + intent.phase);
  }
  return {start, addOne, finishUpload, save, capture, advance};
}
