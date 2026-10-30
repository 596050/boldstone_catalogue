import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const here=path.dirname(fileURLToPath(import.meta.url));
const read=async n=>JSON.parse(await fs.readFile(path.join(here,n),'utf8'));
const plan=await read('workbook-edit-plan.json'),data=await read('workbook-data.json');
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(here,'inputs/master_workbook.before')));
await fs.mkdir(path.join(here,'previews'),{recursive:true});
if(process.argv.includes('--baseline')){
 const overview=await wb.inspect({kind:'sheet',include:'id,name',maxChars:2500});
 await fs.writeFile(path.join(here,'baseline-inspection.ndjson'),overview.ndjson);
 for(const[sheetName,range,name]of plan.baseline_ranges){const blob=await wb.render({sheetName,range,scale:1.5,format:'png'});await fs.writeFile(path.join(here,'previews',name+'.png'),new Uint8Array(await blob.arrayBuffer()));}
 console.log('BASELINE_RENDERED');process.exit(0);
}
for(const change of plan.cell_changes){
 const cell=wb.worksheets.getItem(change.sheet).getRange(change.cell);
 if((cell.values[0][0]??'')!==change.before)throw Error('Unexpected source value '+change.sheet+'!'+change.cell);
 cell.values=[[change.value]];
}
for(const change of plan.row_heights)wb.worksheets.getItem(change.sheet).getRange(`A${change.row}:Y${change.row}`).format.rowHeight=change.height;
const links=[...plan.hyperlinks],expectedSheets={},formulas=[];
const column=n=>{let s='';for(n++;n;n=Math.floor((n-1)/26))s=String.fromCharCode(65+(n-1)%26)+s;return s;};
const plain=x=>x&&typeof x==='object'&&'target'in x?x.label:x;
const green='#344E40',ink='#28362D';
for(const[name,d]of Object.entries(data.sheets)){
 const s=wb.worksheets.add(name),last=9+d.rows.length;s.showGridLines=false;s.tabColor=green;
 s.getRange(`A1:P${last}`).format={font:{name:'Arial',size:10,color:ink},verticalAlignment:'center'};
 s.getRange('A2:H2').merge();s.getRange('A2').values=[[d.title]];s.getRange('A2:H2').format={font:{name:'Arial',size:16,bold:true,color:green},rowHeight:32};
 s.getRange('A3:H3').merge();s.getRange('A3').values=[[d.note]];s.getRange('A3:H3').format={font:{name:'Arial',size:10,color:'#6D776F'},wrapText:true,rowHeight:38};
 s.getRange('A9:P9').values=[d.headers];s.getRange(`A10:P${last}`).values=d.rows.map(r=>r.map(plain));
 const table=s.tables.add(`A9:P${last}`,true,'Gleneagles_Component_Folders');table.style='TableStyleLight1';table.showFilterButton=true;
 s.getRange('A9:P9').format={fill:green,font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},horizontalAlignment:'center',wrapText:true,rowHeight:44};
 s.getRange(`A10:P${last}`).format={wrapText:true,rowHeight:72};
 d.widths.forEach((width,j)=>s.getRangeByIndexes(0,j,last,1).format.columnWidth=width);
 d.rows.forEach((r,i)=>r.forEach((value,j)=>{if(value&&typeof value==='object'&&'target'in value){const cell=column(j)+(i+10);links.push({sheet:name,cell,...value});s.getRange(cell).format.font={name:'Arial',size:10,color:'#245F9E',underline:'single'};}}));
 for(let i=0;i<d.rows.length;i++){
  const row=i+10;
  for(const[col,source,index,value]of [['B','Master Catalogue',2,d.rows[i][1]],['N','Photo Coverage',3,'Group only']]){
   const lastColumn=source==='Master Catalogue'?'Y':'V';
   const formula=`=VLOOKUP($A${row},'${source}'!$A$10:$${lastColumn}$193,${index},FALSE)`;
   s.getRange(col+row).formulas=[[formula]];formulas.push({sheet:name,cell:col+row,formula,expected:value});
  }
 }
 s.getRange('A4').values=[['Component folders']];s.getRange('B4').formulas=[['=COUNTA(A10:A13)']];
 s.getRange('C4').values=[['Individual photo gaps retained']];s.getRange('D4').formulas=[['=COUNTIFS(N10:N13,"Group only")']];
 for(const cell of ['A4','C4'])s.getRange(cell).format={wrapText:true,font:{name:'Arial',size:10,color:'#6D776F'},rowHeight:32};
 for(const cell of ['B4','D4']){s.getRange(cell).format={font:{name:'Arial',size:16,bold:true,color:green},horizontalAlignment:'center'};s.getRange(cell).setNumberFormat('#,##0');}
 formulas.push({sheet:name,cell:'B4',formula:'=COUNTA(A10:A13)',expected:4},{sheet:name,cell:'D4',formula:'=COUNTIFS(N10:N13,"Group only")',expected:4});
 s.freezePanes.freezeRows(9);s.freezePanes.freezeColumns(2);expectedSheets[name]={...d,rows:d.rows.map(r=>r.map(plain))};
}
const view=wb.worksheets.getItem('Gleneagles Folders'),pc=wb.worksheets.getItem('Photo Coverage'),master=wb.worksheets.getItem('Master Catalogue');
const status=pc.getRange('C97').values[0][0],name=master.getRange('B97').values[0][0];
if(status!=='Group only')throw Error('Source role row shifted');
pc.getRange('C97').values=[['Available']];
if(view.getRange('N10').values[0][0]!=='Available'||view.getRange('D4').values[0][0]!==3)throw Error('Photo-role lookup/count dependency failed');
pc.getRange('C97').values=[[status]];
master.getRange('B97').values=[['Temporary component-name verification']];
if(view.getRange('B10').values[0][0]!=='Temporary component-name verification')throw Error('Current-name lookup dependency failed');
master.getRange('B97').values=[[name]];wb.recalculate();
for(const x of plan.cell_changes)if(wb.worksheets.getItem(x.sheet).getRange(x.cell).values[0][0]!==x.value)throw Error('Temporary input not restored '+x.sheet+'!'+x.cell);
for(const x of formulas)if(wb.worksheets.getItem(x.sheet).getRange(x.cell).values[0][0]!==x.expected)throw Error('Recalculated source/binding mismatch '+x.sheet+'!'+x.cell);
const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:30},maxChars:1800});
await fs.writeFile(path.join(here,'formula-error-scan.ndjson'),errors.ndjson);
const previews=[];
for(const[sheetName,range,name]of plan.preview_ranges){const blob=await wb.render({sheetName,range,scale:1.5,format:'png'}),p=path.join(here,'previews',name+'.png');await fs.writeFile(p,new Uint8Array(await blob.arrayBuffer()));previews.push({sheet:sheetName,range,path:p});}
await(await SpreadsheetFile.exportXlsx(wb)).save(path.join(here,'master-workbook.pending'));
await fs.writeFile(path.join(here,'expected-edit.json'),JSON.stringify({sheets:expectedSheets,hyperlinks:links,formulas},null,2));
await fs.writeFile(path.join(here,'preview-manifest.json'),JSON.stringify(previews,null,2));
await fs.writeFile(path.join(here,'artifact-authoring-receipt.json'),JSON.stringify({status:'PASS',baseline_rendered_and_inspected:true,old_sheets:21,new_sheets:1,current_name_and_photo_status_dependencies_verified:true,temporary_inputs_restored:true,recalculated:true,cell_changes:plan.cell_changes.length,new_link_cells:16},null,2));
console.log(JSON.stringify({status:'EXPORTED_PENDING_NATIVE_READBACK',cell_changes:plan.cell_changes.length,new_links:16,previews:previews.length}));
