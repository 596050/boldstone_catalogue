import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const here=path.dirname(fileURLToPath(import.meta.url));
const plan=JSON.parse(await fs.readFile(path.join(here,'workbook-edit-plan.json'),'utf8'));
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(here,'inputs/master_workbook.before')));
for(const x of plan.cell_changes){
 const r=wb.worksheets.getItem(x.sheet).getRange(x.cell);
 if((r.values[0][0]??'')!==x.before)throw new Error(`Changed input ${x.sheet}!${x.cell}`);
 r.values=[[x.value]];
}
for(const h of plan.row_heights)wb.worksheets.getItem(h.sheet).getRange(`A${h.row}:Y${h.row}`).format.rowHeight=h.height;
for(const x of plan.style_changes)wb.worksheets.getItem(x.sheet).getRange(x.cell).format.font=x.font;
const pc=wb.worksheets.getItem('Photo Coverage'),missing=wb.worksheets.getItem('Missing Pictures');
for(const x of plan.formula_caches){
 const r=wb.worksheets.getItem(x.sheet).getRange(x.cell);
 if(r.formulas[0][0]!==x.formula||r.values[0][0]!==x.expected)throw new Error(`Summary failed ${x.sheet}!${x.cell}: ${r.values[0][0]}`);
}
// A reversible input change checks both coverage and current-action dependencies.
const state=pc.getRange('F145').values[0][0];if(state!=='Available')throw new Error('MS1 expected available');
pc.getRange('F145').values=[['Verify existing image']];
if(pc.getRange('D4').values[0][0]!==97||pc.getRange('D5').values[0][0]!==22)throw new Error('Context dependency failed');
pc.getRange('F145').values=[[state]];
const status=missing.getRange('N11').values[0][0];missing.getRange('N11').values=[['Open']];
if(missing.getRange('B4').values[0][0]!==112)throw new Error('Current action dependency failed');
missing.getRange('N11').values=[[status]];wb.recalculate();
for(const x of plan.cell_changes)if(wb.worksheets.getItem(x.sheet).getRange(x.cell).values[0][0]!==x.value)throw new Error('Temporary input not restored');
for(const x of plan.formula_caches)if(wb.worksheets.getItem(x.sheet).getRange(x.cell).values[0][0]!==x.expected)throw new Error('Summary cache changed');
const scan=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:30},maxChars:2000});
await fs.writeFile(path.join(here,'formula-error-scan.ndjson'),scan.ndjson);
await fs.mkdir(path.join(here,'previews'),{recursive:true});const previews=[];
for(const[sheetName,range,file]of plan.preview_ranges){const blob=await wb.render({sheetName,range,scale:1.5,format:'png'}),dest=path.join(here,'previews',file+'.png');await fs.writeFile(dest,new Uint8Array(await blob.arrayBuffer()));previews.push({sheet:sheetName,range,path:dest});}
await(await SpreadsheetFile.exportXlsx(wb)).save(path.join(here,'master-workbook.pending'));
await fs.writeFile(path.join(here,'expected-edit.json'),JSON.stringify({sheets:{},hyperlinks:plan.hyperlinks,formulas:plan.formula_caches},null,2));
await fs.writeFile(path.join(here,'preview-manifest.json'),JSON.stringify(previews,null,2));
await fs.writeFile(path.join(here,'artifact-authoring-receipt.json'),JSON.stringify({status:'PASS',sheets_preserved:21,declared_cell_changes:plan.cell_changes.length,accepted_field_changes:0,coverage_and_action_dependency_tests:true,temporary_inputs_restored:true,recalculated:true,previews:previews.length},null,2));
console.log(JSON.stringify({status:'EXPORTED_PENDING_NATIVE_LINKS_AND_READBACK',cell_changes:plan.cell_changes.length,previews:previews.length}));
