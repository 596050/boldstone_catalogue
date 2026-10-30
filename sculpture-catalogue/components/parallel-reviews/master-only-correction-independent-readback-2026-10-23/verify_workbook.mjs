import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
import {fileURLToPath} from 'node:url';

const out=path.dirname(fileURLToPath(import.meta.url));
const cat=path.resolve(out,'../../..');
const job=path.join(cat,'components/reconciliation/master-only-source-correction-2026-10-23');
const pointer=JSON.parse(await fs.readFile(path.join(cat,'current-master.json'),'utf8'));
if(!pointer.register.includes('master-only-source-correction-2026-10-23'))throw Error('Correction is not the published master');
const file=path.join(cat,pointer.workbook);
const receipt=JSON.parse(await fs.readFile(path.join(job,'saved-file-verification.json'),'utf8'));
const hash=crypto.createHash('sha256').update(await fs.readFile(file)).digest('hex');
if(hash!==receipt.workbook_sha256||hash!==pointer.workbook_sha256)throw Error('Saved workbook changed since root verification');
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(file));
const ranges=[
 ['Photo Coverage','A2:F5'],
 ['Photo Coverage','A15:L16'],
 ['Master Catalogue','M16:V16'],
 ['Missing Pictures','A2:F4']
];
const inspections=[];
for(const [sheet,range] of ranges){
 const r=await wb.inspect({kind:'table',range:sheet+'!'+range,include:'values,formulas',tableMaxRows:5,tableMaxCols:12,maxChars:5000});
 inspections.push({sheet,range,ndjson:r.ndjson});
}
const cells=[
 ['Photo Coverage','B4',177],['Photo Coverage','B5',11],
 ['Photo Coverage','D4',135],['Photo Coverage','F4',116],
 ['Missing Pictures','B4',72],['Missing Pictures','D4',1],['Missing Pictures','F4',54]
];
const checked=[];
for(const [sheet,cell,expected] of cells){
 const range=wb.worksheets.getItem(sheet).getRange(cell);
 const actual=range.values[0][0];
 if(actual!==expected)throw Error(sheet+'!'+cell+' '+actual+' != '+expected);
 checked.push({sheet,cell,expected,actual,formula:range.formulas[0][0]});
}
const after=crypto.createHash('sha256').update(await fs.readFile(file)).digest('hex');
if(after!==hash)throw Error('Workbook file changed during read-only inspection');
await fs.writeFile(path.join(out,'workbook-artifact-inspection.json'),JSON.stringify({
 status:'PASS_READ_ONLY_ARTIFACT_INSPECTION',file,sha256:hash,cells:checked,
 inspections,workbook_modified:false,workbook_exported:false
},null,2));
console.log(JSON.stringify({status:'PASS_READ_ONLY_ARTIFACT_INSPECTION',sha256:hash,checked_summary_cells:checked.length,inspected_ranges:ranges.length}));
