import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const h=path.dirname(fileURLToPath(import.meta.url));
const p=JSON.parse(await fs.readFile(path.join(h,'workbook-edit-plan.json'),'utf8'));
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(h,'inputs/master_workbook.before')));
await fs.mkdir(path.join(h,'previews'),{recursive:true});
async function render(ranges){const out=[];for(const[sheetName,range,name]of ranges){const blob=await wb.render({sheetName,range,scale:1.25,format:'png'});const file=path.join(h,'previews',name+'.png');await fs.writeFile(file,new Uint8Array(await blob.arrayBuffer()));out.push({sheet:sheetName,range,path:file});}return out;}
if(process.argv.includes('--baseline')){await render(p.baseline_ranges);console.log('BASELINE_RENDERED_NO_AUTHORING');process.exit(0);}
for(const x of p.cell_changes){const old=wb.worksheets.getItem(x.sheet).getRange(x.cell).values[0][0]??'';if(old!==x.before)throw Error('Source drift '+x.sheet+'!'+x.cell);}
for(const x of p.value_blocks)wb.worksheets.getItem(x.sheet).getRange(x.range).values=x.values;
for(const x of p.formula_changes)if(x.formula!==x.before)wb.worksheets.getItem(x.sheet).getRange(x.cell).formulas=[[x.formula]];
wb.worksheets.getItem('Missing Pictures').getRange('N10:N220').dataValidation={rule:{type:'list',values:['Open','In progress','Resolved','Optional','Retired / not applicable']}};
const val=(s,c)=>wb.worksheets.getItem(s).getRange(c).values[0][0];
const eq=(a,b,label)=>{if(a!==b)throw Error(label+': '+a+' != '+b);};
function probe(sheet,cell,value,check){const r=wb.worksheets.getItem(sheet).getRange(cell),before=r.values[0][0];r.values=[[value]];check();r.values=[[before]];}
const lifecycle=wb.worksheets.getItem('Specifications').getRange('E46:E51'),retiredStates=lifecycle.values;
lifecycle.values=Array.from({length:6},()=>['Historical working state']);
eq(val('Master Catalogue','B4'),188,'Active-option count responds to source lifecycle');
eq(val('Master Catalogue','F4'),188,'Usable working-field count responds to source lifecycle');
lifecycle.values=retiredStates;
probe('Specifications','E46','Historical accepted proposal',()=>{eq(val('Specifications','Q46'),1,'Specification usability responds to lifecycle');eq(val('Master Catalogue','K16'),1,'Master reads usable field source');});
probe('Photo Coverage','C16','No verified image',()=>eq(val('Photo Coverage','B5'),11,'Retired image excluded from technical gaps'));
probe('Missing Pictures','N13','Open',()=>eq(val('Missing Pictures','B4'),67,'Retired photo task excluded from open work'));
probe('Draft Listings','C12','Individual option draft',()=>eq(val('Draft Listings','B4'),101,'Retired draft excluded from active drafts'));
wb.recalculate();
for(const x of p.summary_expected)eq(val(x.sheet,x.cell),x.value,'Expected '+x.sheet+'!'+x.cell);
const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:20},maxChars:2000});await fs.writeFile(path.join(h,'formula-error-scan.ndjson'),errors.ndjson);
const previews=await render(p.preview_ranges);await(await SpreadsheetFile.exportXlsx(wb)).save(path.join(h,'master-workbook.pending'));
await fs.writeFile(path.join(h,'preview-manifest.json'),JSON.stringify(previews,null,2));
await fs.writeFile(path.join(h,'artifact-authoring-receipt.json'),JSON.stringify({status:'PASS',recalculated:true,temporary_inputs_restored:true,checks:['Active catalogue lifecycle count','Historical specification usability','Retired image exclusion','Retired action reopening','Retired draft exclusion'],source_history_preserved:true,native_or_platform_writes:0},null,2));
console.log('RETIREMENT_WORKBOOK_EXPORTED_PENDING_VERIFICATION');
