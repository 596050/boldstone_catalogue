import fs from 'node:fs/promises';
import path from 'node:path';
import {FileBlob, SpreadsheetFile} from '@oai/artifact-tool';
const out=path.dirname(new URL(import.meta.url).pathname);
const plan=JSON.parse(await fs.readFile(path.join(out,'plan.json'),'utf8'));
const preview=process.argv.includes('--preview');
const final=process.argv.includes('--verify-final');
const book=await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(out,final?'catalogue_wall_sculptures.xlsx':'previous-catalogue.xlsx')));
const master=book.worksheets.getItem('Wall Sculptures');
if(process.argv.includes('--help-values')){
 console.log(book.help('range.values',{include:'index,notes,examples',maxChars:5000}).ndjson);
 for(const value of ['Yes',"'Yes",'2026-11-05T18:34:10.017381+00:00',"'2026-11-05T18:34:10.017381+00:00",'18186080068422463',"'18186080068422463"]){master.getRange('ZZ1').format.numberFormat='@';master.getRange('ZZ1').values=[[value]];console.log(JSON.stringify({input:value,output:master.getRange('ZZ1').values[0][0]}));}
 process.exit(0);
}
if(preview){
 const blob=await book.render({sheetName:'Wall Sculptures',range:'PO7:PQ11',scale:1.1,format:'png'});
 await fs.writeFile(path.join(out,'before.png'),new Uint8Array(await blob.arrayBuffer()));
 console.log((await book.inspect({kind:'region',sheetId:'Wall Sculptures',range:'PO7:PQ11',maxChars:1000,tableMaxRows:5,tableMaxCols:3})).ndjson);
 process.exit(0);
}
if(!final){
 master.getRangeByIndexes(6,plan.first_added_column-1,182,plan.added_headers.length).format={font:{name:'Calibri',size:11},wrapText:true,verticalAlignment:'top',columnWidth:32};
 master.getRangeByIndexes(6,plan.first_added_column-1,1,plan.added_headers.length).format={fill:'#586F50',font:{name:'Calibri',size:11,bold:true,color:'#FFFFFF'},rowHeight:75};
 master.getRangeByIndexes(6,plan.first_added_column-1,182,plan.added_headers.length).format.numberFormat='@';
 for(const p of plan.patches)book.worksheets.getItem(p.sheet).getRange(p.cell).values=[[p.value]];
 for(const h of ['saatchi_art_artwork_price_usd','saatchi_art_packed_weight_kg_estimate','saatchi_art_units_available_native','saatchi_art_year_native','chairish_photo_count_verified'])master.getRange(`${plan.headers[h]}8:${plan.headers[h]}188`).format.numberFormat=h.endsWith('usd')?'0.00':'0';
 await book.recalculate();
 for(const p of plan.patches)if(book.worksheets.getItem(p.sheet).getRange(p.cell).values[0][0]!==p.value)throw Error(`Readback mismatch ${p.sheet}!${p.cell}: ${JSON.stringify(book.worksheets.getItem(p.sheet).getRange(p.cell).values[0][0])} != ${JSON.stringify(p.value)}`);
 await (await SpreadsheetFile.exportXlsx(book)).save(path.join(out,'authored.xlsx'));
}
const sample=plan.patches.find(p=>p.sheet==='Wall Sculptures' && p.cell.startsWith(plan.headers.saatchi_art_publication_status) && p.value!=='saatchi_art_publication_status');
const row=Number(sample.cell.match(/\d+/)[0]);
for(const [range,name] of [[`${plan.headers.saatchi_art_native_artwork_id}7:${plan.headers.saatchi_art_publication_status}9`,'headers'],[`${plan.headers.saatchi_art_native_artwork_id}${row}:${plan.headers.saatchi_art_publication_status}${row}`,'published-row']]){
 const blob=await book.render({sheetName:'Wall Sculptures',range,scale:1.1,format:'png'});
 await fs.writeFile(path.join(out,(final?'final-':'')+name+'.png'),new Uint8Array(await blob.arrayBuffer()));
}
console.log(JSON.stringify({status:final?'FINAL_RENDERED':'AUTHORED',patches:plan.patches.length}));
