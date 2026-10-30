import fs from 'node:fs/promises';
import crypto from 'node:crypto';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const out=path.join(path.dirname(fileURLToPath(import.meta.url)),'final');
await fs.mkdir(out,{recursive:true});
const root='/Users/tprice/Documents/boldstone/sculpture-catalogue/components/reconciliation/whole-gallery-navigation-master-2026-10-24';
const filename=path.join(root,'master-workbook.pending');
const hash=async p=>crypto.createHash('sha256').update(await fs.readFile(p)).digest('hex');
const expected='4d78ad49271f02efc1ae0331e79509169aa41b972533fbae650d0f1cdb3e6bf5';
if(await hash(filename)!==expected)throw new Error('Unexpected candidate workbook');
const plan=JSON.parse(await fs.readFile(path.join(root,'workbook-edit-plan.json'),'utf8'));
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(filename));
const checks=[];
for(const item of plan.cell_changes){
  const value=wb.worksheets.getItem(item.sheet).getRange(item.cell).values[0][0];
  checks.push({sheet:item.sheet,cell:item.cell,passed:value===item.value});
}
const region=await wb.inspect({kind:'table',range:"'Master Catalogue'!N188:R190",include:'values,formulas',tableMaxRows:3,tableMaxCols:5,maxChars:2800});
if(checks.some(x=>!x.passed))throw new Error(JSON.stringify(checks.filter(x=>!x.passed)));
if(await hash(filename)!==expected)throw new Error('Read-only import changed candidate bytes');
const receipt={status:'PASS_ARTIFACT_TOOL_READ_ONLY_IMPORT',candidate:filename,candidate_sha256:expected,planned_value_checks:checks.length,checks,inspection:region.ndjson,workbook_writes:0,export_performed:false};
await fs.writeFile(path.join(out,'artifact-readback.json'),JSON.stringify(receipt,null,2)+'\n');
console.log(JSON.stringify({status:receipt.status,planned_value_checks:checks.length,workbook_writes:0}));
