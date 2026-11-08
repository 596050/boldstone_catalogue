import fs from 'node:fs/promises';
import path from 'node:path';
import {FileBlob,SpreadsheetFile,Workbook} from '@oai/artifact-tool';
const out=path.dirname(new URL(import.meta.url).pathname);
const mode=process.argv[2];
if(mode==='--feed'){
  const plan=JSON.parse(await fs.readFile(out+'/plan.json','utf8'));
  const feed=await Workbook.fromCSV(await fs.readFile(out+'/pinterest_wall_sculptures.csv','utf8'),{sheetName:'Products'});
  const sheet=feed.worksheets.getItem('Products');
  sheet.showGridLines=false;
  sheet.getRange('A1:AT177').format={font:{name:'Calibri',size:11},verticalAlignment:'top',columnWidth:25,rowHeight:36};
  sheet.getRange('A1:AT1').format={fill:'#586F50',font:{name:'Calibri',size:11,bold:true,color:'#FFFFFF'},wrapText:true,rowHeight:58};
  sheet.getRange('B1:B177').format.columnWidth=45;
  sheet.getRange('C1:C177').format.columnWidth=65;
  sheet.getRange('D1:E177').format.columnWidth=42;
  sheet.getRange('F1:G177').format.columnWidth=18;
  sheet.getRange('B2:C177').format.wrapText=true;
  sheet.getRange('A2:A177').format.numberFormat='@';
  sheet.freezePanes.freezeRows(1);
  sheet.tables.add('A1:AT177',true,'PinterestProducts');
  await feed.recalculate();
  const check=sheet.getRange('A1:AT177').values;
  for(let r=0;r<plan.public_feed_rows.length;r++)for(let c=0;c<plan.pinterest_feed_fields.length;c++){
    const want=plan.public_feed_rows[r][plan.pinterest_feed_fields[c]]||'';
    if(String(check[r+1][c]??'')!==String(want))throw Error('Feed readback '+r+','+c);
  }
  const blob=await feed.render({sheetName:'Products',range:'A1:G5',scale:1,format:'png'});
  await fs.writeFile(out+'/pinterest-feed-preview.png',new Uint8Array(await blob.arrayBuffer()));
  await(await SpreadsheetFile.exportXlsx(feed)).save(out+'/pinterest_wall_sculptures.xlsx');
  console.log(JSON.stringify({status:'FEED_AUTHORED',rows:176,columns:46}));
  process.exit(0);
}
const final=mode==='--final';
const book=await SpreadsheetFile.importXlsx(await FileBlob.load(out+(final?'/catalogue_wall_sculptures.xlsx':'/previous-catalogue.xlsx')));
const previews=JSON.parse(await fs.readFile(out+'/plan.json','utf8')).previews;
async function render(p,prefix){const blob=await book.render({sheetName:'Wall Sculptures',range:p.range,scale:1,format:'png'});await fs.writeFile(out+'/'+prefix+'-'+p.name+'.png',new Uint8Array(await blob.arrayBuffer()));}
if(mode==='--before'){
  for(const p of previews)await render(p,'before');
  console.log(JSON.stringify({status:'BEFORE_RENDERED'}));
}else{
  const plan=JSON.parse(await fs.readFile(out+'/plan.json','utf8'));
  if(!final){
    for(const p of plan.patches)book.worksheets.getItem(p.sheet).getRange(p.cell).values=[[p.value]];
    for(const r of plan.row_heights||[])book.worksheets.getItem(r.sheet).getRange('A'+r.row+':XB'+r.row).format.rowHeight=r.value;
    await book.recalculate();
    const readback=[];
    for(const p of plan.patches){const raw=book.worksheets.getItem(p.sheet).getRange(p.cell).values[0][0];const value=raw instanceof Date?raw.toISOString():raw;if(value!==p.value)throw Error('Readback mismatch '+p.cell);readback.push({cell:p.cell,value});}
    await fs.writeFile(out+'/authored-readback.json',JSON.stringify(readback,null,2));
    await(await SpreadsheetFile.exportXlsx(book)).save(out+'/authored.xlsx');
  }
  for(const p of plan.previews)await render(p,final?'final':'after');
  console.log(JSON.stringify({status:final?'FINAL_RENDERED':'AUTHORED',cells:plan.patches.length}));
}
