import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {FileBlob, SpreadsheetFile} from '@oai/artifact-tool';

const h=path.dirname(fileURLToPath(import.meta.url));
const {plans}=JSON.parse(await fs.readFile(path.join(h,'workbook-edit-plan.json'),'utf8'));
await fs.mkdir(path.join(h,'previews'),{recursive:true});
const receipts=[];
for(const plan of plans){
  const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(plan.source));
  for(const e of plan.edits){
    const range=wb.worksheets.getItem(e.sheet).getRange(e.cell);
    if(e.before?.[0]==='formula'){
      const actual=range.formulas[0][0]||'';
      if(actual.replace(/^=/,'')!==e.before[1])throw new Error('Formula input drift '+e.sheet+'!'+e.cell);
    }else{
      const value=range.values[0][0]??'';
      const expected=e.before?.[1]??'';
      if(String(value)!==String(expected))throw new Error('Value input drift '+e.sheet+'!'+e.cell);
    }
  }
  for(const e of plan.edits){
    const range=wb.worksheets.getItem(e.sheet).getRange(e.cell);
    if(e.formula!==undefined)range.formulas=[[e.formula]];
    else range.values=[[e.value]];
  }
  if(plan.key==='comprehensive_workbook')wb.worksheets.getItem('Overview').getRange('A7:C7').format.rowHeight=42;
  wb.recalculate();
  for(const e of plan.expected){
    const actual=wb.worksheets.getItem(e.sheet).getRange(e.cell).values[0][0];
    if(actual!==e.value)throw new Error('Result drift '+e.sheet+'!'+e.cell+': '+actual);
  }
  const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:20},maxChars:2400});
  await fs.writeFile(path.join(h,plan.key+'-formula-errors.ndjson'),errors.ndjson);
  const views=[];
  for(const[sheetName,range,label]of plan.previews){
    const blob=await wb.render({sheetName,range,scale:1.3,format:'png'});
    const output=path.join(h,'previews',label+'.png');
    await fs.writeFile(output,new Uint8Array(await blob.arrayBuffer()));
    views.push({sheetName,range,path:output});
  }
  await(await SpreadsheetFile.exportXlsx(wb)).save(plan.output);
  receipts.push({key:plan.key,output:plan.output,authored_edits:plan.edits.length,recalculated:true,previews:views});
  await fs.writeFile(path.join(h,'artifact-authoring-receipt.json'),JSON.stringify({status:'EXPORTED_FOR_INDEPENDENT_VERIFICATION',workbooks:receipts},null,2));
  console.log(JSON.stringify({key:plan.key,status:'EXPORTED',edits:plan.edits.length}));
}
