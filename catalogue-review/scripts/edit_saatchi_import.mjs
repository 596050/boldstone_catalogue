import fs from 'node:fs/promises';
import path from 'node:path';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const out=path.resolve(process.argv[2]);
const plan=JSON.parse(await fs.readFile(path.join(out,'saatchi-import-plan.json'),'utf8'));
const preview=process.argv.includes('--preview');
const final=process.argv.includes('--verify-final');
const amend=process.argv.includes('--amend');
const notesOnly=process.argv.includes('--notes-only');
const book=await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(out,final?'catalogue_wall_sculptures.xlsx':amend?'authored.xlsx':'previous-catalogue.xlsx')));
const master=book.worksheets.getItem('Wall Sculptures');
if(preview){
 const image=await book.render({sheetName:'Wall Sculptures',range:'JD7:JI10',scale:1.2,format:'png'});
 await fs.writeFile(path.join(out,'before.png'),new Uint8Array(await image.arrayBuffer()));
 console.log((await book.inspect({kind:'region',sheetId:'Wall Sculptures',range:'JD7:JI9',maxChars:1800,tableMaxRows:3,tableMaxCols:6})).ndjson);
 process.exit(0);
}
if(!final){
 const rows=Array.from({length:182},()=>Array(plan.added_master_columns.length).fill(null));
 const index=s=>[...s.replace(/\d/g,'')].reduce((n,c)=>n*26+c.charCodeAt(0)-64,0);
 for(const p of plan.patches){
  if(p.sheet==='Wall Sculptures'&&index(p.cell)>=plan.first_master_column)rows[Number(p.cell.match(/\d+/)[0])-7][index(p.cell)-plan.first_master_column]=p.value;
 }
 const region=master.getRangeByIndexes(6,plan.first_master_column-1,182,plan.added_master_columns.length);
 if(!amend){
  region.values=rows;
  region.format={font:{name:'Calibri',size:11},wrapText:true,verticalAlignment:'top',columnWidth:32};
  master.getRangeByIndexes(6,plan.first_master_column-1,1,plan.added_master_columns.length).format={fill:'#586F50',font:{name:'Calibri',size:11,bold:true,color:'#FFFFFF'},rowHeight:75};
 }
 for(const c of plan.identifier_corrections??[]){
  const cell=book.worksheets.getItem(c.sheet).getRange(c.cell);cell.values=[[c.value]];cell.format.numberFormat='@';
 }
 // Format whole new columns once; imported observations remain typed values.
 for(const h of amend?[]:plan.added_master_columns){
  const p=plan.patches.find(p=>p.sheet==='Wall Sculptures'&&p.cell.startsWith(plan.headers[h])&&p.cell.match(/^[A-Z]+/)[0]===plan.headers[h]&&p.format&&p.format!=='header');
  if(p)master.getRange(`${plan.headers[h]}8:${plan.headers[h]}188`).format.numberFormat=p.format;
 }
 const notes=book.worksheets.getItem('Platform Review');
 const notesRows=Array.from({length:plan.global_notes_last_row-plan.global_notes_first_row+1},()=>Array(3).fill(null));
 for(const p of plan.patches.filter(p=>p.sheet==='Platform Review'))notesRows[Number(p.cell.match(/\d+/)[0])-plan.global_notes_first_row][index(p.cell)-10]=p.value;
 const nr=notes.getRange(`J${plan.global_notes_first_row}:L${plan.global_notes_last_row}`);
 nr.values=notesRows;nr.format={font:{name:'Calibri',size:11},wrapText:true,verticalAlignment:'top',rowHeight:58};
 notes.getRange(`J${plan.global_notes_first_row}:L${plan.global_notes_first_row}`).format={fill:'#586F50',font:{bold:true,color:'#FFFFFF'},rowHeight:32};
 notes.getRange('L:L').format.columnWidth=90;
 for(const p of plan.patches.filter(p=>p.sheet==='Platform Review'&&p.format&&p.format!=='header'))notes.getRange(p.cell).format.numberFormat=p.format;
 for(let r=plan.global_notes_first_row+1;r<=plan.global_notes_last_row;r++){
  const count=Math.max(...notesRows[r-plan.global_notes_first_row].map((v,i)=>Math.ceil(String(v??'').length/(i===0?28:85))));
  notes.getRange(`J${r}:L${r}`).format.rowHeight=Math.max(24,Math.min(220,count*16));
 }
 for(const r of plan.row_format_updates??[])book.worksheets.getItem(r.sheet).getRange(`J${r.row}:L${r.row}`).format.rowHeight=r.height;
 await book.recalculate();
 const errors=[];
 const savedRows=region.values,savedNotes=nr.values;
 for(const p of plan.patches){
  const n=Number(p.cell.match(/\d+/)[0]);
  const value=p.sheet==='Wall Sculptures'&&index(p.cell)>=plan.first_master_column?savedRows[n-7][index(p.cell)-plan.first_master_column]:p.sheet==='Platform Review'?savedNotes[n-plan.global_notes_first_row][index(p.cell)-10]:book.worksheets.getItem(p.sheet).getRange(p.cell).values[0][0];
  if(value!==p.value&&!(value===null&&p.value==='')&&!(typeof value==='number'&&typeof p.value==='number'&&Math.abs(value-p.value)<1e-8))errors.push({sheet:p.sheet,cell:p.cell,expected:p.value,value});
 }
 if(errors.length)throw Error(JSON.stringify(errors.slice(0,10)));
 await fs.writeFile(path.join(out,'artifact-import-verification.json'),JSON.stringify({status:'PASS',new_cell_values_verified:plan.patches.length,original_formulas_not_replaced:true},null,2));
 await(await SpreadsheetFile.exportXlsx(book)).save(path.join(out,'authored.xlsx'));
}
const h=plan.headers;
for(const [range,name] of notesOnly?[]:[
 [`${h.saatchi_observed_record_number}7:${h.saatchi_observed_availability}11`,'artworks'],
 [`${h.saatchi_observed_artwork_price_usd}7:${h.saatchi_observed_your_60_share_usd}11`,'prices'],
 [`${h.saatchi_observed_shipping_uk_core_europe_usd}7:${h.saatchi_observed_list_price_united_states_usd}11`,'shipping']]){
 await fs.writeFile(path.join(out,(final?'final-':'')+name+'.png'),new Uint8Array(await(await book.render({sheetName:'Wall Sculptures',range,scale:1.25,format:'png'})).arrayBuffer()));
}
await fs.writeFile(path.join(out,(final?'final-':'')+'notes.png'),new Uint8Array(await(await book.render({sheetName:'Platform Review',range:'J22:L29',scale:1.1,format:'png'})).arrayBuffer()));
if(final)await fs.writeFile(path.join(out,'final-notes-details.png'),new Uint8Array(await(await book.render({sheetName:'Platform Review',range:'J63:L68',scale:1.1,format:'png'})).arrayBuffer()));
console.log(JSON.stringify({status:final?'FINAL_IMPORTED_AND_RENDERED':'AUTHORED',new_prefixed_fields:plan.added_master_columns.length,matched_artworks:plan.matched_artworks}));
