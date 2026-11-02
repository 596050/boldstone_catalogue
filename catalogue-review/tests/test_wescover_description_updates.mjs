import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import {wescoverDescriptionUpdates} from '../scripts/wescover_description_updates.mjs';

async function fixture(t, url, resolved = []) {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'boldstone-wescover-copy-'));
  t.after(() => fs.rm(root, {recursive: true, force: true}));
  await fs.mkdir(path.join(root, 'wescover-current'));
  await fs.mkdir(path.join(root, 'catalogue-copy-disclosures'));
  const write = (name, value) => fs.writeFile(path.join(root, name), JSON.stringify(value));
  await write('current-prepared-catalogue.json', {records: [{sku: 'S-1'}]});
  await write('wescover-current/enrichment-receipts.json', [{sku: 'S-1', title: 'Existing sculpture', url}]);
  await write('wescover-current/verified-edit-bindings.json', resolved);
  const calls = [];
  const tab = {
    url: async () => {calls.push('url'); return '';},
    goto: async value => {calls.push(value); throw Error('Unexpected browser navigation');},
  };
  return {workflow: wescoverDescriptionUpdates({tab, root}), calls};
}

for (const query of ['item=new&product=new', 'item=existing&product=new']) {
  test(`historical creation URL cannot open a new-product form: ${query}`, async t => {
    const {workflow, calls} = await fixture(t, `https://edit.wescover.com/creator/example?${query}`);
    await assert.rejects(workflow.run(1), /Resolve the existing native edit link/);
    assert.deepEqual(calls, [], 'Must stop before any browser navigation or mutation');
  });
}

test('a resolved edit mapping with the wrong title cannot be used', async t => {
  const {workflow, calls} = await fixture(t,
    'https://edit.wescover.com/creator/example?item=new&product=new',
    [{sku: 'S-1', title: 'Different sculpture', url: 'https://edit.wescover.com/creator/example?item=old&product=old'}]);
  await assert.rejects(workflow.run(1), /Resolved title mismatch/);
  assert.deepEqual(calls, [], 'Conflicting identity must stop before browser access');
});
