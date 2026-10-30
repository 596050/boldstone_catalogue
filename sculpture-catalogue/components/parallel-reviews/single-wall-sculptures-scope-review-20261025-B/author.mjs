import fs from 'node:fs/promises';
import path from 'node:path';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';
const work=path.dirname(new URL(import.meta.url).pathname);
const d=JSON.parse(await fs.readFile(path.join(work,'unified-data.json'),'utf8'));
const wb=Workbook.create(),s=wb.worksheets.add(d.sheet);
const col=n=>{let t='';for(let k=n+1;k;k=Math.floor((k-1)/26))t=String.fromCharCode(65+(k-1)%26)+t;return t;};
const last=col(d.columns.length-1),end=d.rows.length+8;
const widths=[46,29,40,29,54,64,63,65,59,66,68,17,19,19,19,35,31,36,44,30,46,54,31,44,20,20,43,58,72,85,95,53,23,78];
s.showGridLines=false;s.tabColor='#253A49';
s.getRange(`A1:${last}${end}`).format={font:{name:'Arial',size:10,color:'#293238'},verticalAlignment:'top'};
s.getRange('A2').values=[['Wall Sculptures']];s.getRange('A2').format.font={name:'Arial',size:16,bold:true,color:'#253A49'};s.getRange('A2').format.rowHeight=25;
s.getRange('A3').values=[['Combined wall-sculpture records from Dropbox, Squarespace and Shopify. Saved sources, 25 October 2026.']];
s.getRange('A4').values=[['Individual options, source variants, arrangements and photograph groups retain their separate statuses. Estimates remain labelled.']];
s.getRange('A3:A4').format.font={name:'Arial',size:10,italic:true,color:'#596770'};
for(const [cell,value] of [['A5','Reviewed options'],['C5','Other source rows'],['E5','Photograph groups'],['G5','Folders without photographs']])s.getRange(cell).values=[[value]];
for(const [cell,formula] of Object.entries(d.formulas))s.getRange(cell).formulas=[[formula]];
for(const cell of ['B5','D5','F5','H5']){s.getRange(cell).setNumberFormat('#,##0');s.getRange(cell).format.font={name:'Arial',size:12,bold:true,color:'#253A49'};}
s.getRange('A6').values=[['Coverage: 80 reviewed Squarespace listings + 1 wall-scope review / 224 variants; 38 Shopify listings / variants; 6,360 current Dropbox files and 442 folders.']];
s.getRange('A7').values=[['Decorative balloons are included for wall-scope review; no mounting or catalogue identity is assumed. Group rows are not extra sculpture counts.']];
s.getRange('A6:A7').format.font={name:'Arial',size:10,color:'#596770'};
s.getRange(`A8:${last}8`).values=[d.columns];
s.getRange(`A9:${last}${end}`).values=d.rows;
const table=s.tables.add(`A8:${last}${end}`,true,'WallSculpturesTable');table.style='TableStyleLight1';table.showFilterButton=true;
s.getRange(`A8:${last}8`).format={fill:'#354A59',font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},wrapText:true,horizontalAlignment:'center',verticalAlignment:'center',rowHeight:48};
s.getRange(`A9:O${end}`).format.wrapText=true;
s.getRange(`P9:AB${end}`).format.wrapText=false;
s.getRange(`AC9:AE${end}`).format.wrapText=true;
s.getRange(`AF9:AG${end}`).format.wrapText=false;
s.getRange(`AH9:AH${end}`).format.wrapText=true;
for(let j=0;j<widths.length;j++)s.getRange(`${col(j)}1:${col(j)}${end}`).format.columnWidth=widths[j];
s.getRange(`Y9:Z${end}`).setNumberFormat('#,##0');
const readable=[...Array.from({length:11},(_,i)=>i),28,29,30,33];
let maxHeight=0;
for(let i=0;i<d.rows.length;i++){
 let lines=1;
 for(const j of readable){const text=String(d.rows[i][j]??'');lines=Math.max(lines,text.split('\n').reduce((n,line)=>n+Math.max(1,Math.ceil(line.length/(widths[j]*1.08))),0));}
 const height=Math.min(409,Math.max(44,lines*13+12));maxHeight=Math.max(maxHeight,height);
 s.getRange(`A${i+9}:${last}${i+9}`).format.rowHeight=height;
}
const linkcols=new Set(Object.keys(d.links).map(k=>Number(k.split(',')[1])));
for(const j of linkcols)s.getRange(`${col(j)}9:${col(j)}${end}`).format.font={name:'Arial',size:10,color:'#145D87',underline:'single'};
const statuses=s.getRange(`C9:C${end}`);
for(const text of ['Unmatched','unresolved','Provisional','unconfirmed'])statuses.conditionalFormats.add('containsText',{text,format:{fill:'#FFF0D2',font:{color:'#785300'}}});
s.freezePanes.freezeRows(8);s.freezePanes.freezeColumns(2);
wb.recalculate();
for(const [cell,expected] of Object.entries(d.expected_formula_values))if(s.getRange(cell).values[0][0]!==expected)throw new Error('Unexpected total at '+cell);
const sample=s.getRange('B9'),old=sample.values;sample.values=[['Temporary recalculation check']];wb.recalculate();
if(s.getRange('B5').values[0][0]!==187)throw new Error('Option total failed to update');sample.values=old;wb.recalculate();
if(s.getRange('B5').values[0][0]!==188)throw new Error('Option total not restored');
const scan=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:30},summary:'New sheet formula error scan',maxChars:2000});
await fs.writeFile(path.join(work,'formula-scan.ndjson'),scan.ndjson);
await(await SpreadsheetFile.exportXlsx(wb)).save(path.join(work,'primary-sheet.xlsx'));
await fs.mkdir(path.join(work,'previews'),{recursive:true});
const previews=[];
const selections=[['opening','A1:E14'],['specifications','F8:K11'],['links','L8:O14']];
for(const kind of Object.keys(d.counts)){
 const i=d.rows.findIndex(r=>r[1]===kind)+9;selections.push([kind.replaceAll(' ','-').replaceAll('/','-'),`A${i}:E${Math.min(i+2,end)}`]);
}
selections.push(['final-rows',`A${end-3}:E${end}`]);
const circle=d.rows.findIndex(r=>r[1]==='Other website variant')+9;
selections.push(['source-variant-details',`E${circle}:K${circle+2}`]);
selections.push(['image-counts-and-scope','Y8:AC11']);
selections.push(['scope-review-specifications',`F${end}:K${end}`]);
selections.push(['scope-review-links',`L${end}:O${end}`]);
for(const [label,range] of selections){const target=path.join(work,'previews',label+'.png');const png=await wb.render({sheetName:d.sheet,range,scale:1,format:'png'});await fs.writeFile(target,new Uint8Array(await png.arrayBuffer()));previews.push({path:target,range});}
await fs.writeFile(path.join(work,'authoring-receipt.json'),JSON.stringify({status:'PASS_PRIMARY_SHEET_AUTHORED',rows:d.rows.length,columns:d.columns.length,expectedFormulaValues:d.expected_formula_values,temporaryRecalculationCheckPassed:true,maximumRowHeight:maxHeight,previews},null,2));
console.log(JSON.stringify({status:'PRIMARY_SHEET_AUTHORED',rows:d.rows.length,previews:previews.length,maximumRowHeight:maxHeight}));
