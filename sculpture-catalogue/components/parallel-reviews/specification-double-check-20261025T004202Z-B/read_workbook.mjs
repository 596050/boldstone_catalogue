import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { FileBlob, SpreadsheetFile } from '@oai/artifact-tool';

const here = path.dirname(fileURLToPath(import.meta.url));
const base = '/Users/tprice/Documents/boldstone/sculpture-catalogue';
const sha = b => crypto.createHash('sha256').update(b).digest('hex');
const pointerBytes = await fs.readFile(path.join(base, 'current-master.json'));
const pointer = JSON.parse(pointerBytes);
const workbookPath = path.join(base, pointer.workbook);
const workbookBytes = await fs.readFile(workbookPath);
if (sha(workbookBytes) !== pointer.workbook_sha256) throw new Error('Published workbook hash mismatch');
const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(workbookPath));
const summary = await workbook.inspect({kind:'sheet', include:'id,name', maxChars:8000});
await fs.writeFile(path.join(here,'workbook-sheets.ndjson'),summary.ndjson);
console.log(summary.ndjson);
const names = [pointer.specification_value_owner_sheet, pointer.main_sheet, 'Selling Details'];
const ranges = {'Specifications':'A1:Q1143','Master Catalogue':'A1:Y198','Selling Details':'A1:Q198'};
const out = {read_utc:new Date().toISOString(),workbook_path:workbookPath,workbook_sha256:sha(workbookBytes),pointer_sha256:sha(pointerBytes),sheets:{},workbook_edited:false};
for (const name of [...new Set(names)]) {
  const sheet = workbook.worksheets.getItem(name);
  const range = sheet.getRange(ranges[name]);
  out.sheets[name] = {range:ranges[name],values:range.values,formulas:range.formulas};
  console.log(JSON.stringify({sheet:name,range:ranges[name],rows:out.sheets[name].values.length,header:out.sheets[name].values[8]}));
}
await fs.writeFile(path.join(here,'workbook-readback.json'),JSON.stringify(out,null,2)+'\n');
if (sha(await fs.readFile(workbookPath))!==out.workbook_sha256) throw new Error('Workbook changed during audit');
console.log('Read-only workbook extraction complete. No export or recalculation performed.');
