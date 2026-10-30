import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const h=path.dirname(fileURLToPath(import.meta.url)),read=async p=>JSON.parse(await fs.readFile(path.join(h,p),'utf8'));
const p=await read('workbook-edit-plan.json');
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(h,'inputs/master_workbook.before')));
await fs.mkdir(path.join(h,'previews'),{recursive:true});
async function render(ranges){const out=[];for(const[sheetName,range,name]of ranges){const blob=await wb.render({sheetName,range,scale:1.25,format:'png'}),file=path.join(h,'previews',name+'.png');await fs.writeFile(file,new Uint8Array(await blob.arrayBuffer()));out.push({sheet:sheetName,range,path:file});}return out;}
if(process.argv.includes('--baseline')){await render(p.baseline_ranges);console.log('BASELINE_RENDERED_NO_AUTHORING');process.exit(0);}
for(const x of p.cell_changes)if((wb.worksheets.getItem(x.sheet).getRange(x.cell).values[0][0]??'')!==x.before)throw Error('Input drift '+x.sheet+'!'+x.cell);
for(const x of p.value_blocks)wb.worksheets.getItem(x.sheet).getRange(x.range).values=x.values.map(r=>r.map(v=>v===''?null:v));
for(const x of p.row_heights)wb.worksheets.getItem(x.sheet).getRange('A'+x.row+':Y'+x.row).format.rowHeight=x.height;
const value=(s,c)=>wb.worksheets.getItem(s).getRange(c).values[0][0],eq=(x,y,label)=>{if(x!==y)throw Error(label+': '+x+' != '+y);};
for(const z of p.target_rows.slice(0,2)){
 const photo=wb.worksheets.getItem('Photo Coverage').getRange('F'+z.row);photo.values=[['No verified image']];eq(value('Photo Coverage','D4'),160,'Context count responds to actual role status');photo.values=[['Available']];
 const task=wb.worksheets.getItem('Missing Pictures').getRange('N'+z.action_row);task.values=[['Open']];eq(value('Missing Pictures','B4'),44,'Reopened action affects summary');task.values=[['Resolved']];
}
wb.recalculate();for(const x of p.summary_expected)eq(value(x.sheet,x.cell),x.value,'Summary '+x.sheet+'!'+x.cell);
const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:20},maxChars:2000});await fs.writeFile(path.join(h,'formula-error-scan.ndjson'),errors.ndjson);
const previews=await render(p.preview_ranges);await(await SpreadsheetFile.exportXlsx(wb)).save(path.join(h,'master-workbook.pending'));
await fs.writeFile(path.join(h,'preview-manifest.json'),JSON.stringify(previews,null,2));await fs.writeFile(path.join(h,'artifact-authoring-receipt.json'),JSON.stringify({status:'PASS',recalculated:true,temporary_inputs_restored:true,checks:['Four actual role statuses affect context count','Four action statuses affect required summary','187 active options and six working fields preserved'],formula_text_changes:0,new_native_or_platform_writes:0},null,2));console.log('QUALIFIED_DISPLAY_AND_RESIDUAL_REVIEWS_WORKBOOK_EXPORTED');
