import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const here=path.dirname(fileURLToPath(import.meta.url));
const data=JSON.parse(await fs.readFile(path.join(here,'workbook-data.json'),'utf8'));
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(here,'inputs/master_workbook.before')));
const green='#344E40',ink='#28362D',muted='#6D776F';
const col=n=>{let s='';for(n++;n;n=Math.floor((n-1)/26))s=String.fromCharCode(65+(n-1)%26)+s;return s;};
const val=x=>x&&typeof x==='object'&&'target'in x?x.label:x??'';
const expected={},links=[],formulas=[],oldChanges=[];
for(const x of data.old_note_updates){const s=wb.worksheets.getItem(x.sheet);oldChanges.push({...x,before:s.getRange(x.cell).values[0][0]});s.getRange(x.cell).values=[[x.value]];}
for(const[name,d]of Object.entries(data.sheets)){
 const s=wb.worksheets.add(name),last=9+d.rows.length;s.showGridLines=false;s.tabColor=green;
 s.getRangeByIndexes(0,0,last,d.headers.length).format={font:{name:'Arial',size:10,color:ink},verticalAlignment:'center'};
 s.getRange('A2:F2').merge();s.getRange('A2').values=[[d.title]];s.getRange('A2:F2').format={font:{name:'Arial',size:16,bold:true,color:green},rowHeight:32};
 s.getRange('A3:H3').merge();s.getRange('A3').values=[[d.note]];s.getRange('A3:H3').format={font:{name:'Arial',size:10,color:muted},wrapText:true,rowHeight:40};
 s.getRangeByIndexes(8,0,1,d.headers.length).values=[d.headers];s.getRangeByIndexes(9,0,d.rows.length,d.headers.length).values=d.rows.map(r=>r.map(val));
 const t=s.tables.add(`A9:${col(d.headers.length-1)}${last}`,true,'Resolution_'+name.replaceAll(' ','_'));t.style='TableStyleLight1';t.showFilterButton=true;
 s.getRangeByIndexes(8,0,1,d.headers.length).format={fill:green,font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},horizontalAlignment:'center',wrapText:true,rowHeight:38};
 s.getRangeByIndexes(9,0,d.rows.length,d.headers.length).format.wrapText=true;d.widths.forEach((w,j)=>s.getRangeByIndexes(0,j,last,1).format.columnWidth=w);
 d.rows.forEach((r,i)=>{
  const lines=Math.max(...r.map((v,j)=>String(val(v)).split('\n').reduce((n,z)=>n+Math.max(1,Math.ceil(z.length/Math.max(10,d.widths[j]*.85))),0)));
  const h=Math.max(42,lines*13+10);if(h>409)throw new Error(`${name} row${i+10} requires${h}`);s.getRangeByIndexes(i+9,0,1,d.headers.length).format.rowHeight=h;
  r.forEach((v,j)=>{if(v&&typeof v==='object'&&'target'in v){const cell=col(j)+(i+10);links.push({sheet:name,cell,...v});s.getRange(cell).format.font={name:'Arial',size:10,color:'#245F9E',underline:'single'};}});
 });
 for(const c of d.editable)s.getRange(`${c}10:${c}${last}`).format.fill='#FFF3D6';
 s.freezePanes.freezeRows(9);s.freezePanes.freezeColumns(2);expected[name]={...d,rows:d.rows.map(r=>r.map(val)),first:10,last};
}
function summary(name,lc,label,vc,formula,result){const s=wb.worksheets.getItem(name);s.getRange(lc).values=[[label]];s.getRange(lc).format={font:{name:'Arial',size:10,color:muted},wrapText:true,rowHeight:34};s.getRange(vc).formulas=[[formula]];s.getRange(vc).format={font:{name:'Arial',size:16,bold:true,color:green},horizontalAlignment:'center'};s.getRange(vc).setNumberFormat('#,##0');formulas.push({sheet:name,cell:vc,formula,expected:result});}
const name='Listing Resolution';
summary(name,'A4','Individual-design source records','B4','=COUNTIF(D10:D193,1)',47);
summary(name,'C4','Conditional WC lookups','D4','=COUNTIF(E10:E193,1)',4);
summary(name,'E4','Cases reviewed','F4','=COUNTIF(F10:F193,1)',106);
summary(name,'A5','Retained set-only options','B5','=COUNTIF(C10:C193,"Set or arrangement association only")',33);
summary(name,'C5','Remaining review cases','D5','=F4-COUNTIFS(F10:F193,1,D10:D193,1)-D4',100);
summary(name,'E5','New individual-source options','F5','=COUNTIFS(F10:F193,1,D10:D193,1)',2);
summary('Listing Corrections','A4','Prepared copy-field proposals','B4','=COUNTA(A10:A33)',24);
summary('Listing Corrections','C4','Existing listing proposals','D4','=B4/6',4);
summary('Draft Listings','A4','Proposed individual draft SKUs','B4','=COUNTIF(C10:C109,"Individual option draft")',97);
summary('Draft Listings','C4','Custom pattern draft scopes','D4','=COUNTIF(C10:C109,"Custom / unlisted pattern scope")',3);
summary('Listing Actions','A4','Prepared requests','B4','=COUNTA(A10:A16)',7);
summary('Listing Actions','C4','Copy correction requests','D4','=COUNTIF(C10:C16,"Existing product copy correction draft")',4);
summary('Listing Actions','E4','SKU / visibility requests','F4','=B4-D4',3);
const resolution=wb.worksheets.getItem(name);
resolution.getRange('D10').values=[[0]];if(resolution.getRange('B4').values[0][0]!==46)throw new Error('Record-source summary did not follow its input: '+resolution.getRange('B4').values[0][0]);resolution.getRange('D10').values=[[1]];
const drafts=wb.worksheets.getItem('Draft Listings');drafts.getRange('C10').values=[['Custom / unlisted pattern scope']];if(drafts.getRange('B4').values[0][0]!==96||drafts.getRange('D4').values[0][0]!==4)throw new Error('Draft categories did not follow their input');drafts.getRange('C10').values=[['Individual option draft']];
wb.recalculate();
for(const f of formulas){const v=wb.worksheets.getItem(f.sheet).getRange(f.cell).values[0][0];if(v!==f.expected)throw new Error(`${f.sheet}!${f.cell}: ${v} != ${f.expected}`);}
const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:35},maxChars:2000});await fs.writeFile(path.join(here,'formula-error-scan.ndjson'),errors.ndjson);
await fs.mkdir(path.join(here,'previews'),{recursive:true});const previews=[];
for(const[sheetName,range,file]of [['Listing Resolution','A2:H13','01-resolution'],['Listing Resolution','G9:M13','02-native-working-tuples'],['Listing Corrections','A2:G13','03-corrections'],['Draft Listings','A2:H13','04-drafts'],['Listing Actions','A2:H13','05-actions'],['Listing Actions','H13:N16','06-quarantine-and-conditions'],['Listing Reconciliation','A2:H4','07-dated-source-note'],['Listing Issues','A2:H4','08-dated-issues-note']]){
 const b=await wb.render({sheetName,range,scale:1.5,format:'png'});const p=path.join(here,'previews',file+'.png');await fs.writeFile(p,new Uint8Array(await b.arrayBuffer()));previews.push({sheet:sheetName,range,path:p});
}
const out=await SpreadsheetFile.exportXlsx(wb);await out.save(path.join(here,'master-workbook.pending'));
await fs.writeFile(path.join(here,'expected-edit.json'),JSON.stringify({sheets:expected,hyperlinks:links,formulas,old_cell_changes:oldChanges},null,2));await fs.writeFile(path.join(here,'preview-manifest.json'),JSON.stringify(previews,null,2));
await fs.writeFile(path.join(here,'artifact-authoring-receipt.json'),JSON.stringify({status:'PASS',prior_sheets:16,new_sheets:4,old_data_rows_edited:0,dated_note_cells_edited:2,accepted_fields_edited:0,recalculated:true,source_and_draft_dependency_tests:true,temporary_values_restored:true},null,2));
console.log(JSON.stringify({status:'EXPORTED_PENDING_NATIVE_LINKS_AND_VERIFICATION',new_sheets:4,previews:previews.length}));
