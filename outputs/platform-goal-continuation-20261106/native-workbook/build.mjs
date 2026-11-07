import fs from 'node:fs/promises';
import path from 'node:path';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';

const out=path.dirname(new URL(import.meta.url).pathname);
const plan=JSON.parse(await fs.readFile(out+'/plan.json','utf8'));
const mode=process.argv[2],final=mode==='--final';
const book=await SpreadsheetFile.importXlsx(await FileBlob.load(out+(final?'/catalogue_wall_sculptures.xlsx':'/previous-catalogue.xlsx')));
async function render(range,name){const blob=await book.render({sheetName:'Wall Sculptures',range,scale:1,format:'png'});await fs.writeFile(out+'/'+name+'.png',new Uint8Array(await blob.arrayBuffer()));}
if(mode==='--before'){
 await render('KR115:KW118','before-crater-identity');await render('MJ115:ML118','before-crater-prices');
 console.log(JSON.stringify({status:'BEFORE_RENDERED'}));
}else{
 if(!final){
  for(const patch of plan.patches){const cell=book.worksheets.getItem(patch.sheet).getRange(patch.cell);if(typeof patch.value==='string')cell.format.numberFormat='@';cell.values=[[patch.value]];}
  await book.recalculate();
  const readback=[];
  for(const patch of plan.patches){const raw=book.worksheets.getItem(patch.sheet).getRange(patch.cell).values[0][0];const actual=raw instanceof Date?raw.toISOString():raw;const same=typeof patch.value==='number'?typeof actual==='number'&&Math.abs(actual-patch.value)<1e-6:actual===patch.value;if(!same)throw Error(JSON.stringify({cell:patch.cell,actual,expected:patch.value}));readback.push({sheet:patch.sheet,cell:patch.cell,value:actual,api_type:raw instanceof Date?'Date':typeof raw});}
  await fs.writeFile(out+'/authored-readback.json',JSON.stringify(readback,null,2));
  await(await SpreadsheetFile.exportXlsx(book)).save(out+'/authored.xlsx');
 }
 const prefix=final?'final':'after';await render('KR115:KW118',prefix+'-crater-identity');await render('MJ115:ML118',prefix+'-crater-prices');await render('KR18:KW19',prefix+'-ammonite-draft-identity');
 console.log(JSON.stringify({status:final?'FINAL_RENDERED':'AUTHORED',cells:plan.patches.length}));
}
