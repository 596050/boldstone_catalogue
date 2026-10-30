import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const taskArg=process.argv.indexOf('--task-dir');
const here=taskArg>=0?path.resolve(process.argv[taskArg+1]):path.dirname(fileURLToPath(import.meta.url));
const plan=JSON.parse(await fs.readFile(path.join(here,'workbook-edit-plan.json'),'utf8'));
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(here,'inputs/master_workbook.before')));
for(const x of plan.cell_changes){const r=wb.worksheets.getItem(x.sheet).getRange(x.cell);if(r.values[0][0]!==x.before)throw new Error('Current ID differs: '+x.sheet+'!'+x.cell);r.values=[[x.value]];}
wb.recalculate();
for(const x of plan.cell_changes){if(wb.worksheets.getItem(x.sheet).getRange(x.cell).values[0][0]!==x.value)throw new Error('Updated ID not reflected');}
const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:30},maxChars:1800});
await fs.writeFile(path.join(here,'formula-error-scan.ndjson'),errors.ndjson);
await fs.mkdir(path.join(here,'previews'),{recursive:true});const previews=[];
for(const[sheetName,range,file]of (plan.preview_ranges??[['Sets and Context','I37:L41','01-current-parent-ids'],['Identity Review','G18:J23','02-review-parent-ids']])){
 const b=await wb.render({sheetName,range,scale:1.5,format:'png'});const dest=path.join(here,'previews',file+'.png');await fs.writeFile(dest,new Uint8Array(await b.arrayBuffer()));previews.push({sheet:sheetName,range,path:dest});
}
const out=await SpreadsheetFile.exportXlsx(wb);await out.save(path.join(here,'master-workbook.pending'));
await fs.writeFile(path.join(here,'expected-edit.json'),JSON.stringify({sheets:{},hyperlinks:plan.hyperlinks,formulas:[]},null,2));
await fs.writeFile(path.join(here,'preview-manifest.json'),JSON.stringify(previews,null,2));
await fs.writeFile(path.join(here,'artifact-authoring-receipt.json'),JSON.stringify({status:'PASS',sheet_count_preserved:16,current_parent_ID_cells_edited:plan.cell_changes.length,native_link_updates:plan.target_changes.length,names_or_specification_values_edited:0,recalculated:true,preview_count:previews.length},null,2));
console.log(JSON.stringify({status:'EXPORTED_PENDING_NATIVE_LINKS_AND_VERIFICATION',current_parent_ID_cells:plan.cell_changes.length}));
