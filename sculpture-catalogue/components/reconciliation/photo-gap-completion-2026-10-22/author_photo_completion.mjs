import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const here=path.dirname(fileURLToPath(import.meta.url)),plan=JSON.parse(await fs.readFile(path.join(here,'workbook-edit-plan.json'),'utf8'));
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(here,'inputs/master_workbook.before')));
await fs.mkdir(path.join(here,'previews'),{recursive:true});
if(process.argv.includes('--baseline')){
 for(const[sheetName,range,name]of plan.baseline_ranges){const blob=await wb.render({sheetName,range,scale:1.5,format:'png'});await fs.writeFile(path.join(here,'previews',name+'.png'),new Uint8Array(await blob.arrayBuffer()));}
 console.log('BASELINE_RENDERED');process.exit(0);
}
for(const x of plan.cell_changes){const r=wb.worksheets.getItem(x.sheet).getRange(x.cell);if((r.values[0][0]??'')!==x.before)throw Error('Input changed '+x.sheet+'!'+x.cell);r.values=[[x.value]];}
for(const x of plan.row_heights)wb.worksheets.getItem(x.sheet).getRange('A'+x.row+':Y'+x.row).format.rowHeight=x.height;
for(const x of plan.style_changes)wb.worksheets.getItem(x.sheet).getRange(x.cell).format.font=x.font;
for(const x of plan.formula_caches){const r=wb.worksheets.getItem(x.sheet).getRange(x.cell);if(r.formulas[0][0]!==x.formula||r.values[0][0]!==x.expected)throw Error('Recalculated value mismatch '+x.sheet+'!'+x.cell+' '+r.values[0][0]);}
const pc=wb.worksheets.getItem('Photo Coverage'),mp=wb.worksheets.getItem('Missing Pictures');
for(const t of plan.dependency_tests){
 const total=t.role==='In situ'?'D4':'F4',value=pc.getRange(total).values[0][0],state=pc.getRange(t.coverage_cell).values[0][0];if(state!=='Available')throw Error('Role row shifted');
 pc.getRange(t.coverage_cell).values=[['No verified image']];if(pc.getRange(total).values[0][0]!==value-1)throw Error('Role dependency failed');pc.getRange(t.coverage_cell).values=[[state]];
 const count=mp.getRange('B4').values[0][0],status=mp.getRange(t.action_cell).values[0][0];if(status!=='Resolved')throw Error('Resolved action row shifted');
 mp.getRange(t.action_cell).values=[['Open']];if(mp.getRange('B4').values[0][0]!==count+1)throw Error('Action dependency failed');mp.getRange(t.action_cell).values=[[status]];
}
wb.recalculate();
for(const x of plan.cell_changes)if(wb.worksheets.getItem(x.sheet).getRange(x.cell).values[0][0]!==x.value)throw Error('Temporary input not restored');
for(const x of plan.formula_caches)if(wb.worksheets.getItem(x.sheet).getRange(x.cell).values[0][0]!==x.expected)throw Error('Final cache mismatch');
const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:30},maxChars:1800});await fs.writeFile(path.join(here,'formula-error-scan.ndjson'),errors.ndjson);
const previews=[];for(const[sheetName,range,name]of plan.preview_ranges){const b=await wb.render({sheetName,range,scale:1.5,format:'png'}),p=path.join(here,'previews',name+'.png');await fs.writeFile(p,new Uint8Array(await b.arrayBuffer()));previews.push({sheet:sheetName,range,path:p});}
await(await SpreadsheetFile.exportXlsx(wb)).save(path.join(here,'master-workbook.pending'));
await fs.writeFile(path.join(here,'expected-edit.json'),JSON.stringify({sheets:{},hyperlinks:plan.hyperlinks,formulas:plan.formula_caches},null,2));
await fs.writeFile(path.join(here,'preview-manifest.json'),JSON.stringify(previews,null,2));
await fs.writeFile(path.join(here,'artifact-authoring-receipt.json'),JSON.stringify({status:'PASS',baseline_rendered_and_inspected:true,role_and_action_dependency_checks:plan.dependency_tests.length,temporary_inputs_restored:true,recalculated:true,previews:previews.length,cell_changes:plan.cell_changes.length},null,2));
console.log(JSON.stringify({status:'EXPORTED_PENDING_NATIVE_READBACK',cell_changes:plan.cell_changes.length,previews:previews.length}));
