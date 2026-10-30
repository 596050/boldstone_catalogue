import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {FileBlob, SpreadsheetFile} from '@oai/artifact-tool';

const h=path.dirname(fileURLToPath(import.meta.url));
const plans=JSON.parse(await fs.readFile(path.join(h,'workbook-edit-plan.json'),'utf8')).plans;
const overlay=JSON.parse(await fs.readFile(path.join(h,'current-image-overlay.json'),'utf8'));
const manifest=JSON.parse(await fs.readFile(path.join(h,'input-manifest.json'),'utf8'));
await fs.mkdir(path.join(h,'previews'),{recursive:true});
const receipts=[];
const refinement=process.argv.includes('--refine-navigation-labels');
const only=process.argv.find(x=>x.startsWith('--only='))?.slice('--only='.length);
const hyperlink=(url,label)=>`=HYPERLINK("${url.replaceAll('"','""')}","${label.replaceAll('"','""')}")`;
for (const p of plans) {
  if(only&&p.key!==only)continue;
  if(refinement&&!p.edits.some(e=>e.navigation_refinement))continue;
  const digest=crypto.createHash('sha256').update(await fs.readFile(p.source)).digest('hex');
  if(digest!==p.source_sha256)throw new Error('Input hash drift');
  const raw=path.join(h,p.key+'-artifact-authored.xlsx');
  console.log(JSON.stringify({key:p.key,stage:'import'}));
  const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(refinement?raw:p.source));
  console.log(JSON.stringify({key:p.key,stage:'table_extensions'}));
  for(const t of refinement?[]:(p.table_expansions||[])){
    const s=wb.worksheets.getItem(t.sheet);
    const existing=s.tables.items.find(x=>x.name===t.name);
    if(!existing)throw new Error('Declared source table missing');
    const range=s.getRange(t.range),savedValues=range.values,savedFormulas=range.formulas;
    existing.delete();range.values=savedValues;
    const firstRow=Number(t.range.match(/\d+/)[0]);
    const columnName=index=>{let s='';for(let n=index+1;n>0;n=Math.floor((n-1)/26))s=String.fromCharCode(65+(n-1)%26)+s;return s};
    for(let col=0;col<(savedFormulas[0]?.length||0);col++){
      for(let i=0;i<savedFormulas.length;){
        if(!savedFormulas[i][col]){i++;continue}
        let j=i+1;while(j<savedFormulas.length&&savedFormulas[j][col])j++;
        const label=columnName(col);
        s.getRange(`${label}${firstRow+i}:${label}${firstRow+j-1}`).formulas=savedFormulas.slice(i,j).map(r=>[r[col]]);
        i=j;
      }
    }
    s.tables.add(t.range,true,t.name);
    console.log(JSON.stringify({key:p.key,extended_table:t.name}));
  }
  for(const f of refinement?[]:(p.row_formats||[])){
    const s=wb.worksheets.getItem(f.sheet);
    s.getRange(`A${f.first}:AH${f.last}`).format.rowHeight=f.height;
    s.getRange(`A${f.first}:AH${f.last}`).format.wrapText=true;
  }
  // Batch consecutive edits within a column and operation type.
  console.log(JSON.stringify({key:p.key,stage:'declared_edits'}));
  const groups=new Map();
  for(const e of p.edits){
    if(refinement&&!e.navigation_refinement)continue;
    const col=e.cell.match(/^[A-Z]+/)[0],row=Number(e.cell.match(/\d+$/)[0]);
    const mode=e.kind==='value'?'value':'formula',key=JSON.stringify([e.sheet,col,mode]);
    if(!groups.has(key))groups.set(key,[]);
    groups.get(key).push({...e,row,col,mode});
  }
  for (const entries of groups.values()) {
    entries.sort((a,b)=>a.row-b.row);
    for(let i=0;i<entries.length;){
      let j=i+1;while(j<entries.length&&entries[j].row===entries[j-1].row+1)j++;
      const block=entries.slice(i,j),first=block[0],last=block.at(-1);
      const range=wb.worksheets.getItem(first.sheet).getRange(`${first.cell}:${last.cell}`);
      if(first.mode==='value')range.values=block.map(e=>[e.value]);
      else range.formulas=block.map(e=>[e.formula]);
      i=j;
    }
  }
  if(p.new_sheet&&!refinement){
    const rows=JSON.parse(await fs.readFile(path.join(h,'paver-evidence-rows.json'),'utf8'));
    const s=wb.worksheets.add(p.new_sheet),end=rows.length+7;
    s.showGridLines=false;s.tabColor='#344b59';s.getRange(`A1:G${end}`).format.font={name:'Arial',size:10};
    s.getRange('A2:G2').merge();s.getRange('A2').values=[['Two Brown paver working options']];s.getRange('A2').format.font={name:'Arial',size:18,bold:true,color:'#243847'};s.getRange('A2:G2').format.rowHeight=30;
    s.getRange('A3:G3').merge();s.getRange('A3').values=[['Owner-requested separate working options:28 October2026. Native folder/file IDs preserved. Visual CRS2/CRS1 correspondence only; physical mould, material and platform SKU remain unverified. Audited images are source references; Primary, Listing and Advertising remain unselected.']];s.getRange('A3:G3').format.wrapText=true;s.getRange('A3:G3').format.rowHeight=46;
    s.getRange('A4').values=[['Active options']];s.getRange('B4').formulas=[[p.key==='core_workbook'?"='Master Catalogue'!B4":"='Overview'!B7"]];
    s.getRange('C4').values=[['Retained records']];s.getRange('D4').values=[[191]];s.getRange('E4').values=[['New working options']];s.getRange('F4').values=[[2]];
    s.getRange('A5').values=[['Active working fields']];s.getRange('B5').formulas=[['=B4*6']];s.getRange('C5').values=[['Original assertions']];s.getRange('D5').values=[[1668]];
    s.getRange('A4:G5').format.rowHeight=28;
    s.getRange('A7:G7').values=[['Record type','Record ID','Identity / field','Value / target','Image','Folder','Qualification']];
    s.getRange(`A8:G${end}`).values=rows.map(r=>[r.kind,r.id,r.name,r.value,r.image?'Image':'',r.folder?'Folder':'',r.qualification]);
    s.getRange(`E8:E${end}`).formulas=rows.map(r=>[hyperlink(r.image,'Image')]);
    s.getRange(`F8:F${end}`).formulas=rows.map(r=>[hyperlink(r.folder,'Folder')]);
    s.getRange('A7:G7').format={fill:'#344b59',font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},rowHeight:34,wrapText:true};s.getRange(`A8:G${end}`).format.wrapText=true;s.getRange(`A8:G${end}`).format.rowHeight=94;
    for(const[col,width]of [['A',24],['B',46],['C',48],['D',78],['E',15],['F',15],['G',100]])s.getRange(`${col}:${col}`).format.columnWidth=width;
    s.getRange(`E8:F${end}`).format.font={name:'Arial',size:10,color:'#17617D',underline:'single'};
    s.freezePanes.freezeRows(7);s.freezePanes.freezeColumns(1);s.tables.add(`A7:G${end}`,true,'OwnerBrownPaverWorkingOptions');
  }
  wb.recalculate();
  console.log(JSON.stringify({key:p.key,stage:'boundary_checks'}));
  const boundaryChecks=[];
  if(!refinement&&p.key==='core_workbook'){
    const s=wb.worksheets.getItem('Specifications'),master=wb.worksheets.getItem('Master Catalogue');
    const cell=s.getRange('D1144'),before=cell.values[0][0];
    cell.values=[['']];wb.recalculate();
    if(master.getRange('K199').values[0][0]!==5||master.getRange('F4').values[0][0]!==186)throw new Error('Blank working field must remain visibly incomplete');
    cell.values=[[before]];wb.recalculate();boundaryChecks.push('Blank working value removes usable field; restored');
    const key=s.getRange('P1150'),savedKey=key.values[0][0];
    key.values=[[s.getRange('P1144').values[0][0]]];wb.recalculate();
    if(s.getRange('Q1144').values[0][0]!==0||s.getRange('Q1150').values[0][0]!==0)throw new Error('Duplicate field keys must be unusable');
    key.values=[[savedKey]];wb.recalculate();boundaryChecks.push('Duplicate key flagged on both appended records; restored');
  }else if(!refinement){
    const s=wb.worksheets.getItem('Products'),cell=s.getRange('C195'),before=cell.values[0][0];
    cell.values=[['Retired']];wb.recalculate();
    if(wb.worksheets.getItem('Overview').getRange('B7').values[0][0]!==186)throw new Error('Active option lifecycle count failed');
    cell.values=[[before]];wb.recalculate();boundaryChecks.push('Temporary retirement updates active count; restored');
  }
  for(const e of p.expected){const v=wb.worksheets.getItem(e.sheet).getRange(e.cell).values[0][0];if(v!==e.value){
    const data=wb.worksheets.getItem('Missing Pictures').getRange('A10:N227').values;
    await fs.writeFile(path.join(h,'count-diagnostic.json'),JSON.stringify({cell:e.cell,actual:v,open:data.map((r,i)=>({row:i+10,name:r[2],action:r[4],status:r[13]})).filter(r=>r.status==='Open'),strictOpen:data.filter(r=>r[4]==='Find / capture'&&r[13]==='Open').length},null,2));
    throw new Error(`Expected ${e.sheet}!${e.cell}=${e.value}; received ${v}`);
  }}
  const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:15},maxChars:2400});
  await fs.writeFile(path.join(h,p.key+'-formula-errors.ndjson'),errors.ndjson);
  for(const[sheetName,range,label]of p.previews){
    console.log(JSON.stringify({key:p.key,stage:'render',label}));
    const blob=await wb.render({sheetName,range,scale:1.2,format:'png'});
    await fs.writeFile(path.join(h,'previews',label+'.png'),new Uint8Array(await blob.arrayBuffer()));
  }
  await(await SpreadsheetFile.exportXlsx(wb)).save(refinement?raw:p.output);
  receipts.push({key:p.key,source_sha256:digest,output:p.output,declared_edits:p.edits.length,new_sheet:p.new_sheet,recalculated:true,boundary_checks:boundaryChecks});
  await fs.writeFile(path.join(h,refinement?'artifact-navigation-refinement-receipt.json':'artifact-authoring-receipt.json'),JSON.stringify({status:'EXPORTED_FOR_NATIVE_FEATURE_PRESERVATION',workbooks:receipts},null,2)+'\n');
  console.log(JSON.stringify({key:p.key,status:'EXPORTED',edits:p.edits.length}));
}
