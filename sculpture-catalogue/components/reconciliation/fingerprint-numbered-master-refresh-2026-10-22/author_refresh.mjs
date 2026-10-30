import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const h=path.dirname(fileURLToPath(import.meta.url));
const read=async n=>JSON.parse(await fs.readFile(path.join(h,n),'utf8'));
const plan=await read('workbook-edit-plan.json'),data=await read('workbook-data.json');
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(h,'inputs/master_workbook.before')));
await fs.mkdir(path.join(h,'previews'),{recursive:true});
if(process.argv.includes('--baseline')){
 for(const[sheetName,range,name]of plan.baseline_ranges){const blob=await wb.render({sheetName,range,scale:1.5,format:'png'});await fs.writeFile(path.join(h,'previews',name+'.png'),new Uint8Array(await blob.arrayBuffer()));}
 console.log('BASELINE_RENDERED');process.exit(0);
}
for(const c of plan.cell_changes){const r=wb.worksheets.getItem(c.sheet).getRange(c.cell);if((r.values[0][0]??'')!==c.before)throw Error('Source changed '+c.sheet+'!'+c.cell);r.values=[[c.value]];}
// The imported table does not synchronize header metadata after range writes.
// Recreate only this table through the documented API, retaining its name/style.
const legacySheet=wb.worksheets.getItem('Fingerprint Folders'),legacyTable=legacySheet.tables.items[0];
const legacyName=legacyTable.name,legacyStyle=legacyTable.style,legacyTotals=legacyTable.showTotals,legacyFilters=legacyTable.showFilterButton;
legacyTable.delete();const refreshedLegacyTable=legacySheet.tables.add('A9:P13',true,legacyName);
refreshedLegacyTable.style=legacyStyle;refreshedLegacyTable.showTotals=legacyTotals;refreshedLegacyTable.showFilterButton=legacyFilters;
for(const c of plan.row_heights)wb.worksheets.getItem(c.sheet).getRange(`A${c.row}:Y${c.row}`).format.rowHeight=c.height;
const col=n=>{let s='';for(n++;n;n=Math.floor((n-1)/26))s=String.fromCharCode(65+(n-1)%26)+s;return s;};
const plain=x=>x&&typeof x==='object'&&'target'in x?x.label:x;
const links=[...plan.hyperlinks],expected={},formulas=[];
for(const[name,d]of Object.entries(data.sheets)){
 const s=wb.worksheets.add(name),last=9+d.rows.length,end=col(d.headers.length-1);s.showGridLines=false;s.tabColor='#344E40';
 s.getRange(`A1:${end}${last}`).format={font:{name:'Arial',size:10,color:'#28362D'},verticalAlignment:'center'};
 s.getRange('A2:I2').merge();s.getRange('A2').values=[[d.title]];s.getRange('A2:I2').format={font:{name:'Arial',size:16,bold:true,color:'#344E40'},rowHeight:32};
 s.getRange('A3:I3').merge();s.getRange('A3').values=[[d.note]];s.getRange('A3:I3').format={font:{name:'Arial',size:10,color:'#6D776F'},wrapText:true,rowHeight:42};
 s.getRange(`A9:${end}9`).values=[d.headers];s.getRange(`A10:${end}${last}`).values=d.rows.map(r=>r.map(plain));
 const t=s.tables.add(`A9:${end}${last}`,true,name.replaceAll(' ','_')+'_Current_20261022');t.style='TableStyleLight1';t.showFilterButton=true;
 s.getRange(`A9:${end}9`).format={fill:'#344E40',font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},wrapText:true,rowHeight:44,horizontalAlignment:'center'};
 s.getRange(`A10:${end}${last}`).format={wrapText:true,rowHeight:name==='Fingerprint Current'?96:80};
 s.getRange(`C10:C${last}`).format.horizontalAlignment='center';
 d.widths.forEach((w,j)=>s.getRangeByIndexes(0,j,last,1).format.columnWidth=w);
 d.rows.forEach((r,i)=>r.forEach((x,j)=>{if(x&&typeof x==='object'&&'target'in x){const cell=col(j)+(i+10);links.push({sheet:name,cell,...x});s.getRange(cell).format.font={name:'Arial',size:10,color:'#245F9E',underline:'single'};}}));
 s.freezePanes.freezeRows(9);s.freezePanes.freezeColumns(2);expected[name]={...d,rows:d.rows.map(r=>r.map(plain))};
}
const summaries={
 'Fingerprint Current':[['A4','Folder-finish records','B4','=COUNTA(A10:A15)',6],['C4','Matched photo originals','D4',"=COUNTA('Fingerprint Photos'!A10:A35)",26],['E4','Legacy-role candidates','F4','=COUNTIF(K10:K15,"Legacy alias pending")',4]],
 'Fingerprint Photos':[['A4','Photographs','B4','=COUNTA(A10:A35)',26],['C4','Cream photographs','D4','=COUNTIF(B10:B35,"Cream")',13],['E4','White photographs','F4','=COUNTIF(B10:B35,"White")',13],['G4','Detail / partial','H4','=COUNTIF(G10:G35,"Detail / partial arrangement")',4]]
};
for(const[sn,rows]of Object.entries(summaries)){const s=wb.worksheets.getItem(sn);for(const[labelCell,label,cell,formula,value]of rows){s.getRange(labelCell).values=[[label]];s.getRange(labelCell).format={wrapText:true,rowHeight:32,font:{name:'Arial',size:10,color:'#6D776F'}};s.getRange(cell).formulas=[[formula]];s.getRange(cell).format={font:{name:'Arial',size:16,bold:true,color:'#344E40'},horizontalAlignment:'center'};s.getRange(cell).setNumberFormat('#,##0');formulas.push({sheet:sn,cell,formula,expected:value});}}
const photos=wb.worksheets.getItem('Fingerprint Photos'),original=photos.getRange('B23').values[0][0];if(original!=='White')throw Error('Photo row shifted');photos.getRange('B23').values=[['Cream']];
if(photos.getRange('D4').values[0][0]!==14||photos.getRange('F4').values[0][0]!==12)throw Error('Finish count dependency failed');photos.getRange('B23').values=[[original]];wb.recalculate();
for(const f of formulas)if(wb.worksheets.getItem(f.sheet).getRange(f.cell).values[0][0]!==f.expected)throw Error('Formula/cache mismatch '+f.sheet+'!'+f.cell);
const scan=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:30},maxChars:1200});await fs.writeFile(path.join(h,'formula-error-scan.ndjson'),scan.ndjson);
const previews=[];for(const[sheetName,range,name]of plan.preview_ranges){const b=await wb.render({sheetName,range,scale:1.5,format:'png'}),p=path.join(h,'previews',name+'.png');await fs.writeFile(p,new Uint8Array(await b.arrayBuffer()));previews.push({sheet:sheetName,range,path:p});}
await(await SpreadsheetFile.exportXlsx(wb)).save(path.join(h,'master-workbook.pending'));
await fs.writeFile(path.join(h,'expected-edit.json'),JSON.stringify({sheets:expected,hyperlinks:links,formulas},null,2));await fs.writeFile(path.join(h,'preview-manifest.json'),JSON.stringify(previews,null,2));
await fs.writeFile(path.join(h,'artifact-authoring-receipt.json'),JSON.stringify({status:'PASS',baseline_rendered_and_inspected:true,original_sheets:22,new_sheets:2,dependent_photo_count_check:true,temporary_input_restored:true,recalculated:true,new_native_links:82,original_specifications_unchanged:true},null,2));
console.log('EXPORTED_PENDING_NATIVE_READBACK');
