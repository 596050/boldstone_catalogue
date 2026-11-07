import fs from 'node:fs/promises';
import path from 'node:path';
import {FileBlob, SpreadsheetFile} from '@oai/artifact-tool';

const out=path.dirname(new URL(import.meta.url).pathname);
const plan=JSON.parse(await fs.readFile(out+'/plan.json','utf8'));
const mode=process.argv[2];
const final=mode==='--final';
const book=await SpreadsheetFile.importXlsx(await FileBlob.load(out+(final?'/catalogue_wall_sculptures.xlsx':'/previous-catalogue.xlsx')));
const master=book.worksheets.getItem('Wall Sculptures');
async function render(sheetName,range,name){
  await book.inspect({kind:'region',sheetId:sheetName,range,maxChars:600});
  const blob=await book.render({sheetName,range,scale:1,format:'png'});
  await fs.writeFile(out+'/'+name+'.png',new Uint8Array(await blob.arrayBuffer()));
}
if(mode==='--before'){
  await render('Images',plan.image_preview_range,'before-image');
  console.log((await book.inspect({kind:'region',sheetId:'Images',range:plan.image_preview_range,maxChars:900})).ndjson);
}else{
  if(!final){
    master.getRangeByIndexes(6,plan.first_added_column-1,182,plan.added_headers.length).format={font:{name:'Calibri',size:11},wrapText:true,verticalAlignment:'top',columnWidth:32};
    master.getRangeByIndexes(6,plan.first_added_column-1,1,plan.added_headers.length).format={fill:'#586F50',font:{name:'Calibri',size:11,bold:true,color:'#FFFFFF'},rowHeight:75};
    master.getRangeByIndexes(6,plan.first_added_column-1,182,plan.added_headers.length).format.numberFormat='@';
    for(const p of plan.patches)book.worksheets.getItem(p.sheet).getRange(p.cell).values=[[p.value]];
    for(const key of ['saatchi_art_upload_candidate_width_px','saatchi_art_upload_candidate_height_px'])master.getRange(`${plan.headers[key]}8:${plan.headers[key]}188`).format.numberFormat='0';
    await book.recalculate();
    for(const p of plan.patches){
      const value=book.worksheets.getItem(p.sheet).getRange(p.cell).values[0][0];
      if(value!==p.value)throw Error(`Value mismatch ${p.sheet}!${p.cell}: ${JSON.stringify(value)} != ${JSON.stringify(p.value)}`);
    }
    await(await SpreadsheetFile.exportXlsx(book)).save(out+'/authored.xlsx');
  }
  await render('Images',plan.image_preview_range,final?'final-image':'after-image');
  await render('Wall Sculptures',plan.preview_header_range,final?'final-headers':'after-headers');
  await render('Wall Sculptures',plan.preview_row_range,final?'final-row':'after-row');
  console.log(JSON.stringify({status:final?'FINAL_RENDERED':'AUTHORED',patches:plan.patches.length}));
}
