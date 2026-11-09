import fs from 'node:fs/promises';
import {Workbook} from '@oai/artifact-tool';
const root = new URL('../', import.meta.url);
const plan = JSON.parse(await fs.readFile(new URL('squarespace-title-plan.json', root), 'utf8'));
const workbook = await Workbook.fromCSV(await fs.readFile(new URL('squarespace-before.csv', root), 'utf8'), {sheetName:'Products'});
const sheet = workbook.worksheets.getItem('Products');
const rows = sheet.getRange(`A1:AH${plan.rows_before+1}`).values;
const header = rows[0];
const variantColumn = header.indexOf('Variant ID [Non Editable]');
const titleColumn = header.indexOf('Title');
const changes = new Map(plan.changes.map(r => [r.variant_id, r]));
const selected=[];
for (let i=1;i<rows.length;i++) {
  const change=changes.get(rows[i][variantColumn]);
  if (!change) continue;
  if(rows[i][titleColumn] !== change.old) throw new Error('Source title drift');
  sheet.getRange(`F${i+1}`).values=[[change.new]];
  selected.push(i);
}
if(selected.length!==62) throw new Error('Wrong update count');
workbook.recalculate();
const after=sheet.getRange(`A1:AH${plan.rows_before+1}`).values;
// The supported artifact API imports CSV but exposes no documented CSV exporter.
// Serialize the authored cell values with RFC4180 quoting for the native importer.
const csvCell = v => '"'+String(v ?? '').replaceAll('"','""')+'"';
const output=[header,...selected.map(i=>after[i])].map(row=>row.map(csvCell).join(',')).join('\r\n')+'\r\n';
await fs.writeFile(new URL('squarespace-finish-titles.csv',root),output);
console.log(JSON.stringify({authored_rows:selected.length,columns:header.length,first_title:after[selected[0]][titleColumn]}));
