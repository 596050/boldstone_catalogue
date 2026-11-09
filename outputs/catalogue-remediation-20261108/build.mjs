import fs from 'node:fs/promises';
import path from 'node:path';
import {FileBlob, SpreadsheetFile} from '@oai/artifact-tool';

const out=path.dirname(new URL(import.meta.url).pathname);
const mode=process.argv[2]||'--edit';
const plan=JSON.parse(await fs.readFile(out+'/plan.json','utf8'));
const final=mode==='--final'||mode==='--checks';
const book=await SpreadsheetFile.importXlsx(await FileBlob.load(out+(final?'/catalogue_wall_sculptures.xlsx':'/previous-catalogue.xlsx')));
const sheet=book.worksheets.getItem('Wall Sculptures');
const col=n=>{let s='';for(;n;n=Math.floor((n-1)/26))s=String.fromCharCode(65+(n-1)%26)+s;return s;};
if(mode==='--checks'){
  const num=cell=>Number(sheet.getRange(cell).values[0][0]);
  const eq=(a,b,label)=>{if(Math.abs(a-b)>0.000001)throw Error(label+': '+a+' vs '+b);};
  const payout=num('QI4'),labour=num('AL8'),net=num('AEF8'),cost=num('BA8'),profit=num('AEG8');
  sheet.getRange('AL8').values=[[10]];await book.recalculate();
  eq(num('AEF8'),net,'Native receipt must not change with labour');
  eq(num('BA8'),cost+10,'Total includes labour once');
  eq(num('AEG8'),Math.round((profit-10)*100)/100,'Profit includes labour once');
  sheet.getRange('AL8').values=[[labour]];
  sheet.getRange('QI4').values=[[0]];await book.recalculate();
  const expected=Math.floor((num('UX8')*(1-num('QG4')*(1+num('QC4')))-num('QJ4')*(1+num('QC4'))-num('QD4'))*100+0.000001)/100;
  eq(num('AEF8'),expected,'Zero optional payout fee');
  sheet.getRange('QI4').values=[[payout]];await book.recalculate();
  eq(num('AEF8'),net,'Restored native receipt');eq(num('AEG8'),profit,'Restored profit');
  const errors=await book.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:20},summary:'final formula error scan',maxChars:2500});
  await fs.writeFile(out+'/formula-error-scan.json',JSON.stringify(errors,null,2));
  await fs.writeFile(out+'/sensitivity-verification.json',JSON.stringify({status:'PASS',checks:['labour included once','zero payout fee','original values restored'],persistedChanges:false},null,2));
  console.log(JSON.stringify({status:'PASS_SENSITIVITY',formulaErrorScan:errors.ndjson}));
  process.exit(0);
}
if(mode==='--before'){
  const png=await book.render({sheetName:'Wall Sculptures',range:'QV7:QZ11',scale:1,format:'png'});
  await fs.writeFile(out+'/before-faire.png',new Uint8Array(await png.arrayBuffer()));
  console.log(JSON.stringify({status:'BASELINE_RENDERED'}));
  process.exit(0);
}
if(!final){
  const added=Array.from({length:182},()=>Array(plan.new_headers.length).fill(''));
  const index=address=>{const m=address.match(/^([A-Z]+)(\d+)$/);let c=0;for(const x of m[1])c=c*26+x.charCodeAt(0)-64;return {row:Number(m[2]),column:c};};
  for(const p of plan.patches){const q=index(p.cell);if(q.column>=plan.first_added_column)added[q.row-7][q.column-plan.first_added_column]=p.value;}
  const first=col(plan.first_added_column),last=col(plan.last_added_column);
  sheet.getRange(first+'7:'+last+'188').values=added;
  const area=sheet.getRange(first+'7:'+last+'188');
  area.format={font:{name:'Calibri',size:11},wrapText:true,verticalAlignment:'top',columnWidth:32};
  sheet.getRange(first+'7:'+last+'7').format={fill:'#586F50',font:{name:'Calibri',size:11,bold:true,color:'#FFFFFF'},wrapText:true};
  for(const p of plan.patches){
    if(p.formula)sheet.getRange(p.cell).formulas=[['='+p.formula]];
    else if(index(p.cell).column<plan.first_added_column)sheet.getRange(p.cell).values=[[p.value]];
    if(p.style==='money')sheet.getRange(p.cell).format.numberFormat='"£"#,##0.00';
    else if(p.style==='ratio')sheet.getRange(p.cell).format.numberFormat='0.00';
    else if(p.style==='integer')sheet.getRange(p.cell).format.numberFormat='0';
    else if(p.style==='utc')sheet.getRange(p.cell).format.numberFormat='yyyy-mm-dd hh:mm:ss';
  }
  await book.recalculate();
  const readback=[];
  for(const p of plan.patches){
    const v=sheet.getRange(p.cell).values[0][0];
    const actual=v instanceof Date?(v.getTime()-Date.UTC(1899,11,30))/86400000:v;
    const same=typeof p.value==='number'?Math.abs(actual-p.value)<0.000001:String(actual??'')===String(p.value??'');
    if(!same)throw Error('Authoring readback mismatch at '+p.cell+': '+actual+' vs '+p.value);
    readback.push({cell:p.cell,value:actual,formula:p.formula||null});
  }
  await fs.writeFile(out+'/authored-readback.json',JSON.stringify(readback,null,2));
  await(await SpreadsheetFile.exportXlsx(book)).save(out+'/authored.xlsx');
}
for(const p of plan.previews){
  const png=await book.render({sheetName:'Wall Sculptures',range:p.range,scale:1,format:'png'});
  await fs.writeFile(out+'/'+(final?'final':'after')+'-'+p.name+'.png',new Uint8Array(await png.arrayBuffer()));
}
console.log(JSON.stringify({status:final?'FINAL_RENDERED':'AUTHORED',patchedCells:plan.patches.length}));
