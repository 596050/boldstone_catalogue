import fs from 'node:fs/promises';
import path from 'node:path';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const out=path.join(path.dirname(new URL(import.meta.url).pathname),'requirements-workbook');
const changes=JSON.parse(await fs.readFile(path.join(out,'patches.json'),'utf8'));
const book=await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(out,'previous-catalogue.xlsx')));
await fs.writeFile(path.join(out,'before.png'),new Uint8Array(await(await book.render({sheetName:'Wall Sculptures',range:'I7:K11',scale:1,format:'png'})).arrayBuffer()));
for(const p of changes.patches)book.worksheets.getItem(p.sheet).getRange(p.cell).values=[[p.value]];
for(const data of changes.new_sheets){
 const sheet=book.worksheets.add(data.name);sheet.showGridLines=false;
 sheet.getRange('A1').values=[[data.title]];sheet.getRange('A2').values=[[data.note]];
 sheet.getRangeByIndexes(3,0,1,data.headers.length).values=[data.headers];
 sheet.getRangeByIndexes(4,0,data.rows.length,data.headers.length).values=data.rows;
 sheet.getRangeByIndexes(0,0,data.rows.length+4,data.headers.length).format={font:{name:'Calibri',size:11},verticalAlignment:'top',wrapText:true,columnWidth:24,rowHeight:54};
 sheet.getRangeByIndexes(0,0,1,data.headers.length).format={fill:'#23372D',font:{bold:true,color:'#FFFFFF',size:18},rowHeight:32};
 sheet.getRangeByIndexes(3,0,1,data.headers.length).format={fill:'#586F50',font:{bold:true,color:'#FFFFFF'},rowHeight:52};
 sheet.getRange('A:A').format.columnWidth=23;sheet.getRange('B:B').format.columnWidth=37;
 sheet.getRange('A1:F1').merge();sheet.getRange('A2:F2').merge();
 if(data.name==='Channel Details'){
   sheet.getRange('J:N').format.columnWidth=72;
   sheet.getRangeByIndexes(4,0,data.rows.length,data.headers.length).format.rowHeight=170;
 }else{
   sheet.getRange('Y:AC').format.columnWidth=72;
   sheet.getRangeByIndexes(4,0,data.rows.length,data.headers.length).format.rowHeight=105;
 }
 sheet.freezePanes.freezeRows(4);
}
await book.recalculate();
for(const [name,range,file] of [['Wall Sculptures','I7:K11','after.png'],['Channel Details','A4:F8','channel-details.png'],['US Delivery Estimates','A4:K8','us-delivery.png']])
 await fs.writeFile(path.join(out,file),new Uint8Array(await(await book.render({sheetName:name,range,scale:1,format:'png'})).arrayBuffer()));
await(await SpreadsheetFile.exportXlsx(book)).save(path.join(out,'authored.xlsx'));
console.log(JSON.stringify({authored_cells:changes.patches.length,new_sheets:changes.new_sheets.length}));
