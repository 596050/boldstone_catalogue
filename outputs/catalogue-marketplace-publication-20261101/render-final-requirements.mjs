import fs from 'node:fs/promises';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const out='/Users/tprice/Documents/boldstone/outputs/catalogue-marketplace-publication-20261101/requirements-workbook';
const book=await SpreadsheetFile.importXlsx(await FileBlob.load(out+'/catalogue_wall_sculptures.xlsx'));
for(const [sheet,range,name] of [['Channel Details','J4:N6','final-channel-notes.png'],['US Delivery Estimates','L4:R8','final-us-costs.png'],['Wall Sculptures','I7:K10','final-dispatch.png']]){
 const p=await book.render({sheetName:sheet,range,scale:1,format:'png'}); await fs.writeFile(out+'/'+name,new Uint8Array(await p.arrayBuffer()));
}
console.log('Final workbook rendered successfully');
