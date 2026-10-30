import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const h=path.dirname(fileURLToPath(import.meta.url));
const p=JSON.parse(await fs.readFile(path.join(h,'workbook-edit-plan.json'),'utf8'));
const saved=process.argv.includes('--saved-preview');
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(h,saved?'master-workbook.pending':'inputs/master_workbook.before')));
await fs.mkdir(path.join(h,'previews'),{recursive:true});
async function render(ranges){const out=[];for(const[sheetName,range,name]of ranges){const b=await wb.render({sheetName,range,scale:1.3,format:'png'}),file=path.join(h,'previews',name+'.png');await fs.writeFile(file,new Uint8Array(await b.arrayBuffer()));out.push({sheet:sheetName,range,path:file});}return out;}
if(process.argv.includes('--baseline')){await render(p.baseline_ranges);console.log('BASELINE_RENDERED_NO_AUTHORING');process.exit(0);}
if(saved){const views=await render(p.supplemental_preview_ranges);await fs.writeFile(path.join(h,'supplemental-preview-manifest.json'),JSON.stringify(views,null,2));console.log('SAVED_PREVIEWS_RENDERED_NO_AUTHORING');process.exit(0);}
for(const x of p.cell_changes)if((wb.worksheets.getItem(x.sheet).getRange(x.cell).values[0][0]??'')!==x.before)throw Error('Input drift '+x.sheet+'!'+x.cell);
const col=n=>{let s='';for(n++;n;n=Math.floor((n-1)/26))s=String.fromCharCode(65+(n-1)%26)+s;return s;};
for(const t of p.table_appends){const s=wb.worksheets.getItem(t.sheet),end=col(t.columns-1);s.tables.items[0].rows.add(null,Array.from({length:t.rows},()=>Array(t.columns).fill(null)));for(let i=1;i<=t.rows;i++)s.getRange(`A${t.old_last+i}:${end}${t.old_last+i}`).copyFrom(s.getRange(`A${t.old_last}:${end}${t.old_last}`),'all');}
for(const x of p.value_blocks)wb.worksheets.getItem(x.sheet).getRange(x.range).values=x.values.map(r=>r.map(v=>v===''?null:v));
for(const x of p.formula_blocks)wb.worksheets.getItem(x.sheet).getRange(x.range).formulas=x.formulas;
for(const x of p.row_heights)wb.worksheets.getItem(x.sheet).getRange('A'+x.row+':Y'+x.row).format.rowHeight=x.height;
const value=(s,c)=>wb.worksheets.getItem(s).getRange(c).values[0][0],eq=(a,b,label)=>{if(a!==b)throw Error(label+': '+JSON.stringify(a)+' != '+JSON.stringify(b));};
function test(s,c,temp,fn){const r=wb.worksheets.getItem(s).getRange(c),before=r.values[0][0];r.values=[[temp]];fn();r.values=[[before]];}
test('Specifications','I'+p.first_spec_row,0,()=>{eq(value('Master Catalogue','K'+p.new_option_row),5,'New field acceptance reaches option');eq(value('Master Catalogue','F4'),187,'New acceptance changes current completeness total');});
test('Specifications','D'+p.price_spec_row,'£999 temporary dependency check',()=>eq(value('Selling Details','C'+p.new_option_row),'£999 temporary dependency check','New price propagates to selling view'));
test('Specifications','D'+p.last_spec_row,'Made to order; lead time 1 week — temporary check',()=>{eq(value('Selling Details','G'+p.new_option_row),'1 week','New lead time classification');eq(value('Selling Details','H4'),2,'New lead time contributes to summary');});
test('Specifications','D'+p.first_spec_row,null,()=>{eq(value('Specifications','Q'+p.first_spec_row),0,'New blank field is unusable');eq(value('Master Catalogue','K'+p.new_option_row),5,'New blank reduces completeness');});
test('Specifications','P'+p.first_spec_row,value('Specifications','P'+(p.first_spec_row-1)),()=>{eq(value('Specifications','Q'+p.first_spec_row),0,'New duplicate key rejected');eq(value('Specifications','Q'+(p.first_spec_row-1)),0,'Earlier duplicate key rejected through extended range');});
wb.recalculate();
for(const x of p.summary_expected)eq(value(x.sheet,x.cell),x.value,'Current summary '+x.sheet+'!'+x.cell);
for(const x of p.formula_changes.filter(x=>!x.before))eq(value(x.sheet,x.cell),x.expected,'New formula '+x.sheet+'!'+x.cell);
const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:20},maxChars:1800});await fs.writeFile(path.join(h,'formula-error-scan.ndjson'),errors.ndjson);
const previews=await render(p.preview_ranges);await(await SpreadsheetFile.exportXlsx(wb)).save(path.join(h,'master-workbook.pending'));
await fs.writeFile(path.join(h,'preview-manifest.json'),JSON.stringify(previews,null,2));
await fs.writeFile(path.join(h,'artifact-authoring-receipt.json'),JSON.stringify({status:'PASS',recalculated:true,temporary_inputs_restored:true,new_active_options:1,new_component_identities:0,new_physical_verifications:0,native_or_platform_writes:0,dependency_checks:['New field acceptance','New price to selling view','New lead time classification and summary','Blank field usability','Duplicate field key across prior/new rows']},null,2));
console.log('WATER_OPTION_AND_MOONPHASE_MEMBERS_MASTER_EXPORTED');
