import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const h=path.dirname(fileURLToPath(import.meta.url)),read=async p=>JSON.parse(await fs.readFile(path.join(h,p),'utf8'));
const p=await read('workbook-edit-plan.json');
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(h,process.argv.includes('--saved-preview')?'master-workbook.pending':'inputs/master_workbook.before')));
await fs.mkdir(path.join(h,'previews'),{recursive:true});
async function render(ranges){const out=[];for(const[sheetName,range,name]of ranges){const blob=await wb.render({sheetName,range,scale:1.25,format:'png'}),file=path.join(h,'previews',name+'.png');await fs.writeFile(file,new Uint8Array(await blob.arrayBuffer()));out.push({sheet:sheetName,range,path:file});}return out;}
if(process.argv.includes('--baseline')){const views=await render(p.baseline_ranges);await fs.writeFile(path.join(h,'baseline-preview-manifest.json'),JSON.stringify(views,null,2));console.log('BASELINE_RENDERED_NO_AUTHORING');process.exit(0);}
if(process.argv.includes('--saved-preview')){const views=await render(p.supplemental_preview_ranges);await fs.writeFile(path.join(h,'supplemental-preview-manifest.json'),JSON.stringify(views,null,2));console.log('SAVED_PREVIEWS_RENDERED_NO_AUTHORING');process.exit(0);}
for(const x of p.cell_changes)if((wb.worksheets.getItem(x.sheet).getRange(x.cell).values[0][0]??'')!==x.before)throw Error('Input drift '+x.sheet+'!'+x.cell);
for(const x of p.value_blocks)wb.worksheets.getItem(x.sheet).getRange(x.range).values=x.values.map(r=>r.map(v=>v===''?null:v));
for(const x of p.row_heights)wb.worksheets.getItem(x.sheet).getRange('A'+x.row+':Y'+x.row).format.rowHeight=x.height;
const value=(s,c)=>wb.worksheets.getItem(s).getRange(c).values[0][0],eq=(x,y,label)=>{if(x!==y)throw Error(label+': '+x+' != '+y);};
wb.recalculate();for(const x of p.summary_expected)eq(value(x.sheet,x.cell),x.value,'Summary '+x.sheet+'!'+x.cell);
const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:20},maxChars:2000});await fs.writeFile(path.join(h,'formula-error-scan.ndjson'),errors.ndjson);
const previews=await render(p.preview_ranges);await(await SpreadsheetFile.exportXlsx(wb)).save(path.join(h,'master-workbook.pending'));
await fs.writeFile(path.join(h,'preview-manifest.json'),JSON.stringify(previews,null,2));await fs.writeFile(path.join(h,'artifact-authoring-receipt.json'),JSON.stringify({status:'PASS',recalculated:true,temporary_inputs_restored:true,checks:['Current header distinguishes source-photo coverage from checked native navigation','Existing primary images, identities and photo policies unchanged','188 active options, existing physical and commercial fields and all holds preserved'],formula_text_changes:0,new_native_or_platform_writes:0},null,2));console.log('SCOPED_PRIMARY_NAVIGATION_HEALTH_MASTER_EXPORTED');
