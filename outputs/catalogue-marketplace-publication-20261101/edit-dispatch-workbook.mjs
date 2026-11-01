import fs from 'node:fs/promises';
import path from 'node:path';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const out=path.join(path.dirname(new URL(import.meta.url).pathname),'dispatch-workbook');
const changes=JSON.parse(await fs.readFile(path.join(out,'patches.json'),'utf8'));
const book=await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(out,'previous-catalogue.xlsx')));
const mode=process.argv[2]||'inspect';
if(mode==='inspect'){
 console.log((await book.inspect({kind:'table',range:'Channel Details!K4:M6',include:'values,formulas',tableMaxRows:3,tableMaxCols:3,maxChars:4000})).ndjson);
 await fs.writeFile(path.join(out,'before.png'),new Uint8Array(await(await book.render({sheetName:'Channel Details',range:'K4:M7',scale:1,format:'png'})).arrayBuffer()));
}else if(mode==='edit'){
 for(const p of changes.patches){const r=book.worksheets.getItem(p.sheet).getRange(p.cell);if(r.values[0][0]!==p.before)throw Error('Source mismatch '+p.cell);r.values=[[p.value]];}
 book.recalculate();
 console.log((await book.inspect({kind:'table',range:'Channel Details!K4:M6',include:'values,formulas',tableMaxRows:3,tableMaxCols:3,maxChars:4000})).ndjson);
 console.log((await book.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:30},maxChars:2000})).ndjson);
 await fs.writeFile(path.join(out,'after.png'),new Uint8Array(await(await book.render({sheetName:'Channel Details',range:'K4:M7',scale:1,format:'png'})).arrayBuffer()));
 await(await SpreadsheetFile.exportXlsx(book)).save(path.join(out,'authored.xlsx'));
 console.log(JSON.stringify({authored_cells:changes.patches.length}));
}else throw Error('Unknown mode');
