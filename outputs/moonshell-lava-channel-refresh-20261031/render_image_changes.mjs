import fs from 'node:fs/promises';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const out=new URL('.',import.meta.url);
const book=await SpreadsheetFile.importXlsx(await FileBlob.load(new URL('catalogue_wall_sculptures.xlsx',out).pathname));
const b=await book.render({sheetName:'Wall Sculptures',range:'L137:P138',scale:1.2,format:'png'});
await fs.writeFile(new URL('after-moonshell-images.png',out),new Uint8Array(await b.arrayBuffer()));
