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
// A changed source dimension must reach its master value, with temporary input restored.
const sp=wb.worksheets.getItem('Specifications'),master=wb.worksheets.getItem('Master Catalogue'),pc=wb.worksheets.getItem('Photo Coverage'),mp=wb.worksheets.getItem('Missing Pictures');
const dim=sp.getRange('D496').values[0][0];sp.getRange('D496').values=[['TEMPORARY_DIMENSION_DEPENDENCY_CHECK']];
if(master.getRange('E91').values[0][0]!=='TEMPORARY_DIMENSION_DEPENDENCY_CHECK')throw Error('Dimension dependency failed');sp.getRange('D496').values=[[dim]];
const state=pc.getRange('F95').values[0][0];if(state!=='Available')throw Error('White FFS2 row shifted');
pc.getRange('F95').values=[['Verify existing image']];if(pc.getRange('D4').values[0][0]!==116||pc.getRange('D5').values[0][0]!==3)throw Error('Photo dependency failed');pc.getRange('F95').values=[[state]];
const resolved=mp.getRange('N76').values[0][0];if(resolved!=='Resolved')throw Error('Owner resolved action row shifted');mp.getRange('N76').values=[['Open']];if(mp.getRange('D4').values[0][0]!==7)throw Error('Missing-picture dependency failed');mp.getRange('N76').values=[[resolved]];
wb.recalculate();
for(const x of plan.cell_changes)if(wb.worksheets.getItem(x.sheet).getRange(x.cell).values[0][0]!==x.value)throw Error('Temporary input not restored');
for(const x of plan.formula_caches)if(wb.worksheets.getItem(x.sheet).getRange(x.cell).values[0][0]!==x.expected)throw Error('Final cache mismatch');
const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:30},maxChars:1800});await fs.writeFile(path.join(here,'formula-error-scan.ndjson'),errors.ndjson);
const previews=[];for(const[sheetName,range,name]of plan.preview_ranges){const b=await wb.render({sheetName,range,scale:1.5,format:'png'}),p=path.join(here,'previews',name+'.png');await fs.writeFile(p,new Uint8Array(await b.arrayBuffer()));previews.push({sheet:sheetName,range,path:p});}
await(await SpreadsheetFile.exportXlsx(wb)).save(path.join(here,'master-workbook.pending'));
await fs.writeFile(path.join(here,'expected-edit.json'),JSON.stringify({sheets:{},hyperlinks:plan.hyperlinks,formulas:plan.formula_caches},null,2));
await fs.writeFile(path.join(here,'preview-manifest.json'),JSON.stringify(previews,null,2));
await fs.writeFile(path.join(here,'artifact-authoring-receipt.json'),JSON.stringify({status:'PASS',baseline_rendered_and_inspected:true,dimension_and_coverage_dependency_checks:true,temporary_inputs_restored:true,recalculated:true,previews:previews.length,cell_changes:plan.cell_changes.length},null,2));
console.log(JSON.stringify({status:'EXPORTED_PENDING_NATIVE_READBACK',cell_changes:plan.cell_changes.length,previews:previews.length}));
