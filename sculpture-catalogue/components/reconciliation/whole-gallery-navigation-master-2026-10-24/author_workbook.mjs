import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {FileBlob, SpreadsheetFile} from '@oai/artifact-tool';

const h=path.dirname(fileURLToPath(import.meta.url));
const p=JSON.parse(await fs.readFile(path.join(h,'workbook-edit-plan.json'),'utf8'));
const source=process.argv.includes('--saved-preview')?'master-workbook.pending':'inputs/master_workbook.before';
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(h,source)));
await fs.mkdir(path.join(h,'previews'),{recursive:true});
async function render(ranges){
  const result=[];
  for(const[sheetName,range,name]of ranges){
    const blob=await wb.render({sheetName,range,scale:1.25,format:'png'});
    const output=path.join(h,'previews',name+'.png');
    await fs.writeFile(output,new Uint8Array(await blob.arrayBuffer()));
    result.push({sheetName,range,path:output});
  }
  return result;
}
if(process.argv.includes('--baseline')){
  await fs.writeFile(path.join(h,'baseline-preview-manifest.json'),JSON.stringify(await render(p.baseline_ranges),null,2));
  console.log('BASELINE_RENDERED_NO_AUTHORING');
  process.exit(0);
}
if(process.argv.includes('--saved-preview')){
  await fs.writeFile(path.join(h,'saved-preview-manifest.json'),JSON.stringify(await render(p.preview_ranges.concat(p.supplemental_preview_ranges)),null,2));
  console.log('SAVED_PREVIEWS_RENDERED_NO_AUTHORING');
  process.exit(0);
}
for(const edit of p.cell_changes){
  const current=wb.worksheets.getItem(edit.sheet).getRange(edit.cell).values[0][0]??'';
  if(current!==edit.before)throw new Error('Input drift '+edit.sheet+'!'+edit.cell);
}
for(const edit of p.cell_changes){
  wb.worksheets.getItem(edit.sheet).getRange(edit.cell).values=[[edit.value]];
}
wb.recalculate();
for(const expected of p.summary_expected){
  const actual=wb.worksheets.getItem(expected.sheet).getRange(expected.cell).values[0][0];
  if(actual!==expected.value)throw new Error('Summary drift '+expected.sheet+'!'+expected.cell+': '+actual);
}
const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:20},maxChars:2500});
await fs.writeFile(path.join(h,'formula-error-scan.ndjson'),errors.ndjson);
await fs.writeFile(path.join(h,'preview-manifest.json'),JSON.stringify(await render(p.preview_ranges),null,2));
await(await SpreadsheetFile.exportXlsx(wb)).save(path.join(h,'master-workbook.pending'));
await fs.writeFile(path.join(h,'artifact-authoring-receipt.json'),JSON.stringify({status:'EXPORTED_FOR_SAVED_FILE_VERIFICATION',targeted_value_changes:p.cell_changes.length,planned_native_hyperlink_changes:p.native_link_changes.length,recalculated:true,formula_text_changes:0,sheet_changes:0,physical_specification_or_identity_changes:0,native_or_platform_writes:0},null,2));
console.log('TARGETED_CURRENT_NAVIGATION_WORKBOOK_EXPORTED');
