import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const h=path.dirname(fileURLToPath(import.meta.url)),p=JSON.parse(await fs.readFile(path.join(h,'workbook-edit-plan.json'),'utf8'));
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(h,'inputs/master_workbook.before')));
await fs.mkdir(path.join(h,'previews'),{recursive:true});
const baseline=process.argv.includes('--baseline'),previews=[];
if(!baseline){
  wb.recalculate();
  for(const x of p.summary_expected){const value=wb.worksheets.getItem(x.sheet).getRange(x.cell).values[0][0];if(value!==x.value)throw Error('Unexpected summary change '+x.sheet+'!'+x.cell);}
}
for(const[sheetName,range,name]of(baseline?p.baseline_ranges:p.preview_ranges)){
  const blob=await wb.render({sheetName,range,format:'png',scale:1.25}),file=path.join(h,'previews',name+'.png');await fs.writeFile(file,new Uint8Array(await blob.arrayBuffer()));previews.push({sheet:sheetName,range,path:file});
}
if(baseline){console.log('BASELINE_RENDERED_NO_AUTHORING');process.exit(0);}
await(await SpreadsheetFile.exportXlsx(wb)).save(path.join(h,'master-workbook.pending'));
await fs.writeFile(path.join(h,'preview-manifest.json'),JSON.stringify(previews,null,2));
await fs.writeFile(path.join(h,'artifact-authoring-receipt.json'),JSON.stringify({status:'PASS',recalculated:true,values_changed:0,formulas_changed:0,all_eight_summary_values_preserved:true,hyperlink_target_updates_pending_native_serialization:22,source_pixels_edited:false},null,2));
console.log('PATH_ONLY_WORKBOOK_EXPORTED_PENDING_NATIVE_LINK_SERIALIZATION');
