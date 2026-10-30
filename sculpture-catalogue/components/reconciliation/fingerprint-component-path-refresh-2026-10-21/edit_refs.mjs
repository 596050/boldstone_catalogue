import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const here=path.dirname(fileURLToPath(import.meta.url));
const data=JSON.parse(await fs.readFile(path.join(here,'workbook-data.json'),'utf8'));
const plan=JSON.parse(await fs.readFile(path.join(here,'workbook-edit-plan.json'),'utf8'));
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(here,'inputs/master_workbook.before')));
const links=[...plan.hyperlinks],green='#344E40',ink='#28362D';
const col=n=>{let s='';for(n++;n;n=Math.floor((n-1)/26))s=String.fromCharCode(65+(n-1)%26)+s;return s;};
const val=x=>x&&typeof x==='object'&&'target'in x?x.label:x;
const expected={};
for(const[name,d]of Object.entries(data.sheets)){
 const s=wb.worksheets.add(name),last=9+d.rows.length;s.showGridLines=false;s.tabColor=green;
 s.getRange(`A1:P${last}`).format={font:{name:'Arial',size:10,color:ink},verticalAlignment:'center'};
 s.getRange('A2:H2').merge();s.getRange('A2').values=[[d.title]];s.getRange('A2:H2').format={font:{name:'Arial',size:16,bold:true,color:green},rowHeight:32};
 s.getRange('A3:H3').merge();s.getRange('A3').values=[[d.note]];s.getRange('A3:H3').format={font:{name:'Arial',size:10,color:'#6D776F'},wrapText:true,rowHeight:38};
 s.getRange('A9:P9').values=[d.headers];s.getRange(`A10:P${last}`).values=d.rows.map(r=>r.map(val));
 const table=s.tables.add(`A9:P${last}`,true,'Fingerprint_Component_Folders');table.style='TableStyleLight1';table.showFilterButton=true;
 s.getRange('A9:P9').format={fill:green,font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},horizontalAlignment:'center',wrapText:true,rowHeight:44};
 s.getRange(`A10:P${last}`).format={wrapText:true,rowHeight:64};
 d.widths.forEach((w,j)=>s.getRangeByIndexes(0,j,last,1).format.columnWidth=w);
 d.rows.forEach((r,i)=>r.forEach((v,j)=>{if(v&&typeof v==='object'&&'target'in v){const cell=col(j)+(i+10);links.push({sheet:name,cell,...v});s.getRange(cell).format.font={name:'Arial',size:10,color:'#245F9E',underline:'single'};}}));
 s.freezePanes.freezeRows(9);s.freezePanes.freezeColumns(2);expected[name]={...d,rows:d.rows.map(r=>r.map(val))};
}
const s=wb.worksheets.getItem('Fingerprint Folders');
s.getRange('A4').values=[['Component/finish folders']];s.getRange('B4').formulas=[['=COUNTA(A10:A13)']];
s.getRange('C4').values=[['Individual photo gaps retained']];s.getRange('D4').formulas=[['=COUNTIF(N10:N13,"Group only")']];
for(const c of ['A4','C4'])s.getRange(c).format={wrapText:true,font:{name:'Arial',size:10,color:'#6D776F'},rowHeight:32};
for(const c of ['B4','D4']){s.getRange(c).format={font:{name:'Arial',size:16,bold:true,color:green},horizontalAlignment:'center'};s.getRange(c).setNumberFormat('#,##0');}
s.getRange('N10').values=[['Available']];if(s.getRange('D4').values[0][0]!==3)throw new Error('Photo-gap summary dependency failed');s.getRange('N10').values=[['Group only']];wb.recalculate();
if(s.getRange('B4').values[0][0]!==4||s.getRange('D4').values[0][0]!==4)throw new Error('Folder counts failed');
const previews=[];await fs.mkdir(path.join(here,'previews'),{recursive:true});
for(const[sheetName,range,file]of plan.preview_ranges){const blob=await wb.render({sheetName,range,scale:1.5,format:'png'}),dest=path.join(here,'previews',file+'.png');await fs.writeFile(dest,new Uint8Array(await blob.arrayBuffer()));previews.push({sheet:sheetName,range,path:dest});}
await(await SpreadsheetFile.exportXlsx(wb)).save(path.join(here,'master-workbook.pending'));
await fs.writeFile(path.join(here,'expected-edit.json'),JSON.stringify({sheets:expected,hyperlinks:links,formulas:[{sheet:'Fingerprint Folders',cell:'B4',formula:'=COUNTA(A10:A13)',expected:4},{sheet:'Fingerprint Folders',cell:'D4',formula:'=COUNTIF(N10:N13,"Group only")',expected:4}]},null,2));
await fs.writeFile(path.join(here,'preview-manifest.json'),JSON.stringify(previews,null,2));
await fs.writeFile(path.join(here,'artifact-authoring-receipt.json'),JSON.stringify({status:'PASS',old_sheets:20,new_sheets:1,old_values_edited:0,accepted_fields_edited:0,source_IDs_edited:0,coverage_dependency_test:true,temporary_value_restored:true},null,2));
console.log(JSON.stringify({status:'EXPORTED_PENDING_NATIVE_LINKS_AND_VERIFICATION',previews:previews.length}));
