import fs from 'node:fs/promises';
import path from 'node:path';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';

const work=path.dirname(new URL(import.meta.url).pathname);
const data=JSON.parse(await fs.readFile(path.join(work,'workbook-data.json'),'utf8'));
const wb=Workbook.create();
const col=n=>{let s='';for(let v=n+1;v;v=Math.floor((v-1)/26))s=String.fromCharCode(65+(v-1)%26)+s;return s;};
const clean=v=>String(v??'');
const sheets=data.tabs.map(t=>wb.worksheets.add(t.name));
const widthsBySheet={};
const expectedFormulaValues={B7:188,B8:208,B9:376,B10:136,B11:160,B12:6690,B13:442,B14:10847,B15:268,B16:140,B17:913,B18:625,B19:73,B20:47,B21:4,B22:2};
await fs.mkdir(path.join(work,'previews'),{recursive:true});

for(let k=0;k<data.tabs.length;k++){
  const t=data.tabs[k],s=sheets[k],end=t.rows.length+6,last=col(t.columns.length-1);
  const raw=t.name.endsWith('raw');
  const widths=t.columns.map((name,j)=>{
    if(t.widths[String(j)])return t.widths[String(j)];
    if(raw){if(j===0)return 14;if(/Description|Body \(HTML\)|Hosted Image|Image Src|Alt Text/i.test(name))return 75;return /ID|SKU|Handle|Title/i.test(name)?38:24;}
    if(/^(Image|Folder|First image|Source \/ image)$/.test(name))return 15;
    if(/count|bytes|price|weeks|position|increment|verification|recorded|row$/i.test(name))return 20;
    if(/ID|key|SKU|handle/i.test(name))return 34;
    return 36;
  });
  widthsBySheet[t.name]=widths;
  s.showGridLines=false;
  s.getRange(`A1:${last}${end}`).format.font={name:'Arial',size:10,color:'#293238'};
  s.getRange(`A1:${last}${end}`).format.verticalAlignment='top';
  s.getRange('A2').values=[[t.title]];
  s.getRange('A2').format.font={name:'Arial',size:16,bold:true,color:'#253A49'};
  s.getRange('A2').format.rowHeight=25;
  s.getRange('A3').values=[[t.name==='Overview'?'Product register and complete saved source inventories · 25 October 2026':`${t.rows.length.toLocaleString('en-GB')} records · Saved-source consolidation · 25 October 2026`]];
  s.getRange('A3').format.font={name:'Arial',size:10,italic:true,color:'#596770'};
  s.getRange('A4').values=[[t.source?`Source: ${path.basename(t.source)} · definitions in Guide and sources`:'Definitions and source clocks: Guide and sources']];
  s.getRange('A4').format.font={name:'Arial',size:10,color:'#596770'};
  s.getRange(`A5:${last}5`).format.borders={bottom:{style:'thin',color:'#C7CFD2'}};
  s.getRange(`A6:${last}6`).values=[t.columns];
  s.getRange(`A7:${last}${end}`).values=t.rows;
  s.getRange(`A7:${last}${end}`).format.wrapText=!raw;
  const table=s.tables.add(`A6:${last}${end}`,true,'Register'+k);
  table.style='TableStyleLight1';
  table.showFilterButton=true;
  s.getRange(`A6:${last}6`).format={fill:'#354A59',font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},wrapText:true,horizontalAlignment:'center',verticalAlignment:'center',rowHeight:44};
  for(let j=0;j<widths.length;j++)s.getRange(`${col(j)}1:${col(j)}${end}`).format.columnWidth=widths[j];
  // Raw export text remains intact and can be expanded in the formula bar.
  // Reader views use fitted row heights for the substantive displayed columns.
  const heights=[];
  for(let i=0;i<t.rows.length;i++){
    let lines=1;
    if(!raw)for(let j=0;j<t.rows[i].length;j++){
      const v=clean(t.rows[i][j]);
      const n=v.split('\n').reduce((a,line)=>a+Math.max(1,Math.ceil(line.length/Math.max(12,widths[j]*1.12))),0);
      lines=Math.max(lines,n);
    }
    heights.push(raw?32:Math.min(409,Math.max(t.name==='Overview'?34:32,lines*13+10)));
  }
  // Apply contiguous equal-height runs instead of one formatting call per cell.
  for(let a=0;a<heights.length;){let z=a+1;while(z<heights.length&&heights[z]===heights[a])z++;s.getRange(`A${a+7}:${last}${z+6}`).format.rowHeight=heights[a];a=z;}
  for(const [cell,formula] of Object.entries(t.formulas))s.getRange(cell).formulas=[[formula]];
  const linkCols=new Set(Object.keys(t.links).map(ij=>Number(ij.split(',')[1])));
  for(const j of linkCols)s.getRange(`${col(j)}7:${col(j)}${end}`).format.font={name:'Arial',size:10,color:'#145D87',underline:'single'};
  if(t.name!=='Overview'){s.freezePanes.freezeRows(6);s.freezePanes.freezeColumns(raw?1:2);}
  else{s.tabColor='#253A49';s.getRange(`B7:B${end}`).setNumberFormat('#,##0');s.getRange(`B7:B${end}`).format.font={name:'Arial',size:12,bold:true,color:'#253A49'};}
  if(t.name==='Products'){s.tabColor='#536B79';s.getRange('K7:L194').setNumberFormat('"£"#,##0.00');s.getRange('O7:P194').setNumberFormat('0');}
  if(['Squarespace variants','Shopify variants'].includes(t.name))s.getRange(`F7:G${end}`).setNumberFormat('#,##0.00');
  if(t.name==='Guide and sources')s.tabColor='#AEB6BA';
  const statusCol=t.name==='Unmatched and qualified'?'E':(['Products','Squarespace','Shopify','Dropbox files'].includes(t.name)?'C':null);
  if(statusCol){
    const r=s.getRange(`${statusCol}7:${statusCol}${end}`);
    for(const text of ['Unmatched','Provisional'])r.conditionalFormats.add('containsText',{text,format:{fill:'#FFF0D2',font:{color:'#785300'}}});
    r.conditionalFormats.add('containsText',{text:'Outside',format:{fill:'#F0F2F3',font:{color:'#596770'}}});
  }
  console.log(JSON.stringify({populated:t.name,rows:t.rows.length,columns:t.columns.length}));
}

