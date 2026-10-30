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
  const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(refinement?raw:p.source));
  if(p.table_expansion&&!refinement){
    const t=p.table_expansion,s=wb.worksheets.getItem(t.sheet);
    const existing=s.tables.items.find(x=>x.name===t.name);
    if(!existing)throw new Error('Declared source table missing');
    const range=s.getRange(t.range),savedValues=range.values,savedFormulas=range.formulas;
    existing.delete();range.values=savedValues;
    for(let row=0;row<savedFormulas.length;row++)for(let col=0;col<savedFormulas[row].length;col++)if(savedFormulas[row][col])range.getCell(row,col).formulas=[[savedFormulas[row][col]]];
    s.tables.add(t.range,true,t.name);
  }
  // Batch consecutive edits within a column and operation type.
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
    const records=JSON.parse(await fs.readFile(path.join(h,'listing-use-exclusions.json'),'utf8'));
    const s=wb.worksheets.add(p.new_sheet),end=records.length+6;
    s.showGridLines=false;s.tabColor='#344b59';
    s.getRange(`A1:L${end}`).format.font={name:'Arial',size:10};
    s.getRange('A2:F2').merge();s.getRange('A2').values=[['In situ images excluded from Listing']];
    s.getRange('A2').format.font={name:'Arial',size:18,bold:true,color:'#243847'};s.getRange('A2:F2').format.rowHeight=30;
    s.getRange('A3:H3').merge();s.getRange('A3').values=[['Owner image-use policy verified '+manifest.policy_cut_utc+'. Listing removals only; originals, shared types, other purposes and component associations retained. Four Primary choices need replacements. Native paths retain the separate '+manifest.native_inventory_cut_utc+' inventory cutoff.']];
    s.getRange('A3:H3').format.wrapText=true;s.getRange('A3:H3').format.rowHeight=48;
    s.getRange('A4').values=[['Removed choices']];s.getRange('B4').formulas=[[`=COUNTA(A7:A${end})`]];
    s.getRange('C4').values=[['Distinct images']];s.getRange('D4').values=[[68]];
    s.getRange('E4').values=[['Active sculptures']];s.getRange('F4').values=[[30]];
    s.getRange('G4').values=[['Primary choices cleared']];s.getRange('H4').formulas=[[`=COUNTIF(F7:F${end},"Yes")`]];
    s.getRange('A4:H4').format.rowHeight=30;
    const headers=['Sculpture option','Catalogue ID','Stable file ID','Removed use','Remaining purposes','Primary cleared','Effective shared types','Previous review version','Saved review version','Excluded Listing image','Containing folder','Scope'];
    s.getRange('A6:L6').values=[headers];
    s.getRange(`A7:L${end}`).values=records.map(r=>[r.name,r.product_id,r.file_id,r.excluded_use,r.remaining_uses.join(', ')||'None',r.primary_cleared?'Yes':'No',r.effective_image_types.join(', '),r.before_review_version,r.review_version,'Image','Folder',r.scope]);
    s.getRange(`J7:K${end}`).formulas=records.map(r=>[hyperlink(r.image_url,'Image'),hyperlink(r.folder_url,'Folder')]);
    s.getRange('A6:L6').format={fill:'#344b59',font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},rowHeight:38,wrapText:true};
    s.getRange(`A7:L${end}`).format.rowHeight=52;s.getRange(`A7:I${end}`).format.wrapText=true;s.getRange(`L7:L${end}`).format.wrapText=true;
    s.getRange(`H7:I${end}`).setNumberFormat('0');
    for(const[col,width]of [['A',41],['B',24],['C',43],['D',17],['E',22],['F',16],['G',23],['H',17],['I',17],['J',22],['K',20],['L',76]])s.getRange(`${col}:${col}`).format.columnWidth=width;
    s.getRange(`J7:K${end}`).format.font={name:'Arial',size:10,color:'#17617D',underline:'single'};
    s.freezePanes.freezeRows(6);s.freezePanes.freezeColumns(1);
    s.tables.add(`A6:L${end}`,true,'CurrentListingUseExclusions');
  }
  wb.recalculate();
  if(p.new_sheet){
    const s=wb.worksheets.getItem('Image Use Exclusions'),f=s.getRange('F7'),previous=f.values[0][0];
    if(previous!=='No')throw new Error('Count boundary-test input drift');
    f.values=[['Yes']];wb.recalculate();
    if(s.getRange('H4').values[0][0]!==5)throw new Error('Cleared Primary count does not respond to a changed record');
    f.values=[[previous]];wb.recalculate();
  }
  for(const e of p.expected){const v=wb.worksheets.getItem(e.sheet).getRange(e.cell).values[0][0];if(v!==e.value){
    const data=wb.worksheets.getItem('Missing Pictures').getRange('A10:N227').values;
    await fs.writeFile(path.join(h,'count-diagnostic.json'),JSON.stringify({cell:e.cell,actual:v,open:data.map((r,i)=>({row:i+10,name:r[2],action:r[4],status:r[13]})).filter(r=>r.status==='Open'),strictOpen:data.filter(r=>r[4]==='Find / capture'&&r[13]==='Open').length},null,2));
    throw new Error(`Expected ${e.sheet}!${e.cell}=${e.value}; received ${v}`);
  }}
  const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:15},maxChars:2400});
  await fs.writeFile(path.join(h,p.key+'-formula-errors.ndjson'),errors.ndjson);
  for(const[sheetName,range,label]of p.previews){
    const blob=await wb.render({sheetName,range,scale:1.2,format:'png'});
    await fs.writeFile(path.join(h,'previews',label+'.png'),new Uint8Array(await blob.arrayBuffer()));
  }
  await(await SpreadsheetFile.exportXlsx(wb)).save(refinement?raw:p.output);
  receipts.push({key:p.key,source_sha256:digest,output:p.output,declared_edits:p.edits.length,new_sheet:p.new_sheet,recalculated:true});
  await fs.writeFile(path.join(h,refinement?'artifact-navigation-refinement-receipt.json':'artifact-authoring-receipt.json'),JSON.stringify({status:'EXPORTED_FOR_NATIVE_FEATURE_PRESERVATION',workbooks:receipts},null,2)+'\n');
  console.log(JSON.stringify({key:p.key,status:'EXPORTED',edits:p.edits.length}));
}
