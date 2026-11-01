import fs from 'node:fs/promises';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const out=new URL('.',import.meta.url);
const book=await SpreadsheetFile.importXlsx(await FileBlob.load(new URL('previous-catalogue.xlsx',out).pathname));
const b=await book.render({sheetName:'Wall Sculptures',range:'L113:P117',scale:1.1,format:'png'});
await fs.writeFile(new URL('before-images.png',out),new Uint8Array(await b.arrayBuffer()));
