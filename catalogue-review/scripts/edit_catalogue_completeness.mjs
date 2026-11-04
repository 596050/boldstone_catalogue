import fs from 'node:fs/promises';
import path from 'node:path';
import {FileBlob, SpreadsheetFile} from '@oai/artifact-tool';

const out=path.resolve(process.argv[2]);
const plan=JSON.parse(await fs.readFile(path.join(out,'completeness-plan.json'),'utf8'));
const preview=process.argv.includes('--preview'), final=process.argv.includes('--verify-final'), amend=process.argv.includes('--amend');
const book=await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(out,final?'catalogue_wall_sculptures.xlsx':amend?'authored.xlsx':'previous-catalogue.xlsx')));
const master=book.worksheets.getItem('Wall Sculptures');
const col=a=>a.match(/^[A-Z]+/)[0], row=a=>Number(a.match(/\d+/)[0]);
async function render(sheet,range,name){
 const blob=await book.render({sheetName:sheet,range,scale:1.1,format:'png'});
 await fs.writeFile(path.join(out,name+'.png'),new Uint8Array(await blob.arrayBuffer()));
}
if(preview){
 await render('Wall Sculptures','JD7:JI10','before-pricing');
 console.log((await book.inspect({kind:'region',sheetId:'Wall Sculptures',range:'JD7:JI9',maxChars:1800,tableMaxRows:3,tableMaxCols:6})).ndjson);
 process.exit(0);
}
if(!final){
 const newRegion=master.getRangeByIndexes(6,plan.first_master_column-1,182,plan.added_master_columns.length);
 newRegion.format={font:{name:'Calibri',size:11},wrapText:true,verticalAlignment:'top',columnWidth:32};
 master.getRangeByIndexes(6,plan.first_master_column-1,1,plan.added_master_columns.length).format={fill:'#586F50',font:{name:'Calibri',size:11,bold:true,color:'#FFFFFF'},rowHeight:75};
 const groups=new Map();
 for(const p of plan.patches){
  const key=JSON.stringify([p.sheet,col(p.cell),p.formula!==null]);
  if(!groups.has(key))groups.set(key,[]);groups.get(key).push(p);
 }
 let runs=0;
 for(const [key,patches] of groups){
  const [sheet,c,formula]=JSON.parse(key), sh=book.worksheets.getItem(sheet);
  patches.sort((a,b)=>row(a.cell)-row(b.cell));
  for(let i=0;i<patches.length;){
   let end=i+1;
   while(end<patches.length && row(patches[end].cell)===row(patches[end-1].cell)+1)end++;
   const part=patches.slice(i,end), range=sh.getRange(`${c}${row(part[0].cell)}:${c}${row(part.at(-1).cell)}`);
   if(formula)range.formulas=part.map(p=>[p.formula]);else range.values=part.map(p=>[p.value]);
   i=end;runs++;
  }
 }
 console.log(JSON.stringify({stage:'values-written',runs,cells:plan.patches.length}));
 // Format each numeric column as a block; all observations retain their native
 // styles in the final preservation pass.
 const formats=new Map();
 for(const p of plan.patches){
  if(p.format && p.format!=='header' && row(p.cell)>=8 && p.sheet==='Wall Sculptures')formats.set(col(p.cell),p.format);
  else if(p.format==='header')book.worksheets.getItem(p.sheet).getRange(p.cell).format={fill:'#586F50',font:{name:'Calibri',size:11,bold:true,color:'#FFFFFF'},wrapText:true,verticalAlignment:'top'};
 }
 for(const [c,fmt] of formats)master.getRange(`${c}8:${c}188`).format.numberFormat=fmt;
 master.getRange('BM4:BN4').format.numberFormat='0%';
 for(const key of ['saatchi_description','saatchi_unverified_information','saatchi_shipping_basis','saatchi_price_basis','catalogue_noninferable_fields']){
  const c=plan.headers[key], ix=[...c].reduce((n,ch)=>n*26+ch.charCodeAt(0)-64,0),width=key==='saatchi_description'?90:65;
  master.getRange(`${c}:${c}`).format.columnWidth=width;
  if(!plan.column_format_updates.some(p=>p.sheet==='Wall Sculptures'&&p.first===ix))plan.column_format_updates.push({sheet:'Wall Sculptures',first:ix,last:ix,width});
 }
 master.getRange('A8:PN188').format.rowHeight=210;
 for(let r=8;r<=188;r++)if(!plan.row_format_updates.some(p=>p.sheet==='Wall Sculptures'&&p.row===r))plan.row_format_updates.push({sheet:'Wall Sculptures',row:r,height:210});
 const review=book.worksheets.getItem('Platform Review');
 review.getRange(`N4:U${plan.audit_last_row}`).format={font:{name:'Calibri',size:11},wrapText:true,verticalAlignment:'top',rowHeight:76};
 review.getRange('N4:U4').format={fill:'#586F50',font:{bold:true,color:'#FFFFFF'},rowHeight:34};
 for(const c of plan.column_format_updates.filter(p=>p.sheet==='Platform Review'))review.getRangeByIndexes(0,c.first-1,plan.audit_last_row,c.last-c.first+1).format.columnWidth=c.width;
 // Native row heights are explicit, because preserving worksheet features also
 // preserves the original row records.
 for(let r=5;r<=plan.audit_last_row;r++)plan.row_format_updates.push({sheet:'Platform Review',row:r,height:76});
 await fs.writeFile(path.join(out,'completeness-plan.json'),JSON.stringify(plan,null,2)+'\n');
 await book.recalculate();
 // Read blocks once, and verify every authoring instruction after calculation.
 const cache=new Map(), columns=new Map();
 for(const p of plan.patches){const key=JSON.stringify([p.sheet,col(p.cell)]);if(!columns.has(key))columns.set(key,[]);columns.get(key).push(p);}
 for(const [key,patches] of columns){
  const [s,c]=JSON.parse(key), lo=Math.min(...patches.map(p=>row(p.cell))),hi=Math.max(...patches.map(p=>row(p.cell)));
  cache.set(JSON.stringify([s,c]),{lo,values:book.worksheets.getItem(s).getRange(`${c}${lo}:${c}${hi}`).values});
 }
 const errors=[];
 for(const p of plan.patches){
  const block=cache.get(JSON.stringify([p.sheet,col(p.cell)])),got=block.values[row(p.cell)-block.lo][0],exp=p.value;
  if(got!==exp && !(got===null && (exp===null||exp==='')) && !(typeof got==='number'&&typeof exp==='number'&&Math.abs(got-exp)<1e-7))errors.push({sheet:p.sheet,cell:p.cell,expected:exp,got});
 }
 if(errors.length)throw Error(JSON.stringify(errors.slice(0,12)));
 // Exercise editable rate and FX dependencies in memory, then restore.
 const h=plan.headers, r=10, ref=k=>h[k]+r, ask=master.getRange(ref('saatchi_asking_price_usd'));
 const before=ask.values[0][0];master.getRange('BN4').values=[[0.25]];await book.recalculate();
 const discounted=ask.values[0][0];if(!(discounted>before))throw Error('Saatchi discount driver did not recalculate');
 master.getRange('BN4').values=[[0.2]];master.getRange('BB4').values=[[1.5]];await book.recalculate();
 const fxChanged=ask.values[0][0];if(!(fxChanged>before))throw Error('FX driver did not recalculate');
 master.getRange('BB4').values=[[1.3419478344101459]];await book.recalculate();
 if(ask.values[0][0]!==before)throw Error('Pricing drivers not restored');
 await fs.writeFile(path.join(out,'artifact-import-verification.json'),JSON.stringify({status:'PASS',patches_verified:plan.patches.length,discount_driver_test:{before,discounted,restored:true},fx_driver_test:{fxChanged,restored:true}},null,2)+'\n');
 await(await SpreadsheetFile.exportXlsx(book)).save(path.join(out,'authored.xlsx'));
 console.log(JSON.stringify({stage:'authored-and-checked',patches:plan.patches.length}));
}
const h=plan.headers;
await render('Wall Sculptures',`${h.saatchi_catalogue_title}7:${h.saatchi_description_characters}10`,final?'final-copy':'copy');
await render('Wall Sculptures',`${h.saatchi_net_target_usd}7:${h.saatchi_net_after_discount_gbp}10`,final?'final-prices':'prices');
await render('Platform Review','N4:U8',final?'final-audit':'audit');
await render('US Delivery Estimates','U4:X10',final?'final-shipping':'shipping');
console.log(JSON.stringify({status:final?'FINAL_IMPORTED_AND_RENDERED':'AUTHORED',sheets:12,new_fields:plan.added_master_columns.length}));
