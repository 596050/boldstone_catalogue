import fs from 'node:fs/promises';
import path from 'node:path';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const work=path.dirname(new URL(import.meta.url).pathname);
const d=JSON.parse(await fs.readFile(path.join(work,'workbook-data.json'),'utf8'));
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(d.output));
const receipt={status:'PASS_SAVED_FILE_REOPENED',previews:[]};
for(const [sheet,range,label] of [['Dropbox files','Q6:S10','final-file-timestamps'],['Dropbox folders','J6:K10','final-folder-timestamps']]){
  const target=path.join(work,'previews',label+'.png');
  const png=await wb.render({sheetName:sheet,range,scale:1,format:'png'});
  await fs.writeFile(target,new Uint8Array(await png.arrayBuffer()));
  receipt.previews.push({sheet,range,path:target});
}
await fs.writeFile(path.join(work,'saved-file-reopen-receipt.json'),JSON.stringify(receipt,null,2));
console.log(JSON.stringify(receipt));
