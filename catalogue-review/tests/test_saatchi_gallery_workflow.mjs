import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import {saatchiGalleryWorkflow} from '../scripts/saatchi_gallery_ui_workflow.mjs';

async function fixture(t, phase = 'SAVE_REQUESTED') {
  const directory = await fs.mkdtemp(path.join(os.tmpdir(), 'saatchi-gallery-test-'));
  t.after(() => fs.rm(directory, {recursive: true, force: true}));
  const write = (name, value) => fs.writeFile(path.join(directory, name), JSON.stringify(value));
  const read = name => fs.readFile(path.join(directory, name), 'utf8').then(JSON.parse);
  const record = {sku: 'TEST-1', title: 'Test sculpture', artwork_id: '123',
    expected_photo_count: 2, ineligible_selected_photos: [],
    additions: [{id: 'photo-2', path: path.join(directory, 'second.jpg'), sha256: 'expected',
      dimensions: [2000, 1500], caption: 'Additional sculpture view'}]};
  const intent = {sku: record.sku, artwork_id: record.artwork_id,
    overview_url: 'https://www.saatchiart.com/en-gb/studio/art/123/overview',
    image_url: 'https://www.saatchiart.com/en-gb/studio/art/123/image',
    phase, baseline_keys: ['primary'], added_photo_ids: ['photo-2'], expected: 2};
  await write('prepared-galleries.json', {records: [record]});
  await write('gallery-edit-intent.json', intent);
  await write('primary-draft-receipts.json', [{sku: record.sku, artwork_id: '123', url: intent.overview_url}]);
  await write('acanthus-created-draft.json', {sku: 'OTHER', artwork_id: '456'});
  const state = {url: intent.overview_url, keys: ['primary', 'second'], mutations: [],
    waitError: null, ax: '', snapshot: '', titleLoaded: true};
  const locator = {
    waitFor: async () => {if (state.waitError) throw state.waitError;},
    evaluateAll: async () => state.keys,
    fill: async value => state.mutations.push(['fill', value]),
    click: async () => state.mutations.push(['click']),
    first() {return this;},
  };
  const tab = {url: async () => state.url,
    goto: async url => {state.mutations.push(['goto', url]); state.url = url;},
    playwright: {getByText: () => locator, getByRole: () => locator,
      evaluate: async (_fn, arg) => arg === record.title ? state.titleLoaded : state.keys,
      domSnapshot: async () => state.snapshot}};
  const native = {getAXState: async () => state.ax,
    click: async id => state.mutations.push(['native-click', id])};
  return {directory, write, read, record, intent, state, tab, native,
    ops: saatchiGalleryWorkflow({tab, native, directory})};
}

test('an uncertain save is only observed, never submitted again', async t => {
  const f = await fixture(t);
  f.state.url = f.intent.image_url;
  const result = await f.ops.advance();
  assert.equal(result.status, 'SAVE_UNCONFIRMED_DO_NOT_REPEAT');
  assert.deepEqual(f.state.mutations, []);
  assert.equal((await f.read('gallery-edit-intent.json')).phase, 'SAVE_REQUESTED');
});

test('a late successful save is reconciled against the original gallery', async t => {
  const f = await fixture(t);
  assert.equal((await f.ops.advance()).completed_galleries, 1);
  const receipts = await f.read('gallery-completion-receipts.json');
  assert.equal(receipts[0].artwork_id, '123');
  assert.deepEqual(receipts[0].native_image_keys, ['primary', 'second']);
  assert.equal((await f.read('gallery-edit-intent.json')).phase, 'VERIFIED');
  assert.deepEqual(f.state.mutations, []);
  await f.ops.capture();
  assert.equal((await f.read('gallery-completion-receipts.json')).length, 1);
});

test('a navigated overview is not counted until its own title has loaded', async t => {
  const f = await fixture(t);
  f.state.titleLoaded = false;
  assert.equal((await f.ops.capture()).status, 'SAVE_UNCONFIRMED_DO_NOT_REPEAT');
  await assert.rejects(f.read('gallery-completion-receipts.json'), {code: 'ENOENT'});
  assert.deepEqual(f.state.mutations, []);
});

test('a matching photo count cannot hide a lost prior photo', async t => {
  const f = await fixture(t);
  f.state.keys = ['wrong-primary', 'second'];
  await assert.rejects(f.ops.advance(), /prior photos changed/);
  await assert.rejects(f.read('gallery-completion-receipts.json'), {code: 'ENOENT'});
  assert.equal((await f.read('gallery-edit-intent.json')).phase, 'SAVE_REQUESTED');
});

