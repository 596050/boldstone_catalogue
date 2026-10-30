import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import { FileBlob, SpreadsheetFile } from '@oai/artifact-tool';
const out = path.dirname(new URL(import.meta.url).pathname);
const manifest = JSON.parse(await fs.readFile(path.join(out, 'final-inputs.json'), 'utf8'));
const oldPlan = JSON.parse(await fs.readFile(path.join(out, '../frozen-inputs/workbook-edit-plan.json'), 'utf8'));
const plan = JSON.parse(await fs.readFile(path.join(out, 'workbook-edit-plan.json'), 'utf8'));
const key = x => x.sheet + '!' + x.cell;
const prior = new Set(oldPlan.cell_changes.map(key));
const changes = plan.cell_changes.filter(x => !prior.has(key(x)));
if (changes.length !== 9) throw new Error('Expected exactly nine additional authored cells');
const input = path.join(out, 'master-workbook.pending');
const hash = data => crypto.createHash('sha256').update(data).digest('hex');
if (hash(await fs.readFile(input)) !== manifest.final_workbook_sha256) throw new Error('Explicit final candidate hash mismatch');
const wb = await SpreadsheetFile.importXlsx(await FileBlob.load(input));
const results = changes.map(x => ({ ...x, actual: wb.worksheets.getItem(x.sheet).getRange(x.cell).values[0][0] }));
for (const x of results) x.equal = x.actual === x.value;
const preview = await wb.render({ sheetName: 'Draft Listings', range: 'M103:O105', scale: 1.5, format: 'png' });
const bytes = new Uint8Array(await preview.arrayBuffer());
const previewPath = path.join(out, 'draft-name-closure.png');
await fs.writeFile(previewPath, bytes);
const result = { status: results.every(x => x.equal) ? 'PASS' : 'FAIL', additional_value_reads: 9, prior_95_value_reads_repeated: false,
  results, preview: { path: previewPath, sha256: hash(bytes), sheet: 'Draft Listings', range: 'M103:O105' },
  workbook_exported_or_modified: false, candidate_bytes_unchanged: hash(await fs.readFile(input)) === manifest.final_workbook_sha256,
  native_Excel_runtime_evaluated: false };
await fs.writeFile(path.join(out, 'artifact-delta-readback.json'), JSON.stringify(result, null, 2) + '\n');
console.log(JSON.stringify({ status: result.status, additional_value_reads: 9, prior_95_value_reads_repeated: false }));
