import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const h=path.dirname(fileURLToPath(import.meta.url)),read=async n=>JSON.parse(await fs.readFile(path.join(h,n),'utf8'));
const plan=await read('workbook-edit-plan.json');
const clearOnly=process.argv.includes('--clear-appended-blanks')||process.argv.includes('--refresh-current-references');
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(h,clearOnly?'master-workbook.pending':'inputs/master_workbook.before')));
await fs.mkdir(path.join(h,'previews'),{recursive:true});
const render=async ranges=>{const out=[];for(const[sheetName,range,name]of ranges){const b=await wb.render({sheetName,range,scale:1.3,format:'png'}),p=path.join(h,'previews',name+'.png');await fs.writeFile(p,new Uint8Array(await b.arrayBuffer()));out.push({sheet:sheetName,range,path:p});}return out;};
if(process.argv.includes('--baseline')){await render(plan.baseline_ranges);console.log('BASELINE_RENDERED_NO_AUTHORING');process.exit(0);}
if(clearOnly){
 const boundaries={'Master Catalogue':195,'Specifications':1125,'Photo Coverage':195,'Listing Resolution':195,'Draft Listings':111,'Selling Details':195,'Missing Pictures':214};
 const blanks=plan.cell_changes.filter(c=>c.value===''&&Number(c.cell.replace(/\D/g,''))>(boundaries[c.sheet]??1e9));
 for(const b of plan.value_blocks)wb.worksheets.getItem(b.sheet).getRange(b.range).values=b.values.map(r=>r.map(v=>v===''?null:v));
 wb.recalculate();
 for(const x of plan.summary_expected){const v=wb.worksheets.getItem(x.sheet).getRange(x.cell).values[0][0];if(v!==x.value)throw Error('Summary drift after blank-label correction '+x.sheet+'!'+x.cell);}
 const previews=await render(plan.preview_ranges);await(await SpreadsheetFile.exportXlsx(wb)).save(path.join(h,'master-workbook.pending'));await fs.writeFile(path.join(h,'preview-manifest.json'),JSON.stringify(previews,null,2));await fs.writeFile(path.join(h,'appended-blank-correction.json'),JSON.stringify({status:'PASS',cleared_copied_blank_cells:blanks.length,current_value_blocks_applied:plan.value_blocks.length,recalculated:true,summary_results_preserved:true,formulas_changed:false},null,2));console.log('CURRENT_REFERENCES_AND_BLANKS_REFRESHED');process.exit(0);
}
for(const c of plan.cell_changes)if((wb.worksheets.getItem(c.sheet).getRange(c.cell).values[0][0]??'')!==c.before)throw Error('Source drift '+c.sheet+'!'+c.cell);
const col=n=>{let s='';for(n++;n;n=Math.floor((n-1)/26))s=String.fromCharCode(65+(n-1)%26)+s;return s;};
for(const p of plan.table_appends){const s=wb.worksheets.getItem(p.sheet),end=col(p.columns-1);s.tables.items[0].rows.add(null,Array.from({length:p.rows},()=>Array(p.columns).fill(null)));for(let i=1;i<=p.rows;i++)s.getRange(`A${p.old_last+i}:${end}${p.old_last+i}`).copyFrom(s.getRange(`A${p.old_last}:${end}${p.old_last}`),'all');}
for(const b of plan.value_blocks)wb.worksheets.getItem(b.sheet).getRange(b.range).values=b.values;
for(const b of plan.formula_blocks)wb.worksheets.getItem(b.sheet).getRange(b.range).formulas=b.formulas;
for(const r of plan.row_heights)wb.worksheets.getItem(r.sheet).getRange(`A${r.row}:Y${r.row}`).format.rowHeight=r.height;
const amber={fill:'#FFF3D6',font:{color:'#9C440D'}},red={fill:'#FBE8E6',font:{color:'#A22E29'}};
wb.worksheets.getItem('Master Catalogue').getRange('K196:K197').conditionalFormats.add('cellIs',{operator:'notEqual',formula:6,format:amber});
for(const c of ['C','F','I']){const r=wb.worksheets.getItem('Photo Coverage').getRange(`${c}196:${c}197`);r.conditionalFormats.add('containsText',{text:'Verify',format:amber});r.conditionalFormats.add('containsText',{text:'No verified',format:red});}
const spec=wb.worksheets.getItem('Specifications'),master=wb.worksheets.getItem('Master Catalogue'),selling=wb.worksheets.getItem('Selling Details'),photo=wb.worksheets.getItem('Photo Coverage');
const eq=(a,b,label)=>{if(a!==b)throw Error(label+': '+JSON.stringify(a)+' != '+JSON.stringify(b));};
const value=(s,c)=>s.getRange(c).values[0][0];
const test=(s,c,temporary,assert)=>{const saved=value(s,c);s.getRange(c).values=[[temporary]];assert();s.getRange(c).values=[[saved]];};
test(spec,'I'+plan.one_leaf_spec_row,0,()=>{eq(value(master,'K'+plan.one_leaf_master_row),5,'Existing One Leaf acceptance dependency');eq(value(master,'F4'),187,'Existing option summary dependency');});
test(spec,'I1137',0,()=>{eq(value(master,'K197'),5,'Appended final field dependency');eq(value(master,'F4'),187,'Appended option summary dependency');});
test(spec,'D1130','£999 temporary dependency check',()=>eq(value(selling,'C196'),'£999 temporary dependency check','New price reaches selling view'));
test(spec,'D1137','Made to order; lead time 1 week — temporary dependency check',()=>{eq(value(selling,'G197'),'1 week','Lead-time class dependency');eq(value(selling,'H4'),2,'One-week count dependency');});
test(spec,'D1126',null,()=>{eq(value(spec,'Q1126'),0,'Blank field remains unusable');eq(value(master,'K196'),5,'Blank field surfaces in option completeness');});
test(spec,'P1126',value(spec,'P1125'),()=>{eq(value(spec,'Q1126'),0,'Appended duplicate key rejected');eq(value(spec,'Q1125'),0,'Earlier duplicate key rejected across extended range');});
test(photo,'C196','No verified image',()=>{eq(value(photo,'B4'),169,'New photo status count dependency');eq(value(photo,'B5'),19,'New photo gap count dependency');});
wb.recalculate();
for(const x of plan.summary_expected)eq(value(wb.worksheets.getItem(x.sheet),x.cell),x.value,'Summary '+x.sheet+'!'+x.cell);
for(const x of plan.formula_changes.filter(x=>Number(x.cell.replace(/\D/g,''))>=196&&['Master Catalogue','Selling Details'].includes(x.sheet)))eq(value(wb.worksheets.getItem(x.sheet),x.cell),x.expected,'Appended formula '+x.sheet+'!'+x.cell);
const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:20},maxChars:1500});await fs.writeFile(path.join(h,'formula-error-scan.ndjson'),errors.ndjson);
const previews=await render(plan.preview_ranges);
await(await SpreadsheetFile.exportXlsx(wb)).save(path.join(h,'master-workbook.pending'));
await fs.writeFile(path.join(h,'expected-edit.json'),JSON.stringify({sheets:{},hyperlinks:plan.hyperlinks,formulas:[]},null,2));
await fs.writeFile(path.join(h,'preview-manifest.json'),JSON.stringify(previews,null,2));
await fs.writeFile(path.join(h,'artifact-authoring-receipt.json'),JSON.stringify({status:'PASS',current_options:188,working_component_identities:112,field_groups:1128,new_tabs:0,recalculated:true,dependency_checks:['Existing owner acceptance','Appended final field','Price to selling view','Lead-time classification','Blank working value','Duplicate field key across old/new range','New photo-status count'],temporary_inputs_restored:true,original_pixels_edited:false},null,2));
console.log('PEWTER_MASTER_EXPORTED_PENDING_SAVED_FILE_VERIFICATION');
