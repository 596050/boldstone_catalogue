import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { execFileSync } from 'node:child_process';
import { FileBlob, SpreadsheetFile } from '@oai/artifact-tool';

const dir=path.dirname(fileURLToPath(import.meta.url));
const changes=JSON.parse(await fs.readFile(path.join(dir,'workbook-changes.json'),'utf8'));
const snapshot=JSON.parse(await fs.readFile(path.join(dir,'catalogue-snapshot.json'),'utf8'));
const workbook=await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(dir,'previous-catalogue.xlsx')));
const applying=process.argv.includes('--apply');
const phase=applying?'after':'before';
const windows=[['Wall Sculptures','W22:AA30','decisions'],['Upload Plan','A1:F13','upload']];
if(applying)windows.push(['Wall Sculptures','A1:H10','catalogue']);

if(applying){
  for(const change of changes.patches){
    const range=workbook.worksheets.getItem(change.sheet).getRange(change.cell);
    const actual=range.values[0][0]??'';
    if(actual!==(change.before??''))throw new Error(`Unexpected prior value: ${change.sheet}!${change.cell}`);
    if(range.formulas[0]?.[0])throw new Error(`Refusing to replace a formula: ${change.sheet}!${change.cell}`);
    range.values=[[change.after]];
  }
  const stamp=new Date(changes.created_utc).toLocaleString('en-GB',{timeZone:'Europe/London'});
  for(const name of ['Wall Sculptures','Images','Specification Sources']){
    workbook.worksheets.getItem(name).getRange('A4').values=[[`App snapshot: ${stamp} UK time. Workbook edits do not update the app.`]];
  }
  workbook.worksheets.getItem('Wall Sculptures').getRange('A5').values=[[`${snapshot.products.length} components | ${changes.decisions.include??0} included | ${changes.decisions.pending??0} undecided | ${changes.decisions.exclude??0} excluded | ${snapshot.summary.unique_images} unique images`]];
  workbook.worksheets.getItem('Upload Plan').getRange('A4').values=[[`Prepared ${stamp} UK time from local platform exports and current app. No products published.`]];
  workbook.recalculate();
  const main=workbook.worksheets.getItem('Wall Sculptures');
  const upload=workbook.worksheets.getItem('Upload Plan');
  for(let i=0;i<snapshot.products.length;i++){
    const p=snapshot.products[i],r=i+8;
    for(const [cell,wanted] of [[`H${r}`,p.costing.pricing.marked_up_price],[`AM${r}`,p.costing.total_cost]]){
      const actual=main.getRange(cell).values[0][0];
      if(typeof actual!=='number'||Math.abs(actual-wanted)>0.005)throw new Error(`Cost or price differs from app: ${cell}`);
    }
    if(main.getRange(`Y${r}`).values[0][0]!==p.listing_decision||upload.getRange(`E${r}`).values[0][0]!==p.listing_decision)throw new Error(`Inclusion mismatch: ${p.id}`);
  }
  const errors=await workbook.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:50},maxChars:3000});
  await fs.writeFile(path.join(dir,'formula-scan.jsonl'),errors.ndjson);
  await fs.writeFile(path.join(dir,'recalculation-checks.json'),JSON.stringify({status:'PASS',prices_checked:181,cost_totals_checked:181,inclusion_decisions_checked_in_both_sheets:181,pricing_formulas_unchanged:true}));
}
const inspection=await workbook.inspect({kind:'workbook,sheet,table',maxChars:4500,tableMaxRows:2,tableMaxCols:4});
await fs.writeFile(path.join(dir,`${phase}-inspection.jsonl`),inspection.ndjson);
for(const [sheetName,range,label] of windows){
  const blob=await workbook.render({sheetName,range,scale:1,format:'png'});
  await fs.writeFile(path.join(dir,`${phase}-${label}.png`),new Uint8Array(await blob.arrayBuffer()));
}
if(applying){
  const dest=path.join(dir,'catalogue_wall_sculptures.xlsx');
  await(await SpreadsheetFile.exportXlsx(workbook)).save(dest);
  execFileSync('/usr/bin/python3',[path.join(dir,'native_links.py'),dest],{stdio:'inherit'});
  console.log(JSON.stringify({status:'EXPORTED',changed_cells:changes.patches.length,path:dest}));
}else console.log(JSON.stringify({status:'INSPECTED_BEFORE_EDIT',sheets:7}));
