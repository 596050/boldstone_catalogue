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
for(const x of plan.formula_caches){const r=wb.worksheets.getItem(x.sheet).getRange(x.cell);if(r.formulas[0][0]!==x.formula||r.values[0][0]!==x.expected)throw Error('Recalculated value mismatch '+x.sheet+'!'+x.cell+' '+r.values[0][0]);}
// Reversible checks verify the changed image-role and outstanding-action counts.
const pc=wb.worksheets.getItem('Photo Coverage'),mp=wb.worksheets.getItem('Missing Pictures'),t=plan.dependency_test;
const state=pc.getRange(t.coverage_cell).values[0][0];if(state!=='Available')throw Error('Mapped row shifted');
pc.getRange(t.coverage_cell).values=[['Verify existing image']];
if(pc.getRange('D4').values[0][0]!==t.available_after||pc.getRange('D5').values[0][0]!==t.verify_after)throw Error('Coverage dependency failed');
pc.getRange(t.coverage_cell).values=[[state]];
const resolved=mp.getRange(t.action_cell).values[0][0];if(resolved!=='Resolved')throw Error('Resolved action row shifted');
mp.getRange(t.action_cell).values=[['Open']];if(mp.getRange('D4').values[0][0]!==t.actions_after)throw Error('Action dependency failed');mp.getRange(t.action_cell).values=[[resolved]];
wb.recalculate();
for(const x of plan.cell_changes)if(wb.worksheets.getItem(x.sheet).getRange(x.cell).values[0][0]!==x.value)throw Error('Temporary input not restored');
for(const x of plan.formula_caches)if(wb.worksheets.getItem(x.sheet).getRange(x.cell).values[0][0]!==x.expected)throw Error('Final cache mismatch');
const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:30},maxChars:1800});await fs.writeFile(path.join(here,'formula-error-scan.ndjson'),errors.ndjson);
const previews=[];for(const[sheetName,range,name]of plan.preview_ranges){const b=await wb.render({sheetName,range,scale:1.5,format:'png'}),p=path.join(here,'previews',name+'.png');await fs.writeFile(p,new Uint8Array(await b.arrayBuffer()));previews.push({sheet:sheetName,range,path:p});}
await(await SpreadsheetFile.exportXlsx(wb)).save(path.join(here,'master-workbook.pending'));
await fs.writeFile(path.join(here,'expected-edit.json'),JSON.stringify({sheets:{},hyperlinks:plan.hyperlinks,formulas:plan.formula_caches},null,2));
await fs.writeFile(path.join(here,'preview-manifest.json'),JSON.stringify(previews,null,2));
await fs.writeFile(path.join(here,'artifact-authoring-receipt.json'),JSON.stringify({status:'PASS',baseline_rendered_and_inspected:true,coverage_and_action_dependency_checks:true,temporary_inputs_restored:true,recalculated:true,previews:previews.length,cell_changes:plan.cell_changes.length},null,2));
console.log(JSON.stringify({status:'EXPORTED_PENDING_NATIVE_READBACK',cell_changes:plan.cell_changes.length,previews:previews.length}));
