import fs from 'node:fs/promises';
import path from 'node:path';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const out=path.dirname(new URL(import.meta.url).pathname);
const mode=process.argv[2];
const final=mode==='--final';
const book=await SpreadsheetFile.importXlsx(await FileBlob.load(out+(final?'/catalogue_wall_sculptures.xlsx':'/previous-catalogue.xlsx')));
const plan=JSON.parse(await fs.readFile(out+'/plan.json','utf8'));
const previews=plan.previews.filter(p=>p.name==='chairish-photo');
async function render(p,prefix){const blob=await book.render({sheetName:'Wall Sculptures',range:p.range,scale:1,format:'png'});await fs.writeFile(out+'/'+prefix+'-'+p.name+'.png',new Uint8Array(await blob.arrayBuffer()));}
if(mode==='--before'){
  for(const p of previews)await render(p,'before');
  console.log(JSON.stringify({status:'BEFORE_RENDERED'}));
}else{
  if(!final){
    const sheet=book.worksheets.getItem('Wall Sculptures');
    for(const column of plan.new_columns){
      sheet.getRange(column.column+'7').copyFrom(sheet.getRange(column.header_style_source),'all');
      const sourceColumn=column.body_style_source.replace(/\d/g,'');
      const target=sheet.getRange(column.column+'8:'+column.column+'188');
      target.copyFrom(sheet.getRange(sourceColumn+'8:'+sourceColumn+'188'),'all');
      target.values=Array.from({length:181},()=>[null]);
      sheet.getRange(column.column+'7:'+column.column+'188').format.columnWidth=column.width;
    }
    for(const p of plan.patches)book.worksheets.getItem(p.sheet).getRange(p.cell).values=[[p.value]];
    // The supported API recreates the table over the extended range. The final
    // preservation pass retains its original ID, style, columns and relationships.
    sheet.tables.getItem('WallSculpturesTable').delete();
    const extendedTable=sheet.tables.add('A7:'+plan.new_last_column+'188',true,'WallSculpturesTable');
    extendedTable.style='TableStyleLight9';
    for(const column of plan.new_columns)sheet.getRange(column.column+'8:'+column.column+'188').setNumberFormat(column.number_format);
    await book.recalculate();
    const readback=[];
    for(const p of plan.patches){const raw=book.worksheets.getItem(p.sheet).getRange(p.cell).values[0][0];const value=raw instanceof Date?raw.toISOString():raw;if(value!==p.value)throw Error('Readback mismatch '+JSON.stringify({cell:p.cell,value,expected:p.value,type:typeof raw}));readback.push({cell:p.cell,value});}
    await fs.writeFile(out+'/authored-readback.json',JSON.stringify(readback,null,2));
    await(await SpreadsheetFile.exportXlsx(book)).save(out+'/authored.xlsx');
  }
  for(const p of plan.previews)await render(p,final?'final':'after');
  console.log(JSON.stringify({status:final?'FINAL_RENDERED':'AUTHORED',cells:plan.patches.length}));
}
