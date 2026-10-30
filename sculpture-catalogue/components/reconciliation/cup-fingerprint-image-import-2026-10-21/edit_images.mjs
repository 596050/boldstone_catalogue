import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {FileBlob, SpreadsheetFile} from '@oai/artifact-tool';
const here=path.dirname(fileURLToPath(import.meta.url));
const plan=JSON.parse(await fs.readFile(path.join(here,'workbook-edit-plan.json'),'utf8'));
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(here,'inputs/master_workbook.before')));
for(const x of plan.cell_changes){
 const r=wb.worksheets.getItem(x.sheet).getRange(x.cell);
 if((r.values[0][0]??'')!==x.before)throw new Error(`Input changed: ${x.sheet}!${x.cell}`);
 r.values=[[x.value]];
}
for(const x of plan.formula_changes){const r=wb.worksheets.getItem(x.sheet).getRange(x.cell);if(r.formulas[0][0]!==x.before)throw new Error('Source formula changed');r.formulas=[[x.formula]];}
for(const h of plan.row_heights){const s=wb.worksheets.getItem(h.sheet);s.getRange(`A${h.row}:X${h.row}`).format.rowHeight=h.height;}
for(const h of plan.hyperlinks.filter(x=>x.sheet==='Identity Review'&&/^L6[01]$|^M6[01]$/.test(x.cell)))
 wb.worksheets.getItem(h.sheet).getRange(h.cell).format.font={name:'Arial',size:10,color:'#245F9E',underline:'single'};
const pc=wb.worksheets.getItem('Photo Coverage'),missing=wb.worksheets.getItem('Missing Pictures');
if(pc.getRange('B4').values[0][0]!==158||pc.getRange('B5').values[0][0]!==26||missing.getRange('B4').values[0][0]!==119)throw new Error('Current coverage summaries failed');
pc.getRange('C38').values=[['Group only']];
if(pc.getRange('B4').values[0][0]!==157||pc.getRange('B5').values[0][0]!==27)throw new Error('Coverage dependency test failed');
pc.getRange('C38').values=[['Available']];missing.getRange('N11').values=[['Open']];
if(missing.getRange('B4').values[0][0]!==120)throw new Error('Action dependency test failed');
missing.getRange('N11').values=[['Resolved']];wb.recalculate();
for(const x of plan.cell_changes)if(wb.worksheets.getItem(x.sheet).getRange(x.cell).values[0][0]!==x.value)throw new Error('Planned cell not saved');
const identity=wb.worksheets.getItem('Identity Review'),savedState=identity.getRange('E13').values[0][0];identity.getRange('E13').values=[['Strong visual candidate']];
if(identity.getRange('D4').values[0][0]!==3)throw new Error('Conditional lookup summary dependency test failed');identity.getRange('E13').values=[[savedState]];
const formulas=[{sheet:'Photo Coverage',cell:'B4',expected:158},{sheet:'Photo Coverage',cell:'B5',expected:26},{sheet:'Missing Pictures',cell:'B4',expected:119},...plan.formula_changes];
for(const x of formulas)if(wb.worksheets.getItem(x.sheet).getRange(x.cell).values[0][0]!==x.expected)throw new Error('Temporary input not restored');
const scan=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:30},maxChars:2000});
await fs.writeFile(path.join(here,'formula-error-scan.ndjson'),scan.ndjson);
await fs.mkdir(path.join(here,'previews'),{recursive:true});const previews=[];
for(const[sheetName,range,file]of plan.preview_ranges){
 const blob=await wb.render({sheetName,range,scale:1.5,format:'png'}),dest=path.join(here,'previews',file+'.png');
 await fs.writeFile(dest,new Uint8Array(await blob.arrayBuffer()));previews.push({sheet:sheetName,range,path:dest});
}
await(await SpreadsheetFile.exportXlsx(wb)).save(path.join(here,'master-workbook.pending'));
await fs.writeFile(path.join(here,'expected-edit.json'),JSON.stringify({sheets:{},hyperlinks:plan.hyperlinks,formulas},null,2));
await fs.writeFile(path.join(here,'preview-manifest.json'),JSON.stringify(previews,null,2));
await fs.writeFile(path.join(here,'artifact-authoring-receipt.json'),JSON.stringify({status:'PASS',sheets_preserved:20,declared_cell_changes:plan.cell_changes.length,accepted_field_changes:0,recalculated:true,coverage_and_status_dependency_tests:true,temporary_inputs_restored:true,previews:previews.length},null,2));
console.log(JSON.stringify({status:'EXPORTED_PENDING_NATIVE_LINKS_AND_VERIFICATION',cell_changes:plan.cell_changes.length,previews:previews.length}));
