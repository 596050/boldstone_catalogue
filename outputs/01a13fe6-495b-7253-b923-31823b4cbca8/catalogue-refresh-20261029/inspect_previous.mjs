import fs from 'node:fs/promises';
import {FileBlob, SpreadsheetFile} from '@oai/artifact-tool';
const wb = await SpreadsheetFile.importXlsx(await FileBlob.load(new URL('./previous-catalogue.xlsx', import.meta.url).pathname));
const result = await wb.inspect({kind:'workbook,sheet,table',maxChars:3500,tableMaxRows:2,tableMaxCols:4});
await fs.writeFile(new URL('./previous-inspection.jsonl',import.meta.url),result.ndjson);
for(const [sheetName,range,name] of [['Wall Sculptures','A1:J13','previous-catalogue.png'],['Images','A1:N12','previous-images.png'],['Specification Sources','A1:H11','previous-sources.png']]) {
  const image=await wb.render({sheetName,range,scale:1,format:'png'});
  await fs.writeFile(new URL('./'+name,import.meta.url),new Uint8Array(await image.arrayBuffer()));
}
console.log(result.ndjson);
