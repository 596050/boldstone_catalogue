import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import { FileBlob, SpreadsheetFile } from '@oai/artifact-tool';

const out = path.dirname(new URL(import.meta.url).pathname);
const frozen = path.join(out, 'frozen-inputs');
const input = path.join(frozen, 'master-workbook.pending');
const plan = JSON.parse(await fs.readFile(path.join(frozen, 'workbook-edit-plan.json'), 'utf8'));
const hash = data => crypto.createHash('sha256').update(data).digest('hex');
const initialHash = hash(await fs.readFile(input));
if (initialHash !== 'c00191988f65cb0ea6417f19dfab84a63eb25cef00fa2442d5b54a7ea8b3e064') throw new Error('Frozen candidate hash mismatch');
const wb = await SpreadsheetFile.importXlsx(await FileBlob.load(input));
const results = [];
for (const [kind, changes] of [['authored', plan.cell_changes], ['calculated', plan.calculated_value_changes]]) {
  for (const item of changes) {
    const range = wb.worksheets.getItem(item.sheet).getRange(item.cell);
    const actual = range.values[0][0];
    results.push({ kind, sheet: item.sheet, cell: item.cell, expected: item.value, actual,
      equal: actual === item.value, formula: range.formulas[0][0] ?? null });
  }
}
const inspect = await wb.inspect({ kind: 'table', range: "'Master Catalogue'!B90:D92", include: 'values,formulas', tableMaxRows: 3, tableMaxCols: 3, maxChars: 3500 });
await fs.writeFile(path.join(out, 'artifact-inspection.ndjson'), inspect.ndjson);
const previews = [];
await fs.mkdir(path.join(out, 'previews'), { recursive: true });
for (const [sheetName, range, name] of [...plan.preview_ranges, ...plan.supplemental_preview_ranges]) {
  const blob = await wb.render({ sheetName, range, scale: 1.5, format: 'png' });
  const bytes = new Uint8Array(await blob.arrayBuffer());
  const target = path.join(out, 'previews', name + '.png');
  await fs.writeFile(target, bytes);
  previews.push({ sheetName, range, path: target, sha256: hash(bytes) });
}
const unchanged = hash(await fs.readFile(input)) === initialHash;
const result = { status: results.every(x => x.equal) && unchanged ? 'PASS' : 'FAIL',
  candidate_sha256: initialHash, authored_value_reads: results.filter(x => x.kind === 'authored').length,
  calculated_value_reads: results.filter(x => x.kind === 'calculated').length,
  failures: results.filter(x => !x.equal), results, previews, original_candidate_bytes_unchanged: unchanged,
  workbook_exported_or_modified: false, native_Excel_runtime_evaluated: false };
await fs.writeFile(path.join(out, 'artifact-value-readback.json'), JSON.stringify(result, null, 2) + '\n');
console.log(JSON.stringify({ status: result.status, authored_value_reads: result.authored_value_reads,
  calculated_value_reads: result.calculated_value_reads, failures: result.failures.length, previews: previews.length }));