wb.recalculate();
for(const [cell,value] of Object.entries(expectedFormulaValues)){
  const got=sheets[0].getRange(cell).values[0][0];
  if(got!==value)throw new Error(`Overview ${cell}: expected ${value}, got ${got}`);
}
// Representative recalculation, restored before saving.
const sample=sheets[data.tabs.findIndex(t=>t.name==='Squarespace')].getRange('A7');
const previous=sample.values;sample.clear({applyTo:'contents'});wb.recalculate();
if(sheets[0].getRange('B8').values[0][0]!==207)throw new Error('Summary did not recalculate after temporary removal');
sample.values=previous;wb.recalculate();
if(sheets[0].getRange('B8').values[0][0]!==208)throw new Error('Summary not restored');
const inspection=await wb.inspect({kind:'table',range:'Overview!A6:C22',include:'values,formulas',tableMaxRows:18,tableMaxCols:3,maxChars:5000});
await fs.writeFile(path.join(work,'summary-inspection.ndjson'),inspection.ndjson);
const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:40},summary:'Formula error scan',maxChars:4000});
await fs.writeFile(path.join(work,'formula-error-scan.ndjson'),errors.ndjson);
await (await SpreadsheetFile.exportXlsx(wb)).save(data.output);
console.log(JSON.stringify({exported:data.output}));
// Every sheet gets a bounded visual preview, including each raw source table.
const previews=[];
for(let k=0;k<data.tabs.length;k++){
  const t=data.tabs[k];
  const maxCol=t.name==='Overview'?2:t.name==='Guide and sources'?1:Math.min(3,t.columns.length-1);
  const range=t.name==='Overview'?'A1:C22':t.name==='Guide and sources'?'A1:B10':`A1:${col(maxCol)}${Math.min(t.rows.length+6,10)}`;
  const target=path.join(work,'previews',String(k+1).padStart(2,'0')+'-'+t.name.replaceAll(' ','-')+'.png');
  const png=await wb.render({sheetName:t.name,range,scale:1,format:'png'});
  await fs.writeFile(target,new Uint8Array(await png.arrayBuffer()));
  previews.push({sheet:t.name,range,path:target});console.log(JSON.stringify({rendered:t.name}));
}
for(const [sheet,range,label] of [['Products','G6:J9','product-specifications'],['Products','K6:P11','prices-and-availability'],['Dropbox files','D6:H10','dropbox-scope'],['Squarespace variants','D6:N10','source-variant-values'],['Catalogue source links','B269:H274','historical-source-links']]){
  const target=path.join(work,'previews',label+'.png');const png=await wb.render({sheetName:sheet,range,scale:1,format:'png'});await fs.writeFile(target,new Uint8Array(await png.arrayBuffer()));previews.push({sheet,range,path:target});
}
await fs.writeFile(path.join(work,'preview-manifest.json'),JSON.stringify(previews,null,2));
await fs.writeFile(path.join(work,'authoring-receipt.json'),JSON.stringify({status:'EXPORTED_AND_RENDERED',output:data.output,sheets:data.tabs.length,rows:Object.fromEntries(data.tabs.map(t=>[t.name,t.rows.length])),formulaValues:expectedFormulaValues,temporaryRecalculationCheckPassed:true,nativeHyperlinksPending:true},null,2));
console.log(JSON.stringify({status:'AUTHORING_COMPLETE',output:data.output,sheets:data.tabs.length,previews:previews.length}));
