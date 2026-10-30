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
const plain=x=>x&&typeof x==='object'&&'target'in x?x.label:x,links=[...plan.hyperlinks],sheets={},newFormulas=[];
const cellIndex=c=>{const m=c.match(/^([A-Z]+)(\d+)$/);let j=0;for(const v of m[1])j=j*26+v.charCodeAt(0)-64;return[Number(m[2])-1,j-1];};
const readValues=items=>{const bounds=new Map(),values=new Map();for(const x of items){const[r,c]=cellIndex(x.cell),old=bounds.get(x.sheet)||[0,0];bounds.set(x.sheet,[Math.max(old[0],r+1),Math.max(old[1],c+1)]);}for(const[sn,[nr,nc]]of bounds)values.set(sn,wb.worksheets.getItem(sn).getRangeByIndexes(0,0,nr,nc).values);return x=>{const[r,c]=cellIndex(x.cell);return values.get(x.sheet)[r]?.[c];};};
const beforeValue=readValues(plan.cell_changes);
for(const c of plan.cell_changes)if((beforeValue(c)??'')!==c.before)throw Error('Source value drift '+c.sheet+'!'+c.cell);
for(const p of data.table_appends){
 const s=wb.worksheets.getItem(p.sheet),last=p.old_last_row,end=col(p.columns-1);s.tables.items[0].rows.add(null,p.rows.map(r=>r.map(plain)));
 for(let i=0;i<p.rows.length;i++)s.getRange(`A${last+i+1}:${end}${last+i+1}`).copyFrom(s.getRange(`A${last}:${end}${last}`),'all');
 s.getRange(`A${last+1}:${end}${last+p.rows.length}`).values=p.rows.map(r=>r.map(plain));
 p.rows.forEach((r,i)=>r.forEach((v,j)=>{if(v&&typeof v==='object'&&'target'in v)links.push({sheet:p.sheet,cell:col(j)+(last+i+1),...v});}));
}
for(const c of plan.value_blocks)wb.worksheets.getItem(c.sheet).getRange(c.range).values=c.values;
for(const c of plan.row_heights)wb.worksheets.getItem(c.sheet).getRange(`A${c.row}:Y${c.row}`).format.rowHeight=c.height;
for(const f of plan.formula_changes)wb.worksheets.getItem(f.sheet).getRange(f.cell).formulas=[[f.formula]];
for(const[name,d]of Object.entries(data.new_sheets)){
 const s=wb.worksheets.add(name),last=9+d.rows.length,end=col(d.headers.length-1);s.showGridLines=false;s.tabColor='#344E40';
 s.getRange(`A1:${end}${last}`).format={font:{name:'Arial',size:10,color:'#28362D'},verticalAlignment:'center'};
 s.getRange('A2:H2').merge();s.getRange('A2').values=[[d.title]];s.getRange('A2:H2').format={font:{name:'Arial',size:16,bold:true,color:'#344E40'},rowHeight:32};
 s.getRange('A3:H3').merge();s.getRange('A3').values=[[d.note]];s.getRange('A3:H3').format={font:{name:'Arial',size:10,color:'#6D776F'},wrapText:true,rowHeight:44};
 s.getRange(`A9:${end}9`).values=[d.headers];s.getRange(`A10:${end}${last}`).values=d.rows.map(r=>r.map(plain));
 const t=s.tables.add(`A9:${end}${last}`,true,'Current_Individual_Selling_Details');t.style='TableStyleLight1';t.showFilterButton=true;
 s.getRange(`A9:${end}9`).format={fill:'#344E40',font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},horizontalAlignment:'center',wrapText:true,rowHeight:44};
 s.getRange(`A10:${end}${last}`).format={wrapText:true,rowHeight:144};d.widths.forEach((w,j)=>s.getRangeByIndexes(0,j,last,1).format.columnWidth=w);
 d.rows.forEach((r,i)=>r.forEach((v,j)=>{if(v&&typeof v==='object'&&'target'in v){const c=col(j)+(i+10);links.push({sheet:name,cell:c,...v});s.getRange(c).format.font={name:'Arial',size:10,color:'#245F9E',underline:'single'};}}));
 const lookup=[],lead=[];
 for(let i=0;i<d.rows.length;i++){
  const row=i+10,price=`=VLOOKUP($A${row},'Master Catalogue'!$A$10:$Y$195,9,FALSE)`,availability=`=VLOOKUP($A${row},'Master Catalogue'!$A$10:$Y$195,10,FALSE)`,lf=`=IF(ISNUMBER(SEARCH("1–2 weeks",D${row})),"1–2 weeks",IF(ISNUMBER(SEARCH("1 week",D${row})),"1 week","Check source policy"))`;
  lookup.push([price,availability]);lead.push([lf]);newFormulas.push({sheet:name,cell:'C'+row,formula:price,expected:d.rows[i][2]},{sheet:name,cell:'D'+row,formula:availability,expected:d.rows[i][3]},{sheet:name,cell:'G'+row,formula:lf,expected:d.rows[i][6]});
 }
 s.getRange(`C10:D${last}`).formulas=lookup;s.getRange(`G10:G${last}`).formulas=lead;
 for(const[c,v]of [['A4','Current options'],['C4','Working price estimates'],['E4','1–2 week policy'],['G4','One-week exception']])s.getRange(c).values=[[v]];
 for(const[c,f,expected]of [['B4','=COUNTA(A10:A195)',186],['D4','=COUNTIF(E10:E195,"estimate")',185],['F4','=COUNTIF(G10:G195,"1–2 weeks")',185],['H4','=COUNTIF(G10:G195,"1 week")',1]]){
  s.getRange(c).formulas=[[f]];s.getRange(c).format={font:{name:'Arial',size:16,bold:true,color:'#344E40'},horizontalAlignment:'center'};newFormulas.push({sheet:name,cell:c,formula:f,expected});
 }
 s.freezePanes.freezeRows(9);s.freezePanes.freezeColumns(2);sheets[name]={...d,rows:d.rows.map(r=>r.map(plain))};
}
console.log('CURRENT_FIELDS_AND_LINKED_SELLING_VIEW_WRITTEN');
// Verify both linked views follow their owning field rather than frozen copies.
const spec=wb.worksheets.getItem('Specifications'),master=wb.worksheets.getItem('Master Catalogue'),sell=wb.worksheets.getItem('Selling Details');
const price=spec.getRange('D14').values[0][0],availability=spec.getRange('D15').values[0][0];
spec.getRange('D14').values=[['Temporary linked-price check']];if(master.getRange('I10').values[0][0]!=='Temporary linked-price check'||sell.getRange('C10').values[0][0]!=='Temporary linked-price check')throw Error('Price ownership dependency failed');spec.getRange('D14').values=[[price]];
spec.getRange('D15').values=[['Temporary policy check']];if(sell.getRange('D10').values[0][0]!=='Temporary policy check'||sell.getRange('F4').values[0][0]!==184)throw Error('Availability policy dependency failed');spec.getRange('D15').values=[[availability]];wb.recalculate();
const finalChecks=[...plan.formula_changes,...plan.formula_cache_changes,...newFormulas],afterValue=readValues(finalChecks);
for(const f of finalChecks)if(afterValue(f)!==f.expected)throw Error('Formula/cache mismatch '+f.sheet+'!'+f.cell);
console.log('OWNING_FIELD_DEPENDENCIES_VERIFIED_AND_RESTORED');
const previews=[];
for(const[sheetName,range,name]of plan.preview_ranges){const b=await wb.render({sheetName,range,scale:1.5,format:'png'}),p=path.join(h,'previews',name+'.png');await fs.writeFile(p,new Uint8Array(await b.arrayBuffer()));previews.push({sheet:sheetName,range,path:p});}
await(await SpreadsheetFile.exportXlsx(wb)).save(path.join(h,'master-workbook.pending'));
await fs.writeFile(path.join(h,'expected-edit.json'),JSON.stringify({sheets,hyperlinks:links,formulas:newFormulas},null,2));await fs.writeFile(path.join(h,'preview-manifest.json'),JSON.stringify(previews,null,2));
await fs.writeFile(path.join(h,'artifact-authoring-receipt.json'),JSON.stringify({status:'PASS',original_sheets:27,new_sheets:1,cell_changes:plan.cell_changes.length,owning_specification_dependencies_verified:true,temporary_inputs_restored:true,recalculated:true,estimated_price_options:185,specific_owner_exception:1,current_options:186,current_components:112,individual_gaps:19},null,2));console.log('FOLLOWUP_EXPORTED_PENDING_NATIVE_VERIFICATION');
