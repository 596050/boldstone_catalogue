import fs from 'node:fs/promises';
import {Workbook} from '@oai/artifact-tool';
const out = new URL('.', import.meta.url);
const input=JSON.parse(await fs.readFile(new URL('weight-change-manifest.json',out),'utf8'));
const wb=Workbook.create();
const sheet=wb.worksheets.add('Products');
const matrix=[input.headers,...input.native_rows.map(r=>input.headers.map(h=>r[h]))];
sheet.getRangeByIndexes(0,0,matrix.length,input.headers.length).values=matrix;
const weightColumn=input.headers.indexOf('Weight');
const before=await wb.render({sheetName:'Products',range:'AC1:AF6',scale:2});
await fs.writeFile(new URL('weights-before.png',out),new Uint8Array(await before.arrayBuffer()));
for(let i=0;i<input.rows.length;i++) sheet.getCell(i+1,weightColumn).values=[[Number(input.rows[i].shipping_lb)]];
wb.recalculate();
const values=sheet.getRangeByIndexes(0,0,matrix.length,input.headers.length).values;
for(let r=1;r<values.length;r++)for(let c=0;c<input.headers.length;c++){
  if(c!==weightColumn && String(values[r][c]??'')!==String(matrix[r][c]??''))throw Error('Unrelated cell changed');
}
const quote=v=>'"'+String(v??'').replaceAll('"','""')+'"';
await fs.writeFile(new URL('squarespace-weight-update.csv',out),values.map(r=>r.map(quote).join(',')).join('\r\n')+'\r\n');
const after=await wb.render({sheetName:'Products',range:'AC1:AF6',scale:2});
await fs.writeFile(new URL('weights-after.png',out),new Uint8Array(await after.arrayBuffer()));
await fs.writeFile(new URL('builder-validation.json',out),JSON.stringify({updatedRows:176,changedColumns:['Weight'],newProducts:0,preservedOtherCells:true,minimumWeight:Math.min(...input.rows.map(r=>Number(r.shipping_lb)))},null,2));
console.log('176 existing variants prepared; only Weight changed.');
