import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {FileBlob, SpreadsheetFile} from '@oai/artifact-tool';
const h=path.dirname(fileURLToPath(import.meta.url));
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(h,'master-workbook.pending')));
const amber={fill:'#FFF3D6',font:{color:'#9C440D'}};
const red={fill:'#FBE8E6',font:{color:'#A22E29'}};
wb.worksheets.getItem('Master Catalogue').getRange('K194:K195').conditionalFormats.add('cellIs',{operator:'notEqual',formula:6,format:amber});
const p=wb.worksheets.getItem('Photo Coverage');
for(const c of ['C','F','I']){
 p.getRange(`${c}194:${c}195`).conditionalFormats.add('containsText',{text:'Verify',format:amber});
 p.getRange(`${c}194:${c}195`).conditionalFormats.add('containsText',{text:'No verified',format:red});
}
const previews=[];
for(const [sheetName,range,name]of [['Master Catalogue','I194:K195','08-appended-completeness'],['Photo Coverage','A194:J195','09-appended-photo-coverage']]){
 const b=await wb.render({sheetName,range,scale:1.5,format:'png'}),p=path.join(h,'previews',name+'.png');
 await fs.writeFile(p,new Uint8Array(await b.arrayBuffer()));previews.push({sheet:sheetName,range,path:p});
}
await(await SpreadsheetFile.exportXlsx(wb)).save(path.join(h,'master-workbook.cf-export'));
await fs.writeFile(path.join(h,'conditional-format-extension-previews.json'),JSON.stringify(previews,null,2));
console.log('APPENDED_ROW_CONDITIONAL_FORMATS_EXPORTED');
