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
for(const c of plan.cell_changes)if((wb.worksheets.getItem(c.sheet).getRange(c.cell).values[0][0]??'')!==c.before)throw Error('Source value drift '+c.sheet+'!'+c.cell);
for(const c of plan.value_blocks)wb.worksheets.getItem(c.sheet).getRange(c.range).values=c.values;
for(const c of plan.row_heights)wb.worksheets.getItem(c.sheet).getRange(`A${c.row}:Y${c.row}`).format.rowHeight=c.height;
const col=n=>{let s='';for(n++;n;n=Math.floor((n-1)/26))s=String.fromCharCode(65+(n-1)%26)+s;return s;};
const plain=x=>x&&typeof x==='object'&&'target'in x?x.label:x,links=[...plan.hyperlinks],sheets={},formulas=[];
for(const[name,d]of Object.entries(data.sheets)){
 const s=wb.worksheets.add(name),last=9+d.rows.length,end=col(d.headers.length-1);s.showGridLines=false;s.tabColor='#344E40';
 s.getRange(`A1:${end}${last}`).format={font:{name:'Arial',size:10,color:'#28362D'},verticalAlignment:'center'};
 s.getRange('A2:H2').merge();s.getRange('A2').values=[[d.title]];s.getRange('A2:H2').format={font:{name:'Arial',size:16,bold:true,color:'#344E40'},rowHeight:32};
 s.getRange('A3:H3').merge();s.getRange('A3').values=[[d.note]];s.getRange('A3:H3').format={font:{name:'Arial',size:10,color:'#6D776F'},wrapText:true,rowHeight:40};
 s.getRange(`A9:${end}9`).values=[d.headers];s.getRange(`A10:${end}${last}`).values=d.rows.map(r=>r.map(plain));
 const t=s.tables.add(`A9:${end}${last}`,true,'Owner_Approved_Current_Folder_Updates');t.style='TableStyleLight1';t.showFilterButton=true;
 s.getRange(`A9:${end}9`).format={fill:'#344E40',font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},horizontalAlignment:'center',wrapText:true,rowHeight:44};
 s.getRange(`A10:${end}${last}`).format={wrapText:true,rowHeight:100};d.widths.forEach((w,j)=>s.getRangeByIndexes(0,j,last,1).format.columnWidth=w);
 d.rows.forEach((r,i)=>r.forEach((v,j)=>{if(v&&typeof v==='object'&&'target'in v){const c=col(j)+(i+10);links.push({sheet:name,cell:c,...v});s.getRange(c).format.font={name:'Arial',size:10,color:'#245F9E',underline:'single'};}}));
 for(const[c,label]of [['A4','Verified folder renames'],['C4','Dune Ripple folders'],['E4','Moonphases folders'],['H4','Fingerprint working approval']])s.getRange(c).values=[[label]];
 const fs=[['B4',`=COUNTA(B10:B${last})`,35],['D4',`=COUNTIF(A10:A${last},"Dune Ripple")`,22],['F4',`=COUNTIF(A10:A${last},"Moonphases")`,10]];
 for(const[c,f,expected]of fs){s.getRange(c).formulas=[[f]];formulas.push({sheet:name,cell:c,formula:f,expected});s.getRange(c).format={font:{name:'Arial',size:16,bold:true,color:'#344E40'},horizontalAlignment:'center'};}
 s.getRange('I4').values=[['Exact owner table and approval ledger']];s.getRange('I4').format.font={name:'Arial',size:10,color:'#245F9E',underline:'single'};
 links.push({sheet:name,cell:'I4',label:'Exact owner table and approval ledger',target:(await read('input-manifest.json')).fp_approval.path});
 s.freezePanes.freezeRows(9);s.freezePanes.freezeColumns(2);sheets[name]={...d,rows:d.rows.map(r=>r.map(plain))};
}
// Changing a source folder-count cell must update the new owner-facing count.
const s=wb.worksheets.getItem('Moonphases and Dune'),id=s.getRange('B10').values[0][0];
s.getRange('B10').values=[[null]];if(s.getRange('B4').values[0][0]!==34)throw Error('Folder-count dependency failed');
s.getRange('B10').values=[[id]];wb.recalculate();
for(const f of formulas)if(wb.worksheets.getItem(f.sheet).getRange(f.cell).values[0][0]!==f.expected)throw Error('Summary formula mismatch');
for(const[sn,c,value]of [['Master Catalogue','B4',186],['Master Catalogue','D4',112],['Master Catalogue','F4',186],['Photo Coverage','B5',22]])if(wb.worksheets.getItem(sn).getRange(c).values[0][0]!==value)throw Error('Unchanged catalogue-count dependency mismatch '+sn+'!'+c);
const previews=[];
for(const[sheetName,range,name]of plan.preview_ranges){const b=await wb.render({sheetName,range,scale:1.5,format:'png'}),p=path.join(h,'previews',name+'.png');await fs.writeFile(p,new Uint8Array(await b.arrayBuffer()));previews.push({sheet:sheetName,range,path:p});}
await(await SpreadsheetFile.exportXlsx(wb)).save(path.join(h,'master-workbook.pending'));
await fs.writeFile(path.join(h,'expected-edit.json'),JSON.stringify({sheets,hyperlinks:links,formulas},null,2));await fs.writeFile(path.join(h,'preview-manifest.json'),JSON.stringify(previews,null,2));
await fs.writeFile(path.join(h,'artifact-authoring-receipt.json'),JSON.stringify({status:'PASS',original_sheets:26,new_sheets:1,cell_changes:plan.cell_changes.length,dependent_folder_count_verified:true,temporary_source_restored:true,recalculated:true,current_options:186,current_components:112,individual_gaps:22,new_native_links:links.length-plan.hyperlinks.length},null,2));
console.log('EXPORTED_PENDING_NATIVE_VERIFICATION');
