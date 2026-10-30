import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const h=process.env.BOLDSTONE_ARTIFACT_JOB_DIR??path.dirname(fileURLToPath(import.meta.url)),read=async n=>JSON.parse(await fs.readFile(path.join(h,n),'utf8'));
const p=await read('workbook-edit-plan.json'),g=await read('canonical-master-register.json'),audit=await read('image-coverage-current.json');
const renderCurrent=process.argv.includes('--render-current-folder-notes');
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(h,renderCurrent?'master-workbook.pending':'inputs/master_workbook.before')));
await fs.mkdir(path.join(h,'previews'),{recursive:true});
const render=async ranges=>{const out=[];for(const[sheetName,range,name]of ranges){const blob=await wb.render({sheetName,range,scale:1.25,format:'png'}),file=path.join(h,'previews',name+'.png');await fs.writeFile(file,new Uint8Array(await blob.arrayBuffer()));out.push({sheet:sheetName,range,path:file});}return out;};
if(process.argv.includes('--baseline')){await render(p.baseline_ranges);console.log('BASELINE_RENDERED_NO_AUTHORING');process.exit(0);}
if(renderCurrent){const previews=await render([['Gleneagles Folders','M9:P10','06-gleneagles-folder-approval'],['Lava Moon Folders','M9:P10','07-lava-folder-approval']]);await fs.writeFile(path.join(h,'additional-preview-manifest.json'),JSON.stringify(previews,null,2));console.log('CURRENT_FOLDER_NOTES_RENDERED_NO_AUTHORING');process.exit(0);}
for(const x of p.cell_changes){const v=wb.worksheets.getItem(x.sheet).getRange(x.cell).values[0][0]??'';if(v!==x.before)throw Error('Input drift '+x.sheet+'!'+x.cell);}
for(const x of p.value_blocks)wb.worksheets.getItem(x.sheet).getRange(x.range).values=x.values.map(r=>r.map(v=>v===''?null:v));
for(const x of p.row_heights)wb.worksheets.getItem(x.sheet).getRange('A'+x.row+':Y'+x.row).format.rowHeight=x.height;
const photo=wb.worksheets.getItem('Photo Coverage'),missing=wb.worksheets.getItem('Missing Pictures'),spec=wb.worksheets.getItem('Specifications'),master=wb.worksheets.getItem('Master Catalogue');
const value=(s,c)=>s.getRange(c).values[0][0],eq=(a,b,label)=>{if(a!==b)throw Error(label+': '+JSON.stringify(a)+' != '+JSON.stringify(b));};
const test=(s,c,v,assert)=>{const saved=value(s,c);s.getRange(c).values=[[v]];assert();s.getRange(c).values=[[saved]];};
const row=g.options.findIndex(x=>x.product_id==='BSI-53239DE28BCA')+10;
test(photo,'C'+row,'Group only',()=>{eq(value(photo,'B4'),176,'Complete image status summary');eq(value(photo,'B5'),12,'Technical image gap summary');});
const actionrow=audit.missing_pictures.findIndex(x=>x.option_id==='BSI-53239DE28BCA'&&x.role==='Individual')+10;
test(missing,'N'+actionrow,'Open',()=>eq(value(missing,'B4'),80,'Accepted action can reopen independently of technical role'));
const insiturow=g.options.findIndex(x=>x.product_id==='BSI-923D5E50A898')+10;
test(photo,'F'+insiturow,'No verified image',()=>eq(value(photo,'D4'),127,'Qualified in situ summary follows current binding'));
for(const oid of ['BSI-B1DCB5B08396','BSI-725A77437026','BSI-D7C2FC84A86B','BSI-63B177B06578'])eq(value(photo,'C'+(g.options.findIndex(x=>x.product_id===oid)+10)),'Group only','Owner exception preserves technical group coverage');
const fishrow=g.options.findIndex(x=>x.product_id==='BSI-86E6AEA0EB98')+10,specrow=(fishrow-10)*6+10;
test(spec,'I'+specrow,0,()=>{eq(value(master,'K'+fishrow),5,'Scoped working field completeness');eq(value(master,'F4'),187,'Current working-field coverage');});
wb.recalculate();
for(const x of p.summary_expected)eq(value(wb.worksheets.getItem(x.sheet),x.cell),x.value,'Current summary '+x.sheet+'!'+x.cell);
const inspected=await wb.inspect({kind:'table',range:'Photo Coverage!A2:L5',include:'values,formulas',tableMaxRows:4,tableMaxCols:12,maxChars:5000});await fs.writeFile(path.join(h,'summary-inspection.ndjson'),inspected.ndjson);
const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:20},maxChars:2000});await fs.writeFile(path.join(h,'formula-error-scan.ndjson'),errors.ndjson);
const previews=await render(p.preview_ranges);
await(await SpreadsheetFile.exportXlsx(wb)).save(path.join(h,'master-workbook.pending'));
await fs.writeFile(path.join(h,'expected-edit.json'),JSON.stringify({sheets:{},hyperlinks:p.hyperlinks,formulas:[]},null,2));
await fs.writeFile(path.join(h,'preview-manifest.json'),JSON.stringify(previews,null,2));
await fs.writeFile(path.join(h,'artifact-authoring-receipt.json'),JSON.stringify({status:'PASS',recalculated:true,checks:['Complete image status counts','Scoped accepted action reopening','Qualified in situ status count','Owner exceptions preserve technical group coverage','Working completeness still depends on accepted source fields'],temporary_inputs_restored:true,formulas_authored_or_replaced:0,new_tabs:0,rows_added:0,image_pixels_edited:false},null,2));
console.log('MASTER_EXPORTED_PENDING_NATIVE_AND_VISUAL_VERIFICATION');
