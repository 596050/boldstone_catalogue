import fs from 'node:fs/promises';
import path from 'node:path';
import {FileBlob, SpreadsheetFile} from '@oai/artifact-tool';
const out=path.dirname(new URL(import.meta.url).pathname);
const p=JSON.parse(await fs.readFile(out+'/plan.json','utf8'));
const finalPreview=process.argv[2]==='--final-preview';
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(out+(finalPreview?'/catalogue_wall_sculptures.xlsx':'/previous-catalogue.xlsx')));
const s=wb.worksheets.getItem('Wall Sculptures');
if(finalPreview){
 console.log((await wb.inspect({kind:'region',sheetId:s.name,range:p.preview_range,maxChars:1500})).ndjson);
 for(const[range,name]of[['WI7:WL9','final-identities'],[p.preview_range,'final']]){
  await wb.inspect({kind:'region',sheetId:s.name,range,maxChars:300});
  const image=await wb.render({sheetName:s.name,range,scale:1,format:'png'});
  await fs.writeFile(out+'/'+name+'.png',new Uint8Array(await image.arrayBuffer()));
 }
}else if(process.argv[2]==='--before'){
 const image=await wb.render({sheetName:s.name,range:p.preview_range,scale:1,format:'png'});
 await fs.writeFile(out+'/before.png',new Uint8Array(await image.arrayBuffer()));
 console.log((await wb.inspect({kind:'region',sheetId:s.name,range:p.preview_range,maxChars:1200})).ndjson);
}else{
 for(const c of p.patches)s.getRange(c.cell).values=[[c.value]];
 await wb.recalculate();
 for(const c of p.patches)if(s.getRange(c.cell).values[0][0]!==c.value)throw Error('Written value differs: '+c.cell);
 console.log((await wb.inspect({kind:'region',sheetId:s.name,range:p.preview_range,maxChars:1600})).ndjson);
 await(await SpreadsheetFile.exportXlsx(wb)).save(out+'/authored.xlsx');
 const image=await wb.render({sheetName:s.name,range:p.preview_range,scale:1,format:'png'});
 await fs.writeFile(out+'/after.png',new Uint8Array(await image.arrayBuffer()));
 console.log(JSON.stringify({status:'AUTHORED',patches:p.patches.length}));
}
