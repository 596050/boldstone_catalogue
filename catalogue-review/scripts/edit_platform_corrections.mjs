import fs from 'node:fs/promises';
import path from 'node:path';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const out=path.resolve(process.argv[2]);
const plan=JSON.parse(await fs.readFile(path.join(out,'corrections-plan.json'),'utf8'));
const final=process.argv.includes('--verify-final');
const book=await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(out,final?'catalogue_wall_sculptures.xlsx':'previous-catalogue.xlsx')));
const master=book.worksheets.getItem('Wall Sculptures');
const firstNew=Math.min(...plan.added_master_columns.map(k=>columnIndex(plan.headers[k])));
function columnIndex(s){return [...s].reduce((n,c)=>n*26+c.charCodeAt(0)-64,0);}
const first=plan.headers.chairish_net_target_usd;
const last=plan.headers.chairish_asking_price_usd;
if(!final){
 await fs.writeFile(path.join(out,'before.png'),new Uint8Array(await(await book.render({sheetName:'Wall Sculptures',range:'BB3:BF9',scale:1.1,format:'png'})).arrayBuffer()));
 const newRange=master.getRangeByIndexes(6,firstNew-1,182,plan.last_master_column-firstNew+1);
 newRange.format={font:{name:'Calibri',size:11},wrapText:true,verticalAlignment:'top',columnWidth:32};
 master.getRangeByIndexes(6,firstNew-1,1,plan.last_master_column-firstNew+1).format={fill:'#586F50',font:{name:'Calibri',size:11,bold:true,color:'#FFFFFF'},rowHeight:75};
 for(const p of plan.patches){
  const cell=book.worksheets.getItem(p.sheet).getRange(p.cell);
  if(p.value===null)cell.clear({applyTo:'contents'});else cell.values=[[p.value]];
  if(p.format==='header')cell.format={fill:'#586F50',font:{name:'Calibri',size:11,bold:true,color:'#FFFFFF'},wrapText:true};
  else if(p.format&&p.format!=='text')cell.format.numberFormat=p.format;
 }
 master.getRange('BG4:BJ4').format.font={color:'#0000FF'};
 master.getRange('BG3:BL4').format.wrapText=true;
 for(const p of plan.patches)if(p.formula)book.worksheets.getItem(p.sheet).getRange(p.cell).formulas=[[p.formula]];
 // Exercise meaningful pricing drivers, including a fee and a deeper discount.
 const r=8;const cell=plan.headers.chairish_asking_price_usd+r;
 const gbp=Number(master.getRange('H8').values[0][0]);
 const expected=(fx,discount,commission,fee)=>Math.ceil(Math.ceil((Math.ceil(gbp*fx)+fee)/(1-commission))/(1-discount));
 for(const [fx,discount,commission,fee] of [[1.5,.4,.4,0],[1.5,.5,.4,3],[1.5,.4,.3,0]]){
  master.getRange('BB4').values=[[fx]];master.getRange('BG4').values=[[discount]];master.getRange('BH4').values=[[commission]];master.getRange('BJ4').values=[[fee]];
  await book.recalculate();
  if(master.getRange(cell).values[0][0]!==expected(fx,discount,commission,fee))throw Error('Pricing driver failed '+cell);
 }
 master.getRange('BB4').values=[[1.3419478344101459]];master.getRange('BG4').values=[[.4]];master.getRange('BH4').values=[[.4]];master.getRange('BJ4').values=[[0]];
 await book.recalculate();
 const failures=[];
 for(const p of plan.patches){
  if(!p.formula)continue;
  const got=book.worksheets.getItem(p.sheet).getRange(p.cell).values[0][0];
  if(typeof got!=='number'||Math.abs(got-p.value)>.011)failures.push({cell:p.cell,got,expected:p.value});
 }
 if(failures.length)throw Error(JSON.stringify(failures.slice(0,15)));
 await fs.writeFile(path.join(out,'calculation-verification.json'),JSON.stringify({status:'PASS',formula_cells_checked:plan.patches.filter(p=>p.formula).length,fx_discount_commission_and_additional_fee_recalculation:'PASS'},null,2));
 await(await SpreadsheetFile.exportXlsx(book)).save(path.join(out,'authored.xlsx'));
}
for(const [sheetName,range,name] of [
 ['Wall Sculptures','BG3:BJ4','pricing-inputs.png'],
 ['Wall Sculptures',`${first}7:${last}10`,'chairish-pricing.png'],
 ['Platform Review','E4:H8','review-actions.png'],
 ['eBay Photo Links','A4:D7','individual-photos.png']]){
 await fs.writeFile(path.join(out,(final?'final-':'')+name),new Uint8Array(await(await book.render({sheetName,range,scale:1.25,format:'png'})).arrayBuffer()));
}
console.log(JSON.stringify({status:final?'FINAL_IMPORTED_AND_RENDERED':'AUTHORED',patches:plan.patches.length}));
