import fs from 'node:fs/promises';
import path from 'node:path';
import {FileBlob, SpreadsheetFile, Workbook} from '@oai/artifact-tool';

const out=path.dirname(new URL(import.meta.url).pathname);
const plan=JSON.parse(await fs.readFile(out+'/plan.json','utf8'));
const mode=process.argv[2]||'--build';
const final=mode==='--final';
if(mode==='--feed'){
 const feed=await Workbook.fromCSV(await fs.readFile(out+'/pinterest_wall_sculptures.csv','utf8'),{sheetName:'Products'});
 const sheet=feed.worksheets.getItem('Products');
 sheet.showGridLines=false;
 sheet.getRange('A1:AT177').format={font:{name:'Calibri',size:11},verticalAlignment:'top',columnWidth:25,rowHeight:36};
 sheet.getRange('A1:AT1').format={fill:'#586F50',font:{name:'Calibri',size:11,bold:true,color:'#FFFFFF'},wrapText:true,rowHeight:58};
 sheet.getRange('B1:B177').format.columnWidth=45;
 sheet.getRange('C1:C177').format.columnWidth=65;
 sheet.getRange('D1:E177').format.columnWidth=42;
 sheet.getRange('F1:G177').format.columnWidth=18;
 sheet.getRange('B2:C177').format.wrapText=true;
 sheet.getRange('A2:A177').format.numberFormat='@';
 sheet.freezePanes.freezeRows(1);
 sheet.tables.add('A1:AT177',true,'PinterestProducts');
 await feed.recalculate();
 const check=sheet.getRange('A1:AT177').values;
 for(let r=0;r<plan.public_feed_rows.length;r++)for(let c=0;c<plan.pinterest_feed_fields.length;c++){
  const want=plan.public_feed_rows[r][plan.pinterest_feed_fields[c]]||'';
  const got=check[r+1][c]??'';
  if(String(got)!==String(want))throw Error(`Feed readback ${r+2},${c+1}: ${got}`);
 }
 const blob=await feed.render({sheetName:'Products',range:'A1:G5',scale:1,format:'png'});
 await fs.writeFile(out+'/pinterest-feed-preview.png',new Uint8Array(await blob.arrayBuffer()));
 await(await SpreadsheetFile.exportXlsx(feed)).save(out+'/pinterest_wall_sculptures.xlsx');
 console.log(JSON.stringify({status:'FEED_AUTHORED',rows:176,columns:46}));
 process.exit(0);
}
const book=await SpreadsheetFile.importXlsx(await FileBlob.load(out+(final?'/catalogue_wall_sculptures.xlsx':mode==='--identifiers'?'/authored.xlsx':'/previous-catalogue.xlsx')));
const master=book.worksheets.getItem('Wall Sculptures');
async function render(p,prefix){
 const blob=await book.render({sheetName:'Wall Sculptures',range:p.range,scale:1,format:'png'});
 await fs.writeFile(out+'/'+prefix+'-'+p.name+'.png',new Uint8Array(await blob.arrayBuffer()));
}
if(mode==='--before'){
 for(const p of plan.previews.filter(p=>p.name==='faire'))await render(p,'before');
 console.log(JSON.stringify({status:'SOURCE_RENDERED'}));process.exit(0);
}
if(!final){
 if(mode==='--identifiers'){
  master.getRange(plan.headers.pinterest_mpn+'8:'+plan.headers.pinterest_mpn+'188').clear({applyTo:'contents'});
 }else{
 master.getRangeByIndexes(6,plan.first_added_column-1,182,plan.new_headers.length).format={font:{name:'Calibri',size:11},verticalAlignment:'top',wrapText:true,columnWidth:32};
 const groups=new Map();
 for(const p of plan.patches){
  const col=p.cell.replace(/\d/g,'');
  if(!groups.has(col))groups.set(col,[]);
  groups.get(col).push(p);
 }
 for(const [col,patches]of groups){
  patches.sort((a,b)=>Number(a.cell.replace(/\D/g,''))-Number(b.cell.replace(/\D/g,'')));
  for(const p of patches){
   const cell=master.getRange(p.cell);cell.values=[[p.value]];
   if(p.format==='header')cell.format={fill:'#586F50',font:{name:'Calibri',size:11,bold:true,color:'#FFFFFF'},wrapText:true,rowHeight:75};
   else if(p.format==='0.00')cell.format.numberFormat='0.00';
   else cell.format.numberFormat='@';
  }
 }
 }
 await book.recalculate();
 const readback=[];
 for(const p of plan.patches){
  const raw=master.getRange(p.cell).values[0][0];
  const actual=raw instanceof Date?raw.toISOString():raw;
  if(typeof p.value==='number'?typeof actual!=='number'||Math.abs(actual-p.value)>1e-6:actual!==p.value)throw Error('Master readback mismatch '+p.cell+' '+String(actual));
  readback.push({cell:p.cell,value:actual});
 }
 await fs.writeFile(out+'/authored-readback.json',JSON.stringify(readback));
 const errors=await book.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!',options:{useRegex:true,maxResults:30},summary:'Formula error check after channel refresh',maxChars:3000});
 await fs.writeFile(out+'/formula-error-scan.ndjson',errors.ndjson);
 await(await SpreadsheetFile.exportXlsx(book)).save(out+'/authored.xlsx');
}
for(const p of plan.previews)await render(p,final?'final':'after');
console.log(JSON.stringify({status:final?'FINAL_RENDERED':'MASTER_AUTHORED',cells:plan.patches.length}));
