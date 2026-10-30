import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const h=path.dirname(fileURLToPath(import.meta.url)),read=async n=>JSON.parse(await fs.readFile(path.join(h,n),'utf8'));
const plan=await read('workbook-edit-plan.json'),data=await read('workbook-data.json');
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(h,'inputs/master_workbook.before')));
await fs.mkdir(path.join(h,'previews'),{recursive:true});
if(process.argv.includes('--baseline')){
 for(const[sheetName,range,name]of plan.baseline_ranges){const b=await wb.render({sheetName,range,scale:1.5,format:'png'});await fs.writeFile(path.join(h,'previews',name+'.png'),new Uint8Array(await b.arrayBuffer()));}
 console.log('BASELINE_RENDERED');process.exit(0);
}
const col=n=>{let s='';for(n++;n;n=Math.floor((n-1)/26))s=String.fromCharCode(65+(n-1)%26)+s;return s;};
const plain=x=>x&&typeof x==='object'&&'target'in x?x.label:x,links=[...plan.hyperlinks];
for(const c of plan.cell_changes)if((wb.worksheets.getItem(c.sheet).getRange(c.cell).values[0][0]??'')!==c.before)throw Error('Source value drift '+c.sheet+'!'+c.cell);
for(const p of data.table_appends){
 const s=wb.worksheets.getItem(p.sheet),last=p.old_last_row,end=col(p.columns-1);s.tables.items[0].rows.add(null,p.rows.map(r=>r.map(plain)));
 for(let i=0;i<p.rows.length;i++)s.getRange(`A${last+i+1}:${end}${last+i+1}`).copyFrom(s.getRange(`A${last}:${end}${last}`),'all');
 s.getRange(`A${last+1}:${end}${last+p.rows.length}`).values=p.rows.map(r=>r.map(plain));
 p.rows.forEach((r,i)=>r.forEach((v,j)=>{if(v&&typeof v==='object'&&'target'in v)links.push({sheet:p.sheet,cell:col(j)+(last+i+1),...v});}));
}
for(const c of plan.value_blocks)wb.worksheets.getItem(c.sheet).getRange(c.range).values=c.values;
for(const c of plan.row_heights)wb.worksheets.getItem(c.sheet).getRange(`A${c.row}:Y${c.row}`).format.rowHeight=c.height;
for(const f of plan.formula_changes)wb.worksheets.getItem(f.sheet).getRange(f.cell).formulas=[[f.formula]];
const folders=wb.worksheets.getItem('Moonphases and Dune'),saved=folders.getRange('B63').values[0][0];
folders.getRange('B63').values=[[null]];if(folders.getRange('B4').values[0][0]!==57)throw Error('Folder summary does not follow added source rows');folders.getRange('B63').values=[[saved]];wb.recalculate();
for(const f of plan.formula_changes)if(wb.worksheets.getItem(f.sheet).getRange(f.cell).values[0][0]!==f.expected)throw Error('Formula mismatch '+f.sheet+'!'+f.cell);
for(const[sn,c,expected]of [['Master Catalogue','B4',186],['Master Catalogue','D4',112],['Master Catalogue','F4',186],['Photo Coverage','B5',19],['Selling Details','B4',186],['Selling Details','D4',185],['Selling Details','F4',185],['Selling Details','H4',1]])if(wb.worksheets.getItem(sn).getRange(c).values[0][0]!==expected)throw Error('Unchanged dependency drift '+sn+'!'+c);
const inspected=await wb.inspect({kind:'region',sheetId:'Moonphases and Dune',range:'A63:H67',maxChars:2200});await fs.writeFile(path.join(h,'artifact-current-folder-inspection.ndjson'),inspected.ndjson);
console.log('CURRENT_REFERENCES_AND_SUMMARY_DEPENDENCIES_VERIFIED');
const previews=[];
for(const[sheetName,range,name]of plan.preview_ranges){const b=await wb.render({sheetName,range,scale:1.5,format:'png'}),p=path.join(h,'previews',name+'.png');await fs.writeFile(p,new Uint8Array(await b.arrayBuffer()));previews.push({sheet:sheetName,range,path:p});}
await(await SpreadsheetFile.exportXlsx(wb)).save(path.join(h,'master-workbook.pending'));
await fs.writeFile(path.join(h,'expected-edit.json'),JSON.stringify({sheets:{},hyperlinks:links,formulas:[]},null,2));await fs.writeFile(path.join(h,'preview-manifest.json'),JSON.stringify(previews,null,2));
await fs.writeFile(path.join(h,'artifact-authoring-receipt.json'),JSON.stringify({status:'PASS',original_sheets:28,new_sheets:0,cell_changes:plan.cell_changes.length,owning_folder_summary_dependency_verified:true,temporary_input_restored:true,recalculated:true,current_options:186,current_components:112,individual_gaps:19,specification_or_commercial_changes:0},null,2));console.log('EXPORTED_PENDING_NATIVE_VERIFICATION');