test('missing saved photos are not counted as success', async t => {
  const f = await fixture(t);
  f.state.keys = ['primary'];
  await assert.rejects(f.ops.advance(), /gallery count/);
  assert.deepEqual(f.state.mutations, []);
});

test('starting another record cannot abandon a pending gallery', async t => {
  const f = await fixture(t, 'PHOTO_UPLOADING');
  await assert.rejects(f.ops.start(), /Reconcile unfinished gallery/);
  assert.deepEqual(f.state.mutations, []);
});

test('a slow upload is resumed without another upload or submit', async t => {
  const f = await fixture(t, 'PHOTO_UPLOADING');
  await f.write('gallery-edit-intent.json', {...f.intent, added_photo_ids: [], pending_photo_id: 'photo-2'});
  f.state.waitError = new Error('upload still processing');
  await assert.rejects(f.ops.advance(), /upload still processing/);
  assert.deepEqual(f.state.mutations, []);
  const saved = await f.read('gallery-edit-intent.json');
  assert.equal(saved.pending_photo_id, 'photo-2');
  assert.deepEqual(saved.added_photo_ids, []);
});

test('an ambiguous photo submission requires inspection before any retry', async t => {
  const f = await fixture(t, 'PHOTO_SUBMITTING');
  await assert.rejects(f.ops.advance(), /phase needs inspection/);
  assert.deepEqual(f.state.mutations, []);
});

test('native artwork identity conflicts stop before navigation', async t => {
  const f = await fixture(t, 'VERIFIED');
  await f.write('primary-draft-receipts.json', [{sku: 'TEST-1', artwork_id: '999', url: f.intent.overview_url}]);
  await assert.rejects(f.ops.start(), /Missing verified overview URL/);
  assert.deepEqual(f.state.mutations, []);
});

test('unexpected existing additional photos stop before another upload', async t => {
  const f = await fixture(t, 'VERIFIED');
  f.state.keys = ['primary', 'unreconciled-photo'];
  await assert.rejects(f.ops.start(), /Unexpected existing gallery/);
  assert.deepEqual(f.state.mutations, []);
});

test('changed upload bytes cannot reach a file chooser', async t => {
  const f = await fixture(t, 'ADDING');
  f.state.url = f.intent.image_url;
  await f.write('gallery-edit-intent.json', {...f.intent, added_photo_ids: []});
  await fs.writeFile(f.record.additions[0].path, 'changed');
  await assert.rejects(f.ops.addOne(), /Upload bytes changed/);
  assert.deepEqual(f.state.mutations, []);
});

test('another tab cannot start a reserved artwork while its save is pending', async t => {
  const f = await fixture(t, 'VERIFIED');
  await f.write('gallery-other-intent.json', {...f.intent, phase: 'SAVE_REQUESTED'});
  const second = saatchiGalleryWorkflow({tab: f.tab, native: f.native, directory: f.directory,
    otherIntentFiles: ['gallery-other-intent.json']});
  assert.deepEqual(await second.start(), {waiting_for_other_galleries: true, remaining: 1});
  assert.deepEqual(f.state.mutations, []);
});

test('independent tab journals do not overwrite a pending upload', async t => {
  const f = await fixture(t, 'PHOTO_UPLOADING');
  await f.write('gallery-other-intent.json', {...f.intent, phase: 'SAVE_REQUESTED'});
  const second = saatchiGalleryWorkflow({tab: f.tab, native: f.native, directory: f.directory,
    intentFile: 'gallery-other-intent.json', otherIntentFiles: ['gallery-edit-intent.json']});
  await second.capture();
  assert.equal((await f.read('gallery-other-intent.json')).phase, 'VERIFIED');
  assert.equal((await f.read('gallery-edit-intent.json')).phase, 'PHOTO_UPLOADING');
});

test('a chooser deadline is handled even when the opening click is slower', async t => {
  const f = await fixture(t, 'ADDING');
  const bytes = Buffer.from('unchanged-photo');
  await fs.writeFile(f.record.additions[0].path, bytes);
  f.record.additions[0].sha256 = crypto.createHash('sha256').update(bytes).digest('hex');
  await f.write('prepared-galleries.json', {records: [f.record]});
  await f.write('gallery-edit-intent.json', {...f.intent, added_photo_ids: []});
  f.state.url = f.intent.image_url;
  f.state.ax = '1 heading Upload Additional Image';
  f.tab.playwright.waitForEvent = () => Promise.reject(new Error('chooser deadline'));
  f.tab.playwright.locator = () => ({click: () => new Promise(resolve => setTimeout(resolve, 20))});
  await assert.rejects(f.ops.addOne(), /chooser deadline/);
  assert.equal((await f.read('gallery-edit-intent.json')).phase, 'ADDING');
  assert.deepEqual(f.state.mutations, []);
});
