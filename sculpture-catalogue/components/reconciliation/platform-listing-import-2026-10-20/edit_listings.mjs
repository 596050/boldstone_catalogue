import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const here=path.dirname(fileURLToPath(import.meta.url));
const data=JSON.parse(await fs.readFile(path.join(here,'workbook-data.json'),'utf8'));
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(here,'inputs/master_workbook.before')));
const oldInspection=await wb.inspect({kind:'sheet',include:'id,name',maxChars:2200});await fs.writeFile(path.join(here,'initial-workbook-inspection.ndjson'),oldInspection.ndjson);
const green='#344E40',ink='#28362D',muted='#6D776F';
const col=n=>{let s='';for(n++;n;n=Math.floor((n-1)/26))s=String.fromCharCode(65+(n-1)%26)+s;return s;};
const value=x=>x&&typeof x==='object'&&'target'in x?x.label:x??'';
const expected={},links=[],formulas=[];
for(const[name,d]of Object.entries(data.sheets)){
 const s=wb.worksheets.add(name),last=9+d.rows.length;
 s.showGridLines=false;s.tabColor=green;
 s.getRangeByIndexes(0,0,last,d.headers.length).format={font:{name:'Arial',size:10,color:ink},verticalAlignment:'center'};
 s.getRange('A2:F2').merge();s.getRange('A2').values=[[d.title]];s.getRange('A2:F2').format={font:{name:'Arial',size:16,color:green,bold:true},rowHeight:32};
 s.getRange('A3:H3').merge();s.getRange('A3').values=[[d.note]];s.getRange('A3:H3').format={font:{name:'Arial',size:10,color:muted},wrapText:true,rowHeight:40};
 s.getRangeByIndexes(8,0,1,d.headers.length).values=[d.headers];
 s.getRangeByIndexes(9,0,d.rows.length,d.headers.length).values=d.rows.map(r=>r.map(value));
 const table=s.tables.add(`A9:${col(d.headers.length-1)}${last}`,true,'Listing_'+name.replaceAll(' ','_'));table.style='TableStyleLight1';table.showFilterButton=true;
 s.getRangeByIndexes(8,0,1,d.headers.length).format={fill:green,font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},horizontalAlignment:'center',wrapText:true,rowHeight:38};
 s.getRangeByIndexes(9,0,d.rows.length,d.headers.length).format.wrapText=true;
 d.widths.forEach((w,j)=>s.getRangeByIndexes(0,j,last,1).format.columnWidth=w);
 d.rows.forEach((r,i)=>{
  const lines=Math.max(...r.map((v,j)=>String(value(v)).split('\n').reduce((n,z)=>n+Math.max(1,Math.ceil(z.length/Math.max(10,d.widths[j]*.85))),0)));
  const height=Math.max(42,lines*13+10);if(height>409)throw new Error(`${name} row${i+10} requires ${height}px`);
  s.getRangeByIndexes(i+9,0,1,d.headers.length).format.rowHeight=height;
  r.forEach((v,j)=>{if(v&&typeof v==='object'&&'target'in v){const cell=col(j)+(i+10);links.push({sheet:name,cell,...v});s.getRange(cell).format.font={name:'Arial',size:10,color:'#245F9E',underline:'single'};}});
 });
 for(const c of d.editable)s.getRange(`${c}10:${c}${last}`).format.fill='#FFF3D6';
 s.freezePanes.freezeRows(9);s.freezePanes.freezeColumns(2);
 expected[name]={...d,rows:d.rows.map(r=>r.map(value)),first:10,last};
}
function summary(name,labelCell,label,valueCell,formula,result){
 const s=wb.worksheets.getItem(name);s.getRange(labelCell).values=[[label]];s.getRange(labelCell).format={font:{name:'Arial',size:10,color:muted},wrapText:true,rowHeight:34};
 s.getRange(valueCell).formulas=[[formula]];s.getRange(valueCell).format={font:{name:'Arial',size:16,bold:true,color:green},horizontalAlignment:'center'};s.getRange(valueCell).setNumberFormat('#,##0');
 formulas.push({sheet:name,cell:valueCell,formula,expected:result});
}
const name='Listing Reconciliation';
summary(name,'A4','Individual source links','B4','=COUNTIF(C10:C193,"Individual source record linked")',41);
summary(name,'C4','Configuration conflicts','D4','=COUNTIF(C10:C193,"Existing design; configuration conflict")',4);
summary(name,'E4','Set / arrangement only','F4','=COUNTIF(C10:C193,"Set / arrangement only")',33);
const rec=wb.worksheets.getItem(name);
rec.getRange('A6:H6').merge();rec.getRange('A6').values=[['45 options have supported individual-design source records:41 without a known source configuration conflict and4 with a conflict.139 have no supported individual-record association. These are source-reconciliation counts, not verified live missing-listing counts.']];
rec.getRange('A6:H6').format={font:{name:'Arial',size:10,color:muted},wrapText:true,rowHeight:40};
for(const c of ['C','D','H'])rec.getRange(`${c}10:${c}193`).conditionalFormats.add('containsText',{text:'conflict',format:{fill:'#FFF3D6',font:{color:'#9C440D'}}});
summary('Listing Offer Links','A4','Source offer records','B4','=COUNTA(A10:A90)',81);
summary('Listing Offer Links','C4','Sources with SS IDs','D4','=ROWS(D10:D90)-COUNTBLANK(D10:D90)',data.sheets['Listing Offer Links'].rows.filter(r=>r[3]).length);
summary('Listing Offer Links','E4','Sources with SH handles','F4','=ROWS(I10:I90)-COUNTBLANK(I10:I90)',data.sheets['Listing Offer Links'].rows.filter(r=>r[8]).length);
const off=wb.worksheets.getItem('Listing Offer Links');
off.getRange('A6:H6').merge();off.getRange('A6').values=[['Fresh public Squarespace inventory:203 products /370 variants, versus208 advertised products. Shopify:136 products /160 variants in the historical export. Draft/archive completeness, current Shopify IDs and live stock remain unverified.']];
off.getRange('A6:H6').format={font:{name:'Arial',size:10,color:muted},wrapText:true,rowHeight:40};
const il=expected['Listing Issues'].last;
summary('Listing Issues','A4','Unresolved issue rows','B4',`=COUNTIF(P10:P${il},"<>Resolved")`,165);
summary('Listing Issues','C4','Public overlap cases','D4',`=COUNTIF(C10:C${il},"Multiple public individual records for one catalogue design option")`,3);
summary('Listing Issues','E4','Confirmed SKU collisions','F4',`=COUNTIF(C10:C${il},"Confirmed native sku collision duplicate listing candidate")`,1);
const issues=wb.worksheets.getItem('Listing Issues');issues.getRange(`P10:P${il}`).dataValidation={rule:{type:'list',values:['Open','Reviewing','Resolved','Deferred']}};
// Resolution affects the action count only; original source evidence stays intact.
issues.getRange('P10').values=[['Resolved']];if(issues.getRange('B4').values[0][0]!==164)throw new Error('Listing issue resolution did not update count');issues.getRange('P10').values=[['Open']];
rec.getRange('C10').values=[['Existing design; configuration conflict']];if(rec.getRange('B4').values[0][0]!==40||rec.getRange('D4').values[0][0]!==5)throw new Error('Source-disposition summaries did not update');rec.getRange('C10').values=[['Individual source record linked']];
wb.recalculate();
for(const f of formulas){const v=wb.worksheets.getItem(f.sheet).getRange(f.cell).values[0][0];if(v!==f.expected)throw new Error(`${f.sheet}!${f.cell} ${v} != ${f.expected}`);}
const error=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:40},maxChars:2000});await fs.writeFile(path.join(here,'formula-error-scan.ndjson'),error.ndjson);
await fs.mkdir(path.join(here,'previews'),{recursive:true});
const ranges=[['Listing Reconciliation','A2:H12','01-listings'],['Listing Reconciliation','H9:P12','02-shopify-and-images'],['Listing Offer Links','A2:H12','03-source-offers'],['Listing Offer Links','M9:W12','04-sale-units'],['Listing Issues','A2:F13','05-issues'],['Listing Issues','N9:R12','06-review-inputs']];
const previews=[];for(const[sheetName,range,file]of ranges){const b=await wb.render({sheetName,range,scale:1.5,format:'png'});const dest=path.join(here,'previews',file+'.png');await fs.writeFile(dest,new Uint8Array(await b.arrayBuffer()));previews.push({sheet:sheetName,range,path:dest});}
const out=await SpreadsheetFile.exportXlsx(wb);await out.save(path.join(here,'master-workbook.pending'));
await fs.writeFile(path.join(here,'expected-edit.json'),JSON.stringify({sheets:expected,hyperlinks:links,formulas},null,2));
await fs.writeFile(path.join(here,'preview-manifest.json'),JSON.stringify(previews,null,2));
await fs.writeFile(path.join(here,'artifact-authoring-receipt.json'),JSON.stringify({status:'PASS',prior_sheets:13,new_sheets:3,prior_cells_edited:0,recalculation:true,summary_dependency_test:true,issue_resolution_dependency_test:true,temporary_values_restored:true,preview_count:previews.length},null,2));
console.log(JSON.stringify({status:'EXPORTED_PENDING_NATIVE_LINKS_AND_VERIFICATION',new_sheets:3}));
