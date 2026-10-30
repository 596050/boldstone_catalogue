import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {FileBlob, SpreadsheetFile} from '@oai/artifact-tool';

const h=path.dirname(fileURLToPath(import.meta.url));
const plans=JSON.parse(await fs.readFile(path.join(h,'workbook-edit-plan.json'),'utf8')).plans;
const overlay=JSON.parse(await fs.readFile(path.join(h,'current-image-overlay.json'),'utf8'));
const manifest=JSON.parse(await fs.readFile(path.join(h,'input-manifest.json'),'utf8'));
const receipts=[];
const refinement=process.argv.includes('--refine-navigation-labels');
const hyperlink=(url,label)=>`=HYPERLINK("${url.replaceAll('"','""')}","${label.replaceAll('"','""')}")`;
for (const p of plans) {
  if(refinement&&!p.edits.some(e=>e.navigation_refinement))continue;
  const digest=crypto.createHash('sha256').update(await fs.readFile(p.source)).digest('hex');
  if(digest!==p.source_sha256)throw new Error('Input hash drift');
  const raw=path.join(h,p.key+'-artifact-authored.xlsx');
  const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(refinement?raw:p.source));
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
    const s=wb.worksheets.add(p.new_sheet),end=overlay.length+6;
    s.showGridLines=false;s.tabColor='#344b59';
    s.getRange(`A1:L${end}`).format.font={name:'Arial',size:10};
    s.getRange('A2:D2').merge();s.getRange('A2').values=[['Current Dropbox image paths']];
    s.getRange('A2').format.font={name:'Arial',size:18,bold:true,color:'#243847'};
    s.getRange('A2:D2').format.rowHeight=30;
    s.getRange('A3:D3').merge();
    s.getRange('A3').values=[['Publication cut '+manifest.recorded_utc+' | Wall census plus retained Workshop scope, adjusted by verified deletion receipts. Filenames and folders are navigation evidence; physical specifications remain separately qualified.']];
    s.getRange('A3:D3').format.wrapText=true;s.getRange('A3:D3').format.rowHeight=44;
    s.getRange('A4').values=[['Current scoped image files']];s.getRange('B4').formulas=[[`=COUNTA(E7:E${end})`]];
    s.getRange('C4').values=[['Wall files']];s.getRange('D4').formulas=[[`=COUNTIF(L7:L${end},"Wall Sculptures")`]];
    s.getRange('E4').values=[['Retained Workshop']];s.getRange('F4').formulas=[[`=COUNTIF(L7:L${end},"Retained Workshop")`]];
    s.getRange('A4:F4').format.rowHeight=26;
    const headers=['Current filename','Containing folder','Image','Folder','Stable file ID','Actual parent folder ID','Current recorded path','Dropbox content hash','Bytes','Server modified (UTC)','Selected catalogue references','Native scope'];
    s.getRange('A6:L6').values=[headers];
    const values=overlay.map(r=>[r.name||r.path.split('/').at(-1),decodeURIComponent(r.folder_url).split('/').at(-1),'Image','Folder',r.file_id,r.folder_id,r.path,r.content_hash||'',r.bytes??r.size??null,(r.modified||r.server_modified)?new Date(r.modified||r.server_modified):null,r.selected_references.map(x=>x.name+' — '+x.role).join(' | '),r.scope]);
    s.getRange(`A7:L${end}`).values=values;
    s.getRange(`C7:D${end}`).formulas=overlay.map(r=>[hyperlink(r.image_url,'Image'),hyperlink(r.folder_url,'Folder')]);
    s.getRange(`I7:I${end}`).setNumberFormat('#,##0');s.getRange(`J7:J${end}`).setNumberFormat('yyyy-mm-dd hh:mm');
    s.getRange('A6:L6').format={fill:'#344b59',font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},rowHeight:30};
    s.getRange(`A7:L${end}`).format.rowHeight=42;
    s.getRange(`A7:B${end}`).format.wrapText=true;
    for(const[col,width]of [['A',60],['B',42],['C',14],['D',14],['E',41],['F',41],['G',95],['H',66],['I',13],['J',22],['K',76],['L',22]])s.getRange(`${col}:${col}`).format.columnWidth=width;
    s.getRange(`C7:D${end}`).format.font={name:'Arial',size:10,color:'#17617D',underline:'single'};
    s.freezePanes.freezeRows(6);s.freezePanes.freezeColumns(2);
    s.tables.add(`A6:L${end}`,true,'CurrentDropboxImagePaths');
  }
  wb.recalculate();
  for(const e of p.expected){const v=wb.worksheets.getItem(e.sheet).getRange(e.cell).values[0][0];if(v!==e.value)throw new Error(`Expected ${e.sheet}!${e.cell}=${e.value}; received ${v}`);}
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
