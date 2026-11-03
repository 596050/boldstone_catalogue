import fs from 'node:fs/promises';
import path from 'node:path';
import {FileBlob, SpreadsheetFile} from '@oai/artifact-tool';

const out=path.resolve(process.argv[2]);
const plan=JSON.parse(await fs.readFile(path.join(out,'patches.json'),'utf8'));
const finalPreview=process.argv.includes('--verify-final');
const book=await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(out,finalPreview?'catalogue_wall_sculptures.xlsx':'previous-catalogue.xlsx')));
if(finalPreview){
 for(const [sheetName,range,name] of [['Platform Review','E4:H9','final-review.png'],['Wall Sculptures','BB3:BF9','final-platform-fields.png']]){
  await fs.writeFile(path.join(out,name),new Uint8Array(await(await book.render({sheetName,range,scale:1.2,format:'png'})).arrayBuffer()));
 }
 console.log(JSON.stringify({status:'FINAL_FILE_IMPORTED_AND_RENDERED'}));process.exit(0);
}
const finishRow=Number(plan.patches.find(p=>p.sheet==='Wall Sculptures'&&p.value==='Spiralfish Wave and Tide I - Bronze Finish')?.cell.match(/\d+/)[0]);
await fs.writeFile(path.join(out,'titles-before.png'),new Uint8Array(await(await book.render({sheetName:'Wall Sculptures',range:`AV${finishRow-1}:AV${finishRow+1}`,scale:1.5,format:'png'})).arrayBuffer()));
for(const p of plan.patches)book.worksheets.getItem(p.sheet).getRange(p.cell).values=[[p.value]];
const master=book.worksheets.getItem('Wall Sculptures');
const newRange=master.getRangeByIndexes(6,plan.first_added_column-1,182,plan.added_master_columns.length);
newRange.format={font:{name:'Calibri',size:11},verticalAlignment:'top',wrapText:true,columnWidth:32};
master.getRangeByIndexes(6,plan.first_added_column-1,1,plan.added_master_columns.length).format={fill:'#586F50',font:{name:'Calibri',size:11,bold:true,color:'#FFFFFF'},rowHeight:75};
for(const p of plan.new_master_cells){
 const cell=master.getRange(p.cell);
 cell.values=[[p.value]];
 if(p.kind==='header')cell.format={fill:'#586F50',font:{bold:true,color:'#FFFFFF'},wrapText:true};
 else if(typeof p.value==='number'){
   cell.format.numberFormat=/gbp|usd/.test(p.header||'')?'#,##0.00':'0.00';
   if(p.header==='fx_reference')cell.format.numberFormat='0.000000';
 }
}
for(const p of plan.new_master_cells)if(p.formula)master.getRange(p.cell).formulas=[[p.formula]];
master.getRange('BB3:BF4').format={font:{name:'Calibri',size:11},wrapText:true,rowHeight:58};
master.getRange('BB3:BF3').format={fill:'#586F50',font:{bold:true,color:'#FFFFFF'}};
for(const data of plan.new_sheets){
 const sheet=book.worksheets.add(data.name);sheet.showGridLines=false;
 sheet.getRange('A1').values=[[data.title]];
 sheet.getRange('A1').format={font:{name:'Calibri',size:16,bold:true},rowHeight:30};
 sheet.getRange('A2').values=[[data.note]];sheet.getRange('A2:H2').merge();
 sheet.getRange('A2:H2').format={font:{name:'Calibri',size:11},wrapText:true,rowHeight:48};
 sheet.getRangeByIndexes(3,0,1,data.headers.length).values=[data.headers];
 sheet.getRangeByIndexes(4,0,data.rows.length,data.headers.length).values=data.rows;
 sheet.getRangeByIndexes(3,0,data.rows.length+1,data.headers.length).format={font:{name:'Calibri',size:11},verticalAlignment:'top',wrapText:true,columnWidth:26,rowHeight:65};
 sheet.getRangeByIndexes(3,0,1,data.headers.length).format={fill:'#586F50',font:{bold:true,color:'#FFFFFF'},rowHeight:42};
 sheet.freezePanes.freezeRows(4);
 if(data.name==='Platform Review'){
   sheet.getRange('A:A').format.columnWidth=14;sheet.getRange('B:B').format.columnWidth=17;
   sheet.getRange('D:D').format.columnWidth=28;sheet.getRange('E:G').format.columnWidth=60;
   sheet.getRange('H:H').format.columnWidth=14;
   sheet.getRange(`H5:H${data.rows.length+4}`).conditionalFormats.add('containsText',{text:'High',format:{fill:'#FCE4D6',font:{color:'#9C0006',bold:true}}});
 }else{
   sheet.getRange('C:C').format.columnWidth=55;sheet.getRange('E:E').format.columnWidth=78;
 }
}
const sources=JSON.parse(await fs.readFile(path.join(out,'reference-sources.json'),'utf8'));
const review=book.worksheets.getItem('Platform Review');
review.getRange('J10:K16').values=[
 ['Reference','Source'],
 ['Currency conversion (2 November 2026)',sources.fx.url],
 ['Chairish international duties and fees',sources.chairish],
 ['eBay parcel eligibility',sources.ebay],
 ['Royal Mail online prices and limits',sources.royal_mail],
 ['UPS surcharge policy',sources.ups],
 ['US estimate scope','App planning budgets only. Measured packing, actual destination, duties/taxes, carrier discounts and artwork cover require a booking quote.']
];
review.getRange('J10:K16').format={font:{name:'Calibri',size:11},wrapText:true,verticalAlignment:'top',rowHeight:65};
review.getRange('J:J').format.columnWidth=35;review.getRange('K:K').format.columnWidth=90;
// Exercise the editable FX driver, then restore it before final verification.
const originalFx=master.getRange('BB4').values[0][0];
const trial=plan.new_master_cells.find(p=>p.header==='chairish_catalogue_price_usd'&&p.cell.endsWith('8'));
const trialGbp=plan.new_master_cells.find(p=>p.header==='chairish_catalogue_price_gbp'&&p.cell.endsWith('8')).value;
master.getRange('BB4').values=[[1.5]];await book.recalculate();
if(master.getRange(trial.cell).values[0][0]!==Math.round(trialGbp*1.5))throw Error('FX input did not recalculate the target price');
master.getRange('BB4').values=[[originalFx]];
await book.recalculate();
const formulaCells=plan.new_master_cells.filter(p=>p.formula);
const errors=[];
for(const p of formulaCells){
 const value=master.getRange(p.cell).values[0][0];
 if(typeof value!=='number'||Math.abs(value-p.value)>.011)errors.push({cell:p.cell,expected:p.value,value});
}
if(errors.length)throw Error('Calculated reconciliation mismatch: '+JSON.stringify(errors.slice(0,10)));
await fs.writeFile(path.join(out,'calculation-verification.json'),JSON.stringify({status:'PASS',formula_cells_checked:formulaCells.length},null,2));
for(const [sheetName,range,name] of [
 ['Wall Sculptures',`AV${finishRow-1}:AV${finishRow+1}`,'titles-after.png'],
 ['Wall Sculptures','BB3:BF9','platform-fields.png'],
 ['Platform Review','A4:D9','review-identities.png'],
 ['Platform Review','E4:H9','review-actions.png'],
 ['eBay Photo Links','A4:D8','ebay-photos.png']]){
 const image=await book.render({sheetName,range,scale:1.3,format:'png'});
 await fs.writeFile(path.join(out,name),new Uint8Array(await image.arrayBuffer()));
}
await fs.writeFile(path.join(out,'authored-inspection.ndjson'),(await book.inspect({kind:'region',sheetId:'Wall Sculptures',range:'BB3:BF9',maxChars:2500,tableMaxRows:7,tableMaxCols:5})).ndjson);
await(await SpreadsheetFile.exportXlsx(book)).save(path.join(out,'authored.xlsx'));
console.log(JSON.stringify({status:'AUTHORED',patched_cells:plan.patches.length,added_master_columns:plan.added_master_columns.length,formula_cells:formulaCells.length,new_sheets:plan.new_sheets.length}));
