import fs from 'node:fs/promises';
import path from 'node:path';
import {FileBlob, SpreadsheetFile} from '@oai/artifact-tool';

const out=path.dirname(new URL(import.meta.url).pathname);
const plan=JSON.parse(await fs.readFile(out+'/plan.json','utf8'));
const mode=process.argv[2]||'author';
const book=await SpreadsheetFile.importXlsx(await FileBlob.load(out+(mode==='final'?'/catalogue_wall_sculptures.xlsx':'/previous-catalogue.xlsx')));
const sheet=book.worksheets.getItem('Wall Sculptures');
const col=n=>{let s='';for(;n;n=Math.floor((n-1)/26))s=String.fromCharCode(65+(n-1)%26)+s;return s;};
const index=a=>{let m=a.match(/^([A-Z]+)(\d+)$/),c=0;for(let x of m[1])c=c*26+x.charCodeAt(0)-64;return {row:+m[2],column:c};};
if(mode==='before'){
 const im=await book.render({sheetName:'Wall Sculptures',range:'G7:J12',scale:1.3,format:'png'});
 await fs.writeFile(out+'/before-existing-price-format.png',new Uint8Array(await im.arrayBuffer()));
 console.log(JSON.stringify({status:'SOURCE_RENDERED'}));
 process.exit(0);
}
if(mode==='author'){
 const matrix=Array.from({length:186},()=>Array(plan.new_headers.length).fill(''));
 for(const p of plan.patches){const q=index(p.cell);matrix[q.row-3][q.column-plan.first_added_column]=p.value;}
 const first=col(plan.first_added_column),last=col(plan.last_added_column);
 sheet.getRange(first+'3:'+last+'188').values=matrix;
 const body=sheet.getRange(first+'7:'+last+'188');
 body.format={font:{name:'Calibri',size:11},wrapText:true,verticalAlignment:'top',columnWidth:32};
 sheet.getRange(first+'7:'+last+'7').format={fill:'#586F50',font:{name:'Calibri',size:11,bold:true,color:'#FFFFFF'},wrapText:true};
 for(const p of plan.patches){
  const c=sheet.getRange(p.cell);
  if(p.formula)c.formulas=[[p.formula]];
  const formats={gbp:'"£"#,##0.00',eur:'"€"#,##0.00',percentage:'0.0%',ratio:'0.000000',integer:'0',decimal:'0.00',text:'@',utc:'yyyy-mm-dd hh:mm:ss "UTC"'};
  if(formats[p.style])c.format.numberFormat=formats[p.style];
  if(p.style==='header')c.format={fill:'#586F50',font:{name:'Calibri',size:11,bold:true,color:'#FFFFFF'},wrapText:true};
 }
 // Recalculate real formulas, exercise the editable uplift and shared FX driver,
 // then restore both before exporting.
 book.recalculate();
 const priceCol=col(plan.first_added_column+1),eurCol=col(plan.first_added_column+2),upliftCol=col(plan.first_added_column),fxCol=col(plan.first_added_column+4);
 const base=sheet.getRange('H10').values[0][0];
 sheet.getRange(upliftCol+'10').values=[[125]];
 book.recalculate();
 if(Math.abs(sheet.getRange(priceCol+'10').values[0][0]-(base+125))>.001)throw Error('Uplift does not update Catawiki target');
 if(sheet.getRange('H10').values[0][0]!==base)throw Error('Core price changed');
 sheet.getRange(upliftCol+'10').values=[[100]];
 const fx=sheet.getRange(fxCol+'4').values[0][0];
 sheet.getRange(fxCol+'4').values=[[.8]];
 book.recalculate();
 if(sheet.getRange(eurCol+'10').values[0][0]!==Math.ceil((base+100)/.8))throw Error('Shared FX does not update EUR target');
 sheet.getRange(fxCol+'4').values=[[fx]];
 book.recalculate();
 const readback=[];
 for(const p of plan.patches){
  const raw=sheet.getRange(p.cell).values[0][0];
  const v=raw instanceof Date?(raw.getTime()-Date.UTC(1899,11,30))/86400000:raw;
  const same=typeof p.value==='number'?typeof v==='number'&&Math.abs(v-p.value)<.000001:String(v??'')===String(p.value??'');
  if(!same)throw Error('Artifact readback mismatch '+p.cell+': '+JSON.stringify({actual:v,expected:p.value}));
  readback.push({cell:p.cell,value:v});
 }
 await fs.writeFile(out+'/authored-readback.json',JSON.stringify({status:'PASS',uplift_input_recalculated:true,fx_input_recalculated:true,core_price_preserved:true,cells:readback}));
 await(await SpreadsheetFile.exportXlsx(book)).save(out+'/authored.xlsx');
}
for(const p of plan.previews){
 const im=await book.render({sheetName:'Wall Sculptures',range:p.range,scale:1.1,format:'png'});
 await fs.writeFile(out+'/'+mode+'-'+p.name+'.png',new Uint8Array(await im.arrayBuffer()));
}
await fs.writeFile(out+'/'+mode+'-inspection.ndjson',(await book.inspect({kind:'region',sheetId:'Wall Sculptures',range:plan.previews[0].range,maxChars:2500,tableMaxRows:7,tableMaxCols:3})).ndjson);
console.log(JSON.stringify({status:mode==='author'?'AUTHORED_AND_FORMULAS_CHECKED':'FINAL_RENDERED',patches:plan.patches.length,columns:plan.new_headers.length}));
