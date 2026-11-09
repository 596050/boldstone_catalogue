import fs from 'node:fs/promises';
import path from 'node:path';
import {FileBlob, SpreadsheetFile} from '@oai/artifact-tool';

const out=path.dirname(new URL(import.meta.url).pathname);
const plan=JSON.parse(await fs.readFile(out+'/plan.json','utf8'));
const final=process.argv.includes('--final');
const book=await SpreadsheetFile.importXlsx(await FileBlob.load(out+(final?'/catalogue_wall_sculptures.xlsx':'/previous-catalogue.xlsx')));
const sheet=book.worksheets.getItem('Wall Sculptures');
const col=n=>{let s='';for(;n;n=Math.floor((n-1)/26))s=String.fromCharCode(65+(n-1)%26)+s;return s;};
const index=address=>{const m=address.match(/^([A-Z]+)(\d+)$/);let c=0;for(const x of m[1])c=c*26+x.charCodeAt(0)-64;return {row:Number(m[2]),column:c};};
if(!final){
  const added=Array.from({length:182},()=>Array(plan.new_headers.length).fill(''));
  for(const p of plan.patches){const q=index(p.cell);if(q.column>=plan.first_added_column)added[q.row-7][q.column-plan.first_added_column]=p.value;}
  const first=col(plan.first_added_column),last=col(plan.last_added_column);
  sheet.getRange(first+'7:'+last+'188').values=added;
  sheet.getRange(first+'7:'+last+'188').format={font:{name:'Calibri',size:11},wrapText:true,verticalAlignment:'top',columnWidth:32};
  sheet.getRange(first+'7:'+last+'7').format={fill:'#586F50',font:{name:'Calibri',size:11,bold:true,color:'#FFFFFF'},wrapText:true};
  for(const p of plan.patches){
    if(index(p.cell).column<plan.first_added_column)sheet.getRange(p.cell).values=[[p.value]];
    if(p.style==='money')sheet.getRange(p.cell).format.numberFormat='"£"#,##0.00';
    else if(p.style==='integer')sheet.getRange(p.cell).format.numberFormat='0';
    else if(p.style==='utc')sheet.getRange(p.cell).format.numberFormat='yyyy-mm-dd hh:mm:ss';
    else if(p.style==='text')sheet.getRange(p.cell).format.numberFormat='@';
  }
  await book.recalculate();
  const readback=[];
  for(const p of plan.patches){
    const v=sheet.getRange(p.cell).values[0][0];
    const actual=v instanceof Date?(v.getTime()-Date.UTC(1899,11,30))/86400000:v;
    const same=typeof p.value==='number'?Math.abs(actual-p.value)<0.000001:String(actual??'')===String(p.value??'');
    if(!same)throw Error('Artifact readback mismatch at '+p.cell);
    readback.push({cell:p.cell,value:actual});
  }
  await fs.writeFile(out+'/authored-readback.json',JSON.stringify(readback,null,2));
  await(await SpreadsheetFile.exportXlsx(book)).save(out+'/authored.xlsx');
}
for(const p of plan.previews){
  const png=await book.render({sheetName:'Wall Sculptures',range:p.range,scale:1,format:'png'});
  await fs.writeFile(out+'/'+(final?'final':'after')+'-'+p.name+'.png',new Uint8Array(await png.arrayBuffer()));
}
console.log(JSON.stringify({status:final?'FINAL_RENDERED':'AUTHORED',patchedCells:plan.patches.length}));
