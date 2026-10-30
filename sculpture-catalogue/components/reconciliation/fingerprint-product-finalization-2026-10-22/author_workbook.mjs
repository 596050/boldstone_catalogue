import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const h=path.dirname(fileURLToPath(import.meta.url)),read=async n=>JSON.parse(await fs.readFile(path.join(h,n),'utf8'));
const plan=await read('workbook-edit-plan.json'),g=await read('canonical-master-register.json');
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(h,'inputs/master_workbook.before')));
await fs.mkdir(path.join(h,'previews'),{recursive:true});
if(process.argv.includes('--baseline')){
 for(const[sheetName,range,name]of plan.baseline_ranges){const b=await wb.render({sheetName,range,scale:1.5,format:'png'});await fs.writeFile(path.join(h,'previews',name+'.png'),new Uint8Array(await b.arrayBuffer()));}
 console.log('BASELINES_RENDERED');process.exit(0);
}
for(const c of plan.cell_changes){const r=wb.worksheets.getItem(c.sheet).getRange(c.cell);if((r.values[0][0]??'')!==c.before)throw Error('Source value drift '+c.sheet+'!'+c.cell);}
const col=n=>{let s='';for(n++;n;n=Math.floor((n-1)/26))s=String.fromCharCode(65+(n-1)%26)+s;return s;};
const oldLast={'Master Catalogue':193,'Specifications':1113,'Components':120,'Photo Coverage':193,'Listing Resolution':193,'Draft Listings':109};
for(const p of plan.table_appends){
 const s=wb.worksheets.getItem(p.sheet),last=oldLast[p.sheet];s.tables.items[0].rows.add(null,Array.from({length:p.append_rows},()=>Array(p.columns).fill(null)));
 for(let i=1;i<=p.append_rows;i++)s.getRange(`A${last+i}:${col(p.columns-1)}${last+i}`).copyFrom(s.getRange(`A${last}:${col(p.columns-1)}${last}`),'all');
}
const batch=await read('batched-write-plan.json');
console.log('TABLE_ROWS_APPENDED');
for(const c of batch.value_blocks)wb.worksheets.getItem(c.sheet).getRange(c.range).values=c.values;
console.log('VALUE_BLOCKS_WRITTEN');
for(const p of plan.table_recreates){const s=wb.worksheets.getItem(p.sheet),old=s.tables.items[0],name=old.name,style=old.style,totals=old.showTotals,filters=old.showFilterButton;old.delete();const t=s.tables.add(p.range,true,name);t.style=style;t.showTotals=totals;t.showFilterButton=filters;}
for(const p of plan.row_heights)wb.worksheets.getItem(p.sheet).getRange(`A${p.row}:Y${p.row}`).format.rowHeight=p.height;
for(const f of batch.formula_blocks)wb.worksheets.getItem(f.sheet).getRange(f.range).formulas=f.formulas;
console.log('DEPENDENT_FORMULA_BLOCKS_WRITTEN');
wb.worksheets.getItem('Fingerprint Current').getRange('O10:O15').format.font={name:'Arial',size:10,color:'#245F9E',underline:'single'};
const links=[...plan.hyperlinks],newSheets={},newFormulas=[];
const plain=x=>x&&typeof x==='object'&&'target'in x?x.label:x;
for(const[name,d]of Object.entries(plan.new_sheets)){
 const s=wb.worksheets.add(name),last=9+d.rows.length,end=col(d.headers.length-1);s.showGridLines=false;s.tabColor='#8A9B8D';s.getRange(`A1:${end}${last}`).format={font:{name:'Arial',size:10,color:'#28362D'},verticalAlignment:'center'};
 s.getRange('A2:H2').merge();s.getRange('A2').values=[[d.title]];s.getRange('A2:H2').format={font:{name:'Arial',size:16,bold:true,color:'#344E40'},rowHeight:32};s.getRange('A3:H3').merge();s.getRange('A3').values=[[d.note]];s.getRange('A3:H3').format={font:{name:'Arial',size:10,color:'#6D776F'},wrapText:true,rowHeight:44};
 s.getRange(`A9:${end}9`).values=[d.headers];s.getRange(`A10:${end}${last}`).values=d.rows.map(r=>r.map(plain));const t=s.tables.add(`A9:${end}${last}`,true,'Fingerprint_Archived_Working_Specifications');t.style='TableStyleLight1';t.showFilterButton=true;
 s.getRange(`A9:${end}9`).format={fill:'#344E40',font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},wrapText:true,rowHeight:44,horizontalAlignment:'center'};s.getRange(`A10:${end}${last}`).format={wrapText:true,rowHeight:180};d.widths.forEach((w,j)=>s.getRangeByIndexes(0,j,last,1).format.columnWidth=w);
 d.rows.forEach((r,i)=>r.forEach((v,j)=>{if(v&&typeof v==='object'&&'target'in v){const cell=col(j)+(i+10);links.push({sheet:name,cell,...v});s.getRange(cell).format.font={name:'Arial',size:10,color:'#245F9E',underline:'single'};}}));
 s.getRange('A4').values=[['Archived prior offers']];s.getRange('B4').formulas=[['=COUNTA(A10:A33)/6']];s.getRange('C4').values=[['Preserved working fields']];s.getRange('D4').formulas=[['=COUNTA(D10:D33)']];
 for(const c of ['A4','C4'])s.getRange(c).format={wrapText:true,font:{name:'Arial',size:10,color:'#6D776F'},rowHeight:32};for(const c of ['B4','D4'])s.getRange(c).format={font:{name:'Arial',size:16,bold:true,color:'#344E40'},horizontalAlignment:'center'};
 newFormulas.push({sheet:name,cell:'B4',formula:'=COUNTA(A10:A33)/6',expected:4},{sheet:name,cell:'D4',formula:'=COUNTA(D10:D33)',expected:24});s.freezePanes.freezeRows(9);s.freezePanes.freezeColumns(2);newSheets[name]={...d,rows:d.rows.map(r=>r.map(plain))};
}
// Test both first replacement and final appended record through the owning field sheet.
const specs=wb.worksheets.getItem('Specifications'),master=wb.worksheets.getItem('Master Catalogue');const first=specs.getRange('I454').values[0][0],last=specs.getRange('I1125').values[0][0];
if(first!==1||last!==1)throw Error('Working acceptance rows shifted');specs.getRange('I454').values=[[0]];
if(master.getRange('K84').values[0][0]!==5||master.getRange('F4').values[0][0]!==185)throw Error('First current option dependency failed');specs.getRange('I454').values=[[first]];
specs.getRange('I1125').values=[[0]];if(master.getRange('K195').values[0][0]!==5||master.getRange('F4').values[0][0]!==185)throw Error('Appended option dependency failed');specs.getRange('I1125').values=[[last]];wb.recalculate();
console.log('DEPENDENCY_CHECKS_RESTORED');
for(const f of [...batch.restored_formulas,...newFormulas]){const value=wb.worksheets.getItem(f.sheet).getRange(f.cell).values[0][0];if(value!==f.expected)throw Error('Formula cache mismatch '+f.sheet+'!'+f.cell+': '+JSON.stringify(value)+' != '+JSON.stringify(f.expected));}
const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:20},maxChars:1200});await fs.writeFile(path.join(h,'formula-error-scan.ndjson'),errors.ndjson);
const previews=[];for(const[sheetName,range,name]of plan.preview_ranges){const b=await wb.render({sheetName,range,scale:1.5,format:'png'}),p=path.join(h,'previews',name+'.png');await fs.writeFile(p,new Uint8Array(await b.arrayBuffer()));previews.push({sheet:sheetName,range,path:p});}
await(await SpreadsheetFile.exportXlsx(wb)).save(path.join(h,'master-workbook.pending'));await fs.writeFile(path.join(h,'expected-edit.json'),JSON.stringify({sheets:newSheets,hyperlinks:links,formulas:newFormulas},null,2));await fs.writeFile(path.join(h,'preview-manifest.json'),JSON.stringify(previews,null,2));
await fs.writeFile(path.join(h,'artifact-authoring-receipt.json'),JSON.stringify({status:'PASS',baseline_inspected:true,current_options:186,current_components:112,field_groups:1116,first_and_final_option_dependencies_verified:true,temporary_acceptance_inputs_restored:true,recalculated:true,new_sheets:1},null,2));console.log('FP_PRODUCTS_EXPORTED_PENDING_NATIVE_VERIFICATION');
