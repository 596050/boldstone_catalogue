import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {FileBlob, SpreadsheetFile} from '@oai/artifact-tool';

const here=path.dirname(fileURLToPath(import.meta.url));
const root=path.resolve(here,'../../..');
const previous=JSON.parse(await fs.readFile(path.join(root,'components/evidence/component_workbook_manifest.json'),'utf8'));
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(previous.output));
if(process.argv.includes('--hyperlink-help')){
  console.log(wb.help('*',{search:'hyperlink|Hyperlink',include:'index,examples,notes',maxChars:7000}).ndjson);
  process.exit(0);
}
if(process.argv.includes('--inspect')){
  const dir=path.join(here,'before');await fs.mkdir(dir,{recursive:true});
  for(const [sheetName,range]of [['Summary','A2:C19'],['Individual Sculptures','A6:D10'],['Photograph Gaps','A6:F9']]){
    const blob=await wb.render({sheetName,range,scale:1,format:'png'});
    await fs.writeFile(path.join(dir,sheetName.replaceAll(' ','_')+'.png'),new Uint8Array(await blob.arrayBuffer()));
  }
  console.log((await wb.inspect({kind:'table',range:'Summary!A5:C19',include:'values,formulas',tableMaxRows:15,tableMaxCols:3,maxChars:4500})).ndjson);
  console.log((await wb.inspect({kind:'sheet',include:'id,name',maxChars:2500})).ndjson);
  process.exit(0);
}
const data=JSON.parse(await fs.readFile(path.join(here,'refresh-data.json'),'utf8'));
const outputDir=path.dirname(data.output);await fs.mkdir(outputDir,{recursive:true});
const sha=bytes=>crypto.createHash('sha256').update(bytes).digest('hex');
for(const source of data.source_files){
  const file=source.snapshot??source.source;
  if(sha(await fs.readFile(file))!==source.sha256)throw new Error('Source snapshot changed: '+file);
}
const allowedChanges=[],nativeLinks=[];
function setNativeLink(sheetName,address,url,label){
  const range=wb.worksheets.getItem(sheetName).getRange(address);
  range.values=[[label]];range.format.font={name:'Arial',size:10,color:'#245F9E'};
  nativeLinks.push({sheet:sheetName,cell:address,target:url,label});
}
function change(sheetName,address,value,formula=false){
  const range=wb.worksheets.getItem(sheetName).getRange(address);
  if(value&&typeof value==='object'&&value.nativeHyperlink){
    setNativeLink(sheetName,address,value.target,value.label);value=value.label;formula=false;
  }else if(formula)range.formulas=[[value]];else range.values=[[value]];
  allowedChanges.push({sheet:sheetName,address,formula,value});
}
const col=index=>{let result='';for(let n=index+1;n;n=Math.floor((n-1)/26))result=String.fromCharCode(65+(n-1)%26)+result;return result;};
const literal=v=>typeof v==='string'&&v.startsWith('=')?"'"+v:v??'';
const link=(url,label)=>({nativeHyperlink:true,target:url,label});
const green='#344E40',ink='#27392F',muted='#66746C';
const newSheets={};
function addView(name,title,note,headers,rows,widths,linkColumns){
  const sheet=wb.worksheets.add(name),end=6+rows.length,lastCol=col(headers.length-1);
  sheet.showGridLines=false;sheet.tabColor=green;
  sheet.getRangeByIndexes(0,0,end,headers.length).format.font={name:'Arial',size:10,color:ink};
  sheet.getRangeByIndexes(0,0,end,headers.length).format.verticalAlignment='center';
  sheet.getRange('A2').values=[[title]];sheet.getRange('A2').format.font={name:'Arial',size:15,bold:true,color:ink};
  sheet.getRange('A3').values=[[note]];sheet.getRange('A3').format.font={name:'Arial',size:10,italic:true,color:muted};
  sheet.getRangeByIndexes(5,0,1,headers.length).values=[headers];
  if(rows.length)sheet.getRangeByIndexes(6,0,rows.length,headers.length).values=rows.map(row=>row.map(literal));
  const table=sheet.tables.add(`A6:${lastCol}${end}`,true,'Current_'+name.replaceAll(' ',''));
  table.style='TableStyleLight1';table.showFilterButton=true;
  sheet.getRangeByIndexes(5,0,1,headers.length).format={fill:green,font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},horizontalAlignment:'center',verticalAlignment:'center',wrapText:true,rowHeight:38};
  widths.forEach((width,i)=>sheet.getRangeByIndexes(0,i,end,1).format.columnWidth=width);
  if(rows.length){
    sheet.getRangeByIndexes(6,0,rows.length,headers.length).format.wrapText=true;
    sheet.getRangeByIndexes(6,headers.length-1,rows.length,1).format.fill='#FFF6DB';
  }
  rows.forEach((row,index)=>{
    const lines=Math.max(1,...row.map((v,i)=>linkColumns.includes(i)?1:String(v??'').split('\n').reduce((count,line)=>count+Math.max(1,Math.ceil(line.length/Math.max(12,widths[i]*.95))),0)));
    const minHeight=name==='Reviewed Specifications'&&row[0]==='BC-MCP-4'&&row[2]==='MCP4-VERDIGRIS-RUST'?110:30;
    sheet.getRangeByIndexes(index+6,0,1,headers.length).format.rowHeight=Math.min(409,Math.max(minHeight,lines*12+8));
    for(const i of linkColumns)if(row[i]){
      setNativeLink(name,col(i)+(index+7),row[i],linkColumns.indexOf(i)%2===0?'Open image':'Open folder');
    }
  });
  sheet.freezePanes.freezeRows(6);sheet.freezePanes.freezeColumns(2);
  newSheets[name]={first:7,last:end,rows:rows.length,headers};
  return sheet;
}
const reviewRows=data.reviews.map(row=>[row[0],row[2],row[1],...row.slice(3)]);
addView('Current Reviews','Current sculpture reviews','Each row is a review scope. Base records, finishes, builds and aliases overlap. Filter by name or component ID.',
 ['Component / design ID','Current review name','Finish / build / source scope','Record type','Name decision','Specification status','Platform correspondence','Example image','Containing folder','Stable file ID','Stable folder ID','Scope and remaining questions','Notes for next review','Context images: status','Context images: type and limitations','Context example image','Context containing folder'],
 reviewRows,[23,58,35,29,38,55,65,20,20,47,47,105,55,46,105,20,20],[7,8,15,16]);
const specRows=data.specifications.map(row=>[row[0],row[2],row[1],...row.slice(3)]);
addView('Reviewed Specifications','Specifications by review scope','Six fields per scope. Owner-accepted estimates retain their assumptions. Set values are not divided among components.',
 ['Component / design ID','Sculpture / review name','Finish / build / source scope','Specification field','Available detail or proposal','Evidence / approval state','Source basis','Example image','Containing folder','Stable file ID','Stable folder ID','Proposal reference','Notes for next review'],
 specRows,[23,58,35,26,105,75,110,20,20,47,47,48,55],[7,8]);
addView('Group References','Group and arrangement references','Owner instruction: retain grouped photographs as context without identifying every component. Existing individual approvals remain recorded.',
 ['Source reference','Group / arrangement name','Name / existence decision','Current review scope','Available specifications or estimates','Specification status','Example image','Containing folder','Stable file ID','Stable folder ID','Limits / unresolved details','Notes for next review'],
 data.groups,[40,62,65,80,120,75,20,20,47,47,100,55],[6,7]);
if(data.physical_manufacture_review_policy?.owner_confirms_all_sculpture_designs_physically_made){
  for(const sheetName of ['Current Reviews','Group References']){
    wb.worksheets.getItem(sheetName).getRange('A3').values=[['Owner states all catalogue sculptures have been made. Names, specifications, stock and image provenance retain separate review states.']];
  }
  change('Summary','A31','Physical manufacture');
  change('Summary','B31','Owner states all sculptures have been made');
  change('Summary','C31','Owner instruction, 19 October. Repeat manufacture questions are superseded. Names, specifications, current stock, image provenance and final counts remain separate.');
  const policyRange=wb.worksheets.getItem('Summary').getRange('A31:C31');
  policyRange.format={wrapText:true,rowHeight:64,fill:'#FFFFFF',font:{name:'Arial',size:10,color:ink},verticalAlignment:'center'};
}
if(data.working_specification_acceptance_policy){
  change('Summary','A32','Working specifications');
  change('Summary','B32','Comparable working proposals accepted under owner instruction');
  change('Summary','C32','Owner instruction, 20 October. Keep guesses, conflicting sources and unknowns labelled. No separate reply is invented for each scope. Measurements, physical stock and scene provenance remain unverified.');
  wb.worksheets.getItem('Summary').getRange('A32:C32').format={wrapText:true,rowHeight:86,fill:'#FFFFFF',font:{name:'Arial',size:10,color:ink},verticalAlignment:'center'};
}
if(data.global_fixing_choice_policy){
  change('Summary','A33','Fixing choices');
  change('Summary','B33','Keyhole fixing or French cleat');
  change('Summary','C33','Owner instruction, 20 October. Offer a choice for all sculptures and individual components. Existing or historical fitted hardware stays recorded separately; fixing counts, attachment and load ratings remain subject to the individual record.');
  wb.worksheets.getItem('Summary').getRange('A33:C33').format={wrapText:true,rowHeight:86,fill:'#FFFFFF',font:{name:'Arial',size:10,color:ink},verticalAlignment:'center'};
}
if(data.global_approximate_weight_policy){
  change('Summary','A34','Approximate weights');
  change('Summary','B34','Applicable estimates accepted; missing individual weights estimated');
  change('Summary','C34','Owner instruction, 20 October. Policy90 added nine estimates and recovered seven source displays. Later reviews retain exact-scope corrections and add Azure’s conditional net estimate separately from shipping. Actual mass, packaging, water/system weights and support loads remain unverified.');
  wb.worksheets.getItem('Summary').getRange('A34:C34').format={wrapText:true,rowHeight:100,fill:'#FFFFFF',font:{name:'Arial',size:10,color:ink},verticalAlignment:'center'};
}

for(const [name,idColumn,nameColumn]of [['Individual Sculptures',0,1],['Listing Actions',0,1],['Photograph Gaps',1,2],['Component BOM',1,2],['Proposed Specifications',0,1]]){
  const table=previous.sheets[name];
  table.values.forEach((row,i)=>{
    const current=data.name_updates[row[idColumn]];
    if(current&&current!==row[nameColumn])change(name,col(nameColumn)+(table.first+i),current);
  });
}
const photoSheet=wb.worksheets.getItem('Photograph Gaps');
change('Photograph Gaps','J6','Recorded folder IDs (first folder link)');
change('Photograph Gaps','L6','Example image');
data.photograph_gap_links.forEach((reference,index)=>{
  const row=previous.sheets['Photograph Gaps'].first+index;
  if(reference.image)change('Photograph Gaps','L'+row,link(reference.image,'Open example image'),true);
  if(reference.folder)change('Photograph Gaps','J'+row,link(reference.folder,reference.current_folder_ids_label??previous.sheets['Photograph Gaps'].values[index][9]),true);
});
const additions=data.additional_photograph_gaps;
photoSheet.tables.items[0].rows.add(null,additions.map(x=>x.values));
additions.forEach((entry,index)=>{
  const row=previous.sheets['Photograph Gaps'].first+previous.sheets['Photograph Gaps'].count+index;
  photoSheet.getRange(`A${row}:L${row}`).format.font={name:'Arial',size:10,color:ink};
  photoSheet.getRange(`A${row}:L${row}`).format.wrapText=true;
  photoSheet.getRange(`A${row}:L${row}`).format.verticalAlignment='center';
  const widths=[25,23,61,38,44,45,54,80,105,47,47,85];
  const lines=Math.max(1,...entry.values.map((v,i)=>String(v??'').split('\n').reduce((n,line)=>n+Math.max(1,Math.ceil(line.length/(widths[i]*.95))),0)));
  photoSheet.getRange(`A${row}:L${row}`).format.rowHeight=Math.max(34,lines*13+9);
  if(entry.reference.image)change('Photograph Gaps','L'+row,link(entry.reference.image,'Open example image'),true);
  if(entry.reference.folder)change('Photograph Gaps','J'+row,link(entry.reference.folder,entry.reference.folder_id),true);
});
const platformHeaders=previous.sheets['Platform Mapping'].headers;
for(const record of data.platform_updates){
  const index=previous.sheets['Platform Mapping'].values.findIndex(row=>row[0]===record.offer_ref);
  if(index<0)throw new Error('Unknown platform offer');
  const row=previous.sheets['Platform Mapping'].first+index;
  for(const [key,header]of [['image_state','Photograph / design correspondence'],['image_folder_id','Stable photographed folder ID'],['image_file_id','Stable photograph file ID'],['image_path','Current photograph path']]){
    const column=platformHeaders.indexOf(header);if(column<0)throw new Error('Unknown platform column '+header);
    change('Platform Mapping',col(column)+row,record[key]??'');
  }
}
for(const record of data.asset_updates){
  const index=previous.sheets['Dropbox Files'].values.findIndex(row=>row[0]===record.id);
  if(index<0)throw new Error('Unknown asset');
  const row=previous.sheets['Dropbox Files'].first+index;
  for(const [field,column]of [['folder_id',1],['family',2],['group',3],['name',4],['path',8]]){
    const value=record[field]??'';
    if(value!==previous.sheets['Dropbox Files'].values[index][column])change('Dropbox Files',col(column)+row,value);
  }
}
for(const update of data.group_updates){
  const source=previous.sheets['Dropbox Groups'];const index=source.values.findIndex(row=>row[0]===update.group_ref);
  if(index<0)throw new Error('Unknown group override');const row=source.first+index;
  for(const [field,column]of [['family',1],['name',2],['id',3],['file_count',4],['role',5],['component_ids',6],['assignment_status',7],['path',9]])if(update[field]!==undefined){
    change('Dropbox Groups',col(column)+row,Array.isArray(update[field])?update[field].join('\n'):update[field]);
  }
  if(update.assignment_status?.includes('Owner confirmed finish: Moon Crater Phase 4')||update.group_ref==='G233'){
    wb.worksheets.getItem('Dropbox Groups').getRange(`A${row}:J${row}`).format.rowHeight=84;
    wb.worksheets.getItem('Dropbox Groups').getRange(`H${row}`).format.wrapText=true;
  }
}
for(const update of data.asset_scope_overrides){
  const source=previous.sheets['Dropbox Files'];const index=source.values.findIndex(row=>row[0]===update.file_id);
  if(index>=0)change('Dropbox Files','H'+(source.first+index),update.component_ids.join('\n'));
}
for(const update of data.source_cell_updates??[])change(update.sheet,col(update.column)+update.row,update.value);
if(data.catalogue_alias_rows?.length){
  const aliasSheet=wb.worksheets.getItem('Moulds and Aliases');
  aliasSheet.tables.items[0].rows.add(null,data.catalogue_alias_rows);
  const first=previous.sheets['Moulds and Aliases'].first+previous.sheets['Moulds and Aliases'].count;
  aliasSheet.getRange(`A${first}:F${first+data.catalogue_alias_rows.length-1}`).format={font:{name:'Arial',size:10,color:ink},wrapText:true,verticalAlignment:'center',rowHeight:84};
}
for(const name of Object.keys(previous.sheets))if(name!=='Summary'){
  change(name,'A3',name==='Photograph Gaps'?
    'Baseline photo gaps plus scoped component and finish reviews. Links open the recorded example and its folder. Not identified does not mean absent from all Dropbox.':
    name==='Platform Mapping'?'Platform exports / public pages captured 16 October; verified later photo correspondences added. Current account SKUs and stock have not been re-read.':
    name==='Unresolved Media'?'Historical source questions. Group-photo component identification is deferred by owner. Current standalone reviews continue separately.':
    name==='Moulds and Aliases'?'Historical maker codes and current owner catalogue aliases. A design-name consolidation does not confirm physical mould, cast or stock identity.':
    'Source register: 16–17 October 2026. Later owner decisions and scoped estimates appear in Current Reviews and Reviewed Specifications.');
}
change('Summary','A3','Owner reviews through 20 October 2026. Source inventory and platform evidence: 16–17 October.');
change('Summary','A5','Source-register checkpoint (16–17 October)');
for(const row of [6,7,8,9,10,14,15,18]){
  const old=wb.worksheets.getItem('Summary').getRange('A'+row).values[0][0];
  change('Summary','A'+row,'Baseline '+old.charAt(0).toLowerCase()+old.slice(1));
}
change('Summary','A16','Public pages captured / unavailable (16 October)');
change('Summary','C18','Historical work-item counts. The owner now skips component identification within group photographs. These are not current sculpture counts.');
change('Summary','A23','1. Continue standalone identity reviews');
const mcp4Consolidation=data.canonical_consolidations?.['BC-CONCAVE'];
if(mcp4Consolidation){
  change('Summary','A28','Canonical name update');
  change('Summary','B28','Concave Moon is now Moon Crater Phase 4');
  change('Summary','C28','Former name and source ID retained. Existing finish-specific specifications and offer conflicts preserved.');
  change('Summary','A29','MCP4 image folder');
  change('Summary','B29',link(mcp4Consolidation.canonical_folder_url,'Open Moon Crater Phase 4'));
  change('Summary','C29','47 image files retained; White has 8 images and 3 room references. Finish comparisons remain scoped.');
  wb.worksheets.getItem('Summary').getRange('A28:C29').format.wrapText=true;
  wb.worksheets.getItem('Summary').getRange('A28:C29').format.rowHeight=48;
  wb.worksheets.getItem('Summary').getRange('A28:C29').format.fill='#FFFFFF';
  wb.worksheets.getItem('Summary').getRange('A28:C29').format.font={name:'Arial',size:10,bold:false,color:ink};
  wb.worksheets.getItem('Summary').getRange('B29').format.font={name:'Arial',size:10,bold:false,color:'#245F9E'};
}
change('Summary','C23','Review remaining standalone designs and pending naming relationships. Group photographs remain context under the owner instruction.');
change('Summary','C24','Complete dimensions/depth, weight, material, fixing, individual price and availability. Keep source facts, owner statements and working estimates distinct.');
change('Summary','C25','Use Photograph Gaps for linked examples and folders. Confirm missing individual, rear/fixing, in situ and series photographs for the exact finish.');
change('Summary','C26','Connect shared SKUs to exact Dropbox designs, finishes and sale units. Finalise the individual listing count after aliases and offers are resolved.');
const summary=wb.worksheets.getItem('Summary');
summary.getRange('E5:G19').format.font={name:'Arial',size:10,color:ink};
summary.getRange('E5:G19').format.verticalAlignment='center';
for(const [letter,width]of [['D',4],['E',48],['F',19],['G',85]])summary.getRange(`${letter}1:${letter}24`).format.columnWidth=width;
summary.getRange('E5:G5').values=[['Current owner review','Records / state','Meaning']];
summary.getRange('E5:G5').format={fill:green,font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},rowHeight:29};
const currentStats=[
 ['Review scopes',`=COUNTA('Current Reviews'!$A$7:$A$${newSheets['Current Reviews'].last})`,'Overlapping base, finish/build and alias records. Not a physical sculpture count.'],
 ['Scoped working proposal approvals',data.specification_approval_counts.proposal_groups,'Recorded scoped working fields. Global fixing and weight policies are shown separately; estimates remain approximate.'],
 ['Individual dimension decisions',data.dimension_confirmation_counts.individual_dimension_decisions,'Scoped owner instructions. Depth, actual weight and fixing may remain unresolved.'],
 ['Source face-size instructions',data.source_dimension_decision_count,'Includes Soundwave 80 × 60 cm owner-stated face. Six working fields accepted; estimated depth remains unmeasured.'],
 ['Group references',`=COUNTA('Group References'!$A$7:$A$${newSheets['Group References'].last})`,'Group photographs remain available without component-identification questions.'],
 ['Group-photo component questions','Not required','Owner instruction recorded 19 October. Existing individual approvals are retained.'],
 ['Final individual listing count','Unverified','Source IDs and review scopes still include aliases, variants and unresolved sale units.']
];
currentStats.forEach((row,index)=>{
  summary.getRangeByIndexes(index+5,4,1,3).values=[[row[0],typeof row[1]==='string'&&row[1].startsWith('=')?'':row[1],row[2]]];
  if(typeof row[1]==='string'&&row[1].startsWith('='))summary.getRangeByIndexes(index+5,5,1,1).formulas=[[row[1]]];
  summary.getRangeByIndexes(index+5,4,1,3).format.rowHeight=48;
  summary.getRangeByIndexes(index+5,6,1,1).format.wrapText=true;
});
for(const [offset,name]of ['Current Reviews','Reviewed Specifications','Photograph Gaps','Platform Mapping','Group References'].entries()){
  summary.getRangeByIndexes(offset+13,4,1,3).values=[[name,'','']];
  setNativeLink('Summary','F'+(offset+14),"#'"+name+"'!A1",'Open sheet');
}
const textRestorations=JSON.parse(await fs.readFile(path.join(here,'source-text-restorations.json'),'utf8'));
for(const item of textRestorations)wb.worksheets.getItem(item.sheet).getRange(item.cell).values=[[item.value]];
for(const alias of Object.values(data.source_identity_consolidations??{})){
  const reviewRow=data.reviews.findIndex(row=>row[0]===alias.canonical_component_id&&row[1]==='SOURCE-G233002')+7;
  const aliasRow=previous.sheets['Moulds and Aliases'].first+previous.sheets['Moulds and Aliases'].count+data.catalogue_alias_rows.findIndex(row=>row[0]===alias.canonical_component_id);
  setNativeLink('Current Reviews','M'+reviewRow,alias.links.comparison_image,'Compare Chelsea image');
  setNativeLink('Moulds and Aliases','E'+aliasRow,alias.links.comparison_folder,'Open Chelsea reference folder');
}
wb.recalculate();
const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:50},maxChars:4500});
await fs.writeFile(path.join(here,'formula-error-inspection.ndjson'),errors.ndjson);
const previewDir=path.join(here,'after');await fs.mkdir(previewDir,{recursive:true});
const aliasIndex=reviewRows.findIndex(row=>row[2]==='MOONPHASE-CURRENT-1:WHITE-WITH-BORDER')+7;
const weightIndex=specRows.findIndex(row=>row[2]==='MOONPHASE-CURRENT-1:WHITE-WITH-BORDER'&&row[3]==='Weight')+7;
const newPhotoFirst=previous.sheets['Photograph Gaps'].first+previous.sheets['Photograph Gaps'].count;
const latestGroupRow=data.groups.findIndex(row=>row[0]==='FINGERPRINT-WAVY-VERDIGRIS-G158036')+7;
const followupGroupRow=data.groups.findIndex(row=>row[0]==='FINGERPRINT-DOUBLE-CURL-VERDIGRIS-G158013')+7;
const soundwaveRow=data.reviews.findIndex(row=>row[0]==='UGR-G310')+7;
const mcpDesignRow=data.reviews.findIndex(row=>row[0]==='BC-MCP-4'&&row[1]==='BASE')+7;
const mcpWhiteRow=data.reviews.findIndex(row=>row[0]==='BC-MCP-4'&&row[1]==='MCP4-WHITE')+7;
const mcpWhiteSpec=data.specifications.findIndex(row=>row[0]==='BC-MCP-4'&&row[1]==='MCP4-WHITE')+7;
const formerSourceRow=previous.sheets['Individual Sculptures'].values.findIndex(row=>row[0]==='BC-CONCAVE')+previous.sheets['Individual Sculptures'].first;
const mcpWhiteGroupRow=previous.sheets['Dropbox Groups'].values.findIndex(row=>row[0]==='G219')+previous.sheets['Dropbox Groups'].first;
const formerWhiteGroupRow=previous.sheets['Dropbox Groups'].values.findIndex(row=>row[0]==='G054')+previous.sheets['Dropbox Groups'].first;
const movedWhiteFileRow=previous.sheets['Dropbox Files'].values.findIndex(row=>row[0]==='id:cnqzTNngPVsAAAAAAAyiJw')+previous.sheets['Dropbox Files'].first;
const canonicalAliasRow=previous.sheets['Moulds and Aliases'].first+previous.sheets['Moulds and Aliases'].count;
const fourPanelRow=data.groups.findIndex(row=>row[0]==='FINGERPRINT-FOUR-PANEL-VERDIGRIS-G158026')+7;
const goldRow=data.reviews.findIndex(row=>row[0]==='BC-AC-FULL'&&row[1]==='AC-FULL-GOLD-LEAF')+7;
const goldSpecRow=data.specifications.findIndex(row=>row[0]==='BC-AC-FULL'&&row[1]==='AC-FULL-GOLD-LEAF')+7;
const doubleCurlRow=data.groups.findIndex(row=>row[0]==='FINGERPRINT-DOUBLE-CURL-VERDIGRIS-G158013')+7;
const threePanelRow=data.groups.findIndex(row=>row[0]==='FINGERPRINT-THREE-PANEL-VERDIGRIS-G160006')+7;
const fourPanelRowRef=data.groups.findIndex(row=>row[0]==='FINGERPRINT-FOUR-PANEL-ROW-VERDIGRIS-G160005')+7;
const whiteBlackRow=data.reviews.findIndex(row=>row[0]==='BC-AC-TWO'&&row[1]==='AC-TWO-WHITE-BLACK')+7;
const whiteBlackSpec=data.specifications.findIndex(row=>row[0]==='BC-AC-TWO'&&row[1]==='AC-TWO-WHITE-BLACK')+7;
const brancusiComponent=process.argv.includes('--brancusi-two')?'BC-BR-2':'BC-BR-1';
const brancusiVariant=process.argv.includes('--brancusi-two')?'BR-2-GOLD-LEAF':'BR-1-GOLD-LEAF';
const brancusiBaseRow=data.reviews.findIndex(row=>row[0]===brancusiComponent&&row[1]==='BASE')+7;
const brancusiGoldRow=data.reviews.findIndex(row=>row[0]===brancusiComponent&&row[1]===brancusiVariant)+7;
const brancusiGoldSpec=data.specifications.findIndex(row=>row[0]===brancusiComponent&&row[1]===brancusiVariant)+7;
const mcpSilverRow=data.reviews.findIndex(row=>row[0]==='BC-MCP-4'&&row[1]==='MCP4-SILVER-BRONZE-25')+7;
const mcpVerdigrisRow=data.reviews.findIndex(row=>row[0]==='BC-MCP-4'&&row[1]==='MCP4-VERDIGRIS-25')+7;
const mcpRustRow=data.reviews.findIndex(row=>row[0]==='BC-MCP-4'&&row[1]==='MCP4-VERDIGRIS-RUST')+7;
const mcpRustSpec=data.specifications.findIndex(row=>row[0]==='BC-MCP-4'&&row[1]==='MCP4-VERDIGRIS-RUST')+7;
const asymmetricRow=data.groups.findIndex(row=>row[0]==='FINGERPRINT-ASYMMETRIC-SPIRAL-VERDIGRIS-G160003')+7;
const loopedRow=data.groups.findIndex(row=>row[0]==='FINGERPRINT-LOOPED-RIDGE-VERDIGRIS-G158032')+7;
const chelseaSourceRow=data.reviews.findIndex(row=>row[0]==='BC-CHELSEA'&&row[1]==='SOURCE-G233002')+7;
const chelseaSourceSpec=data.specifications.findIndex(row=>row[0]==='BC-CHELSEA'&&row[1]==='SOURCE-G233002')+7;
const chelseaSourceGroup=previous.sheets['Dropbox Groups'].values.findIndex(row=>row[0]==='G233')+previous.sheets['Dropbox Groups'].first;
const chelseaAliasRow=canonicalAliasRow+data.catalogue_alias_rows.findIndex(row=>row[0]==='BC-CHELSEA');
const silverGroupRows=['G215','G051'].map(group=>previous.sheets['Dropbox Groups'].values.findIndex(row=>row[0]===group)+previous.sheets['Dropbox Groups'].first);
const finishFollowupViews=['AC-TWO-BRONZE','AC-TWO-PALE-BLUE-WHITE'].flatMap(variant=>{
  const row=data.reviews.findIndex(r=>r[0]==='BC-AC-TWO'&&r[1]===variant)+7;
  const spec=data.specifications.findIndex(r=>r[0]==='BC-AC-TWO'&&r[1]===variant)+7;
  return [['Current Reviews',`A${row}:F${row}`],['Current Reviews',`G${row}:L${row}`],['Reviewed Specifications',`B${spec}:F${spec+5}`]];
});
const coverageReviewRows=['BR-1-GOLD-LEAF','BR-2-GOLD-LEAF'].map(variant=>data.reviews.findIndex(row=>row[1]===variant)+7);
const coveragePhotoRows=['BR-1-GOLD-LEAF','BR-2-GOLD-LEAF'].map(variant=>newPhotoFirst+additions.findIndex(entry=>entry.values[0]===variant));
const moonphaseSilverRow=data.reviews.findIndex(row=>row[1]==='MOONPHASE-CURRENT-4:SILVER')+7;
const moonphaseSilverSpec=data.specifications.findIndex(row=>row[1]==='MOONPHASE-CURRENT-4:SILVER')+7;
const moonphaseSilverGroup=previous.sheets['Dropbox Groups'].values.findIndex(row=>row[0]==='G243')+previous.sheets['Dropbox Groups'].first;
const newFingerprintViews=['FINGERPRINT-FINE-RIDGE-VERDIGRIS-G158004','FINGERPRINT-DIAGONAL-SPIRAL-VERDIGRIS-G158034'].flatMap(key=>{
  const row=data.groups.findIndex(item=>item[0]===key)+7;
  return [['Group References',`A${row}:D${row}`],['Group References',`E${row}:F${row}`],['Group References',`G${row}:L${row}`]];
});
const multipleSpiralRow=data.groups.findIndex(item=>item[0]==='FINGERPRINT-MULTIPLE-SPIRAL-VERDIGRIS-G158020')+7;
const gold2ReviewRow=data.reviews.findIndex(item=>item[1]==='BR-2-GOLD-LEAF')+7;
const gold2SpecRow=data.specifications.findIndex(item=>item[1]==='BR-2-GOLD-LEAF')+7;
const ovalRingsRow=data.groups.findIndex(item=>item[0]==='FINGERPRINT-OVAL-RINGS-VERDIGRIS-G158017')+7;
const twinSpiralsRow=data.groups.findIndex(item=>item[0]==='FINGERPRINT-TWIN-SPIRALS-VERDIGRIS-G158019')+7;
const acanthusGoldContextRow=data.reviews.findIndex(item=>item[1]==='AC-FULL-GOLD-LEAF')+7;
const acanthusGoldSpecRow=data.specifications.findIndex(item=>item[1]==='AC-FULL-GOLD-LEAF')+7;
const ovalRingsCurlsRow=data.groups.findIndex(item=>item[0]==='FINGERPRINT-OVAL-RINGS-CURLS-VERDIGRIS-G158018')+7;
const ms1ContextRow=data.reviews.findIndex(item=>item[1]==='MS1-WHITE')+7;
const ms1GapRow=newPhotoFirst+additions.findIndex(entry=>entry.values[0]==='MS1-WHITE');
const offsetSpiralRow=data.groups.findIndex(item=>item[0]==='FINGERPRINT-OFFSET-SPIRAL-VERDIGRIS-G158022')+7;
const moonspiralWorkingViews=['MS1-WHITE','MS2-WHITE','MS3-WHITE'].flatMap(variant=>{
 const row=data.reviews.findIndex(item=>item[1]===variant)+7;
 const spec=data.specifications.findIndex(item=>item[1]===variant)+7;
 return [['Current Reviews',`A${row}:F${row}`],['Current Reviews',`G${row}:L${row}`],['Reviewed Specifications',`B${spec}:F${spec+5}`],...(variant==='MS1-WHITE'?[]:[['Current Reviews',`N${row}:Q${row}`]])];
});
const ms2GapRow=newPhotoFirst+additions.findIndex(entry=>entry.values[0]==='MS2-WHITE');
const ms3GapRow=newPhotoFirst+additions.findIndex(entry=>entry.values[0]==='MS3-WHITE');
const roughConcentricRow=data.groups.findIndex(item=>item[0]==='FINGERPRINT-ROUGH-CONCENTRIC-VERDIGRIS-G160001')+7;
const bronze74Row=data.reviews.findIndex(item=>item[1]==='AC-TWO-BRONZE')+7;
const bronze74Spec=data.specifications.findIndex(item=>item[1]==='AC-TWO-BRONZE')+7;
const bronze74Gap=newPhotoFirst+additions.findIndex(entry=>entry.values[0]==='AC-TWO-BRONZE');
const ffl74Gap=newPhotoFirst+additions.findIndex(entry=>entry.values[0]==='BC-FFL-1-SOURCE-ONLY');
const sourceAlias74=canonicalAliasRow+data.catalogue_alias_rows.findIndex(row=>row[0]==='PIXEL-IDENTICAL-G158022-G160001');
const source74Views=[['Summary','E5:G12'],['Current Reviews',`A${bronze74Row}:F${bronze74Row}`],['Current Reviews',`G${bronze74Row}:L${bronze74Row}`],['Current Reviews',`N${bronze74Row}:Q${bronze74Row}`],['Reviewed Specifications',`B${bronze74Spec}:F${bronze74Spec+5}`],...[offsetSpiralRow,roughConcentricRow].flatMap(row=>[['Group References',`A${row}:D${row}`],['Group References',`G${row}:L${row}`]]),['Moulds and Aliases',`A${sourceAlias74}:C${sourceAlias74}`],['Moulds and Aliases',`D${sourceAlias74}:F${sourceAlias74}`],['Individual Sculptures','A64:E64'],['Individual Sculptures','Q64:Q64'],['Photograph Gaps',`A${bronze74Gap}:F${ffl74Gap}`],['Photograph Gaps',`G${bronze74Gap}:I${ffl74Gap}`],['Photograph Gaps',`J${bronze74Gap}:L${ffl74Gap}`]];
const specs76Views=[['Summary','E5:G12'],...[[ 'BC-AC-TWO','AC-TWO-PALE-BLUE-WHITE'],['BC-FOUNTAIN-EG','FOUNTAIN-EG-WHITE']].flatMap(([cid,vid])=>{const row=data.reviews.findIndex(r=>r[0]===cid&&r[1]===vid)+7;const spec=data.specifications.findIndex(r=>r[0]===cid&&r[1]===vid)+7;return [['Current Reviews',`A${row}:F${row}`],['Current Reviews',`G${row}:L${row}`],['Current Reviews',`N${row}:Q${row}`],['Reviewed Specifications',`B${spec}:F${spec+5}`]];}),...['AC-TWO-PALE-BLUE-WHITE','FOUNTAIN-EG-WHITE'].flatMap(vid=>{const row=newPhotoFirst+additions.findIndex(r=>r.values[0]===vid);return [['Photograph Gaps',`A${row}:F${row}`],['Photograph Gaps',`G${row}:I${row}`],['Photograph Gaps',`J${row}:L${row}`]];})];
const whiteBlack78Row=data.reviews.findIndex(r=>r[0]==='BC-AC-TWO'&&r[1]==='AC-TWO-WHITE-BLACK')+7;
const whiteBlack78Spec=data.specifications.findIndex(r=>r[0]==='BC-AC-TWO'&&r[1]==='AC-TWO-WHITE-BLACK')+7;
const whiteBlack78Gap=newPhotoFirst+additions.findIndex(r=>r.values[0]==='AC-TWO-WHITE-BLACK');
const fountain78Row=data.reviews.findIndex(r=>r[0]==='BC-FOUNTAIN-EG'&&r[1]==='FOUNTAIN-EG-WHITE')+7;
const fountain78Weight=data.specifications.findIndex(r=>r[0]==='BC-FOUNTAIN-EG'&&r[1]==='FOUNTAIN-EG-WHITE'&&r[3]==='Weight')+7;
const updates78Views=[['Summary','E5:G12'],['Current Reviews',`A${whiteBlack78Row}:F${whiteBlack78Row}`],['Current Reviews',`G${whiteBlack78Row}:L${whiteBlack78Row}`],['Current Reviews',`N${whiteBlack78Row}:Q${whiteBlack78Row}`],['Reviewed Specifications',`B${whiteBlack78Spec}:F${whiteBlack78Spec+5}`],['Photograph Gaps',`A${whiteBlack78Gap}:F${whiteBlack78Gap}`],['Photograph Gaps',`G${whiteBlack78Gap}:I${whiteBlack78Gap}`],['Photograph Gaps',`J${whiteBlack78Gap}:L${whiteBlack78Gap}`],['Current Reviews',`A${fountain78Row}:F${fountain78Row}`],['Current Reviews',`G${fountain78Row}:L${fountain78Row}`],['Reviewed Specifications',`B${fountain78Weight}:F${fountain78Weight}`]];
const working83Scopes=[['BC-FOUNTAIN-EG','FOUNTAIN-EG-BRONZE-VERDIGRIS'],['BC-FOUNTAIN-MED','FOUNTAIN-MED-WHITE'],['BC-LEAF-CURVE','LEAF-CURVE-WHITE-GOLD'],['BC-LEAF-GROWTH','LEAF-GROWTH-WHITE'],['BC-LEAF-GROWTH','LEAF-GROWTH-WHITE-GOLD'],['BC-LEAF-FORM','LEAF-FORM-LF1-WHITE'],['BC-LEAF-FORM','LEAF-FORM-LF2-WHITE'],['BC-LEAF-FORM','LEAF-FORM-GOLD']];
const find83=(rows,cid,vid)=>{const i=rows.findIndex(r=>r[0]===cid&&r[1]===vid);if(i<0)throw new Error('Missing exact83 scope '+cid+' '+vid);return i+7;};
const updates83Views=[['Summary','E5:G12'],['Summary','A31:C32'],['Current Reviews',`A${mcpRustRow}:F${mcpRustRow}`],['Reviewed Specifications',`D${mcpRustSpec+4}:G${mcpRustSpec+5}`],['Reviewed Specifications',`G${whiteBlack78Spec+4}:G${whiteBlack78Spec+4}`],...working83Scopes.flatMap(([cid,vid])=>{const r=find83(data.reviews,cid,vid),s=find83(data.specifications,cid,vid);return [['Current Reviews',`A${r}:F${r}`],['Reviewed Specifications',`D${s}:G${s+5}`],['Current Reviews',`N${r}:Q${r}`]];}),...[working83Scopes.slice(0,4),working83Scopes.slice(4)].flatMap(scopes=>{const rows=scopes.map(([cid,vid])=>{const i=additions.findIndex(r=>r.values[0]===vid);if(i<0)throw new Error('Missing photo gap '+vid);return newPhotoFirst+i;});if(rows.some((r,i)=>r!==rows[0]+i))throw new Error('Expected contiguous83 photo gaps');const a=rows[0],b=rows.at(-1);return [['Photograph Gaps',`A${a}:D${b}`],['Photograph Gaps',`E${a}:I${b}`],['Photograph Gaps',`J${a}:L${b}`]];})];
const working87Scopes=[['BC-MCP-1','MCP1-WHITE'],['BC-MCP-1','MCP1-VERDIGRIS-RUST'],['BC-MCP-2','MCP2-WHITE'],['BC-MCP-2','MCP2-BLUE-SPLASHES'],['BC-MCP-2','MCP2-VERDIGRIS-RUST'],['BC-MCP-3','MCP3-WHITE'],['BC-MCP-3','MCP3-VERDIGRIS-RUST'],['BC-EMBED-SHELLS','EMBED-SHELLS-WHITE'],['BC-FACET-MOUND','FACET-MOUND-GOLD-LEAF']];
const global87Examples=[['BC-MCP-4','MCP4-VERDIGRIS-RUST'],['BC-FOUNTAIN-EG','FOUNTAIN-EG-WHITE'],['BC-AC-ONE','AC-ONE-LEFT-SANDSTONE'],['MOONPHASE-CURRENT-1','MOONPHASE-CURRENT-1:WHITE-WITH-BORDER'],['BC-FFL-1','BASE'],['BC-MIX-SPIRALS','BASE']];
const updates87Views=[['Summary','E5:G12'],['Summary','A31:C33'],...working87Scopes.flatMap(([cid,vid])=>{const r=find83(data.reviews,cid,vid),s=find83(data.specifications,cid,vid);return [['Current Reviews',`A${r}:F${r}`],['Reviewed Specifications',`D${s}:G${s+5}`],['Current Reviews',`N${r}:Q${r}`]];}),...[working87Scopes.slice(0,3),working87Scopes.slice(3,6),working87Scopes.slice(6)].flatMap(scopes=>{const rows=scopes.map(([cid,vid])=>{const i=additions.findIndex(r=>r.values[0]===vid);if(i<0)throw new Error('Missing87 gap '+vid);return newPhotoFirst+i;});if(rows.some((r,i)=>r!==rows[0]+i))throw new Error('Expected contiguous87 gaps');const a=rows[0],b=rows.at(-1);return [['Photograph Gaps',`A${a}:D${b}`],['Photograph Gaps',`E${a}:I${b}`],['Photograph Gaps',`J${a}:L${b}`]];}),...global87Examples.map(([cid,vid])=>{const s=find83(data.specifications,cid,vid)+3;return ['Reviewed Specifications',`D${s}:G${s}`];})];
const working91Scopes=[['BC-AC-ONE','AC-ONE-LEFT-SANDSTONE'],['BC-AC-ONE','AC-ONE-LEFT-PEWTER'],['BC-PANEL-CURVES','PANEL-CURVES-BEIGE-PROCESS'],['BC-PANEL-CURVES','PANEL-CURVES-MULTICOLOUR-PATINA'],['BC-PLANT','PLANT-WHITE'],['BC-RW-SPIRAL1','RAKED-SPIRAL1-BEIGE'],['BC-RW-SPIRAL1','RAKED-SPIRAL1-WHITE'],['BC-RW-WAVE','RAKED-SPIRAL2-BEIGE'],['BC-RW-WAVE','RAKED-SPIRAL2-WHITE'],['BC-RW-SPIRAL3','RAKED-SPIRAL3-BEIGE'],['BC-RW-SPIRAL3','RAKED-SPIRAL3-WHITE'],['BC-CRATER-WIDE','CRATER-WIDE-DRIP-RUST'],['BC-MFW-1','MFW-LEFT-WHITE'],['BC-MFW-2','MFW-RIGHT-WHITE'],['BC-MOON-RING','MOON-RING-WHITE']];
const consecutive91=rows=>{const groups=[];for(const n of [...new Set(rows)].sort((a,b)=>a-b)){const g=groups.at(-1);if(g&&n===g.at(-1)+1&&g.length<3)g.push(n);else groups.push([n]);}return groups;};
const new91ReviewGroups=consecutive91(working91Scopes.map(([cid,vid])=>find83(data.reviews,cid,vid)));
const new91PhotoGroups=consecutive91(working91Scopes.map(([cid,vid])=>{const i=additions.findIndex(x=>x.values[0]===vid);if(i<0)throw Error('Missing91 gap '+vid);return newPhotoFirst+i;}));
const weight91Examples=[['BC-MCP-4','MCP4-VERDIGRIS-RUST'],['BC-FOUNTAIN-EG','FOUNTAIN-EG-WHITE'],['BC-LEAF-GROWTH','LEAF-GROWTH-WHITE'],['BC-CHELSEA','SOURCE-G233002'],['BC-MIX-SPIRALS','BASE']];
const updates91Views=[['Summary','E5:G12'],['Summary','A31:C34'],...new91ReviewGroups.flatMap(g=>[['Current Reviews',`A${g[0]}:F${g.at(-1)}`],['Current Reviews',`N${g[0]}:Q${g.at(-1)}`]]),...working91Scopes.map(([cid,vid])=>{const s=find83(data.specifications,cid,vid);return ['Reviewed Specifications',`D${s}:G${s+5}`];}),...new91PhotoGroups.flatMap(g=>[['Photograph Gaps',`A${g[0]}:D${g.at(-1)}`],['Photograph Gaps',`E${g[0]}:I${g.at(-1)}`],['Photograph Gaps',`J${g[0]}:L${g.at(-1)}`]]),...data.weight_policy_overlays.filter(x=>['NEW_CONDITIONAL_ESTIMATE_PREPARED','EXISTING_ESTIMATE_DISPLAY_RECOVERY'].includes(x.disposition)).map(x=>{const i=data.specifications.findIndex(r=>r[0]===x.key[0]&&r[1]===x.key[1]&&r[3]==='Weight')+7;if(i<7)throw Error('Missing weight91');return ['Reviewed Specifications',`D${i}:G${i}`];}),...weight91Examples.map(([cid,vid])=>{const i=data.specifications.findIndex(r=>r[0]===cid&&r[1]===vid&&r[3]==='Weight')+7;if(i<7)throw Error('Missing example91');return ['Reviewed Specifications',`D${i}:G${i}`];}),['Current Reviews',`G${find83(data.reviews,'BC-CHELSEA','BASE')}:L${find83(data.reviews,'BC-CHELSEA','BASE')}`]];
const updates97Views=process.argv.includes('--all-remaining-97')?JSON.parse(await fs.readFile(path.join(here,'preview-plan-batch97.json'),'utf8')).views:[];
const views=process.argv.includes('--all-remaining-97')?updates97Views:process.argv.includes('--working-and-weights-91')?updates91Views:process.argv.includes('--next-working-and-fixing-choice')?updates87Views:process.argv.includes('--commercial-policy-and-leaves')?updates83Views:process.argv.includes('--white-black-and-owner-weight')?updates78Views:process.argv.includes('--pale-blue-and-fountain-white')?specs76Views:process.argv.includes('--bronze-canonical-source-gap')?source74Views:process.argv.includes('--moonspirals-and-duplicate')?
 [['Summary','E5:G12'],...moonspiralWorkingViews,['Photograph Gaps',`A${ms2GapRow}:F${ms3GapRow}`],['Photograph Gaps',`G${ms2GapRow}:I${ms3GapRow}`],['Photograph Gaps',`J${ms2GapRow}:L${ms3GapRow}`],['Group References',`A${roughConcentricRow}:D${roughConcentricRow}`],['Group References',`E${roughConcentricRow}:F${roughConcentricRow}`],['Group References',`G${roughConcentricRow}:L${roughConcentricRow}`],['Group References',`G${offsetSpiralRow}:L${offsetSpiralRow}`]]:process.argv.includes('--offset-and-ms1-context')?
 [['Summary','E5:G12'],['Current Reviews',`N${ms1ContextRow}:Q${ms1ContextRow}`],['Photograph Gaps',`A${ms1GapRow}:F${ms1GapRow}`],['Photograph Gaps',`G${ms1GapRow}:I${ms1GapRow}`],['Photograph Gaps',`J${ms1GapRow}:L${ms1GapRow}`],['Group References',`A${offsetSpiralRow}:D${offsetSpiralRow}`],['Group References',`E${offsetSpiralRow}:F${offsetSpiralRow}`],['Group References',`G${offsetSpiralRow}:L${offsetSpiralRow}`]]:process.argv.includes('--acanthus-working-and-fingerprint')?
 [['Summary','E5:G12'],['Current Reviews',`A${acanthusGoldContextRow}:F${acanthusGoldContextRow}`],['Current Reviews',`G${acanthusGoldContextRow}:L${acanthusGoldContextRow}`],['Reviewed Specifications',`B${acanthusGoldSpecRow}:F${acanthusGoldSpecRow+5}`],['Group References',`A${ovalRingsCurlsRow}:D${ovalRingsCurlsRow}`],['Group References',`E${ovalRingsCurlsRow}:F${ovalRingsCurlsRow}`],['Group References',`G${ovalRingsCurlsRow}:L${ovalRingsCurlsRow}`]]:process.argv.includes('--silver-and-twins')?
 [['Summary','E5:G12'],['Current Reviews',`A${moonphaseSilverRow}:F${moonphaseSilverRow}`],['Current Reviews',`G${moonphaseSilverRow}:L${moonphaseSilverRow}`],['Reviewed Specifications',`B${moonphaseSilverSpec}:F${moonphaseSilverSpec+5}`],['Dropbox Groups',`A${moonphaseSilverGroup}:H${moonphaseSilverGroup}`],['Current Reviews',`N${acanthusGoldContextRow}:Q${acanthusGoldContextRow}`],['Group References',`A${twinSpiralsRow}:D${twinSpiralsRow}`],['Group References',`E${twinSpiralsRow}:F${twinSpiralsRow}`],['Group References',`G${twinSpiralsRow}:L${twinSpiralsRow}`]]:process.argv.includes('--gold2-and-keyhole')?
 [['Summary','E5:G12'],['Current Reviews',`A${gold2ReviewRow}:F${gold2ReviewRow}`],['Current Reviews',`G${gold2ReviewRow}:L${gold2ReviewRow}`],['Reviewed Specifications',`B${gold2SpecRow}:F${gold2SpecRow+5}`],['Current Reviews',`A${mcpRustRow}:F${mcpRustRow}`],['Current Reviews',`G${mcpRustRow}:L${mcpRustRow}`],['Reviewed Specifications',`B${mcpRustSpec+3}:F${mcpRustSpec+3}`],['Group References',`A${ovalRingsRow}:D${ovalRingsRow}`],['Group References',`E${ovalRingsRow}:F${ovalRingsRow}`],['Group References',`G${ovalRingsRow}:L${ovalRingsRow}`]]:process.argv.includes('--rust-material-and-multiple')?
 [['Summary','E5:G12'],['Current Reviews',`A${mcpRustRow}:F${mcpRustRow}`],['Current Reviews',`G${mcpRustRow}:L${mcpRustRow}`],['Reviewed Specifications',`B${mcpRustSpec+2}:F${mcpRustSpec+2}`],['Group References',`A${multipleSpiralRow}:D${multipleSpiralRow}`],['Group References',`E${multipleSpiralRow}:F${multipleSpiralRow}`],['Group References',`G${multipleSpiralRow}:L${multipleSpiralRow}`]]:process.argv.includes('--gold-working-and-fingerprint')?
 [['Summary','E5:G12'],['Current Reviews',`A${brancusiGoldRow}:F${brancusiGoldRow}`],['Current Reviews',`G${brancusiGoldRow}:L${brancusiGoldRow}`],['Reviewed Specifications',`B${brancusiGoldSpec}:F${brancusiGoldSpec+5}`],['Current Reviews',`N${brancusiGoldRow}:Q${brancusiGoldRow}`],...newFingerprintViews]:process.argv.includes('--mcp4-rust-weight')?
 [['Current Reviews',`A${mcpRustRow}:F${mcpRustRow}`],['Current Reviews',`G${mcpRustRow}:L${mcpRustRow}`],['Reviewed Specifications',`B${mcpRustSpec+1}:F${mcpRustSpec+1}`],['Reviewed Specifications',`B${mcpRustSpec+2}:F${mcpRustSpec+5}`]]:process.argv.includes('--rust-dimensions-and-silver')?
 [['Summary','E5:G12'],['Summary','A31:C31'],['Current Reviews',`A${mcpRustRow}:F${mcpRustRow}`],['Reviewed Specifications',`B${mcpRustSpec}:F${mcpRustSpec}`],['Reviewed Specifications',`B${mcpRustSpec+1}:F${mcpRustSpec+5}`],['Current Reviews',`A${moonphaseSilverRow}:F${moonphaseSilverRow}`],['Current Reviews',`G${moonphaseSilverRow}:L${moonphaseSilverRow}`],['Current Reviews',`N${moonphaseSilverRow}:Q${moonphaseSilverRow}`],['Reviewed Specifications',`B${moonphaseSilverSpec}:F${moonphaseSilverSpec+5}`],['Dropbox Groups',`A${moonphaseSilverGroup}:H${moonphaseSilverGroup}`]]:process.argv.includes('--chelsea-comparison-links')?
 [['Current Reviews',`G${chelseaSourceRow}:M${chelseaSourceRow}`],['Moulds and Aliases',`A${chelseaAliasRow}:F${chelseaAliasRow}`]]:process.argv.includes('--chelsea-and-looped')?
 [['Summary','E5:G12'],['Group References',`A${loopedRow}:D${loopedRow}`],['Current Reviews',`A${chelseaSourceRow}:F${chelseaSourceRow}`],['Current Reviews',`G${chelseaSourceRow}:L${chelseaSourceRow}`],['Current Reviews',`N${chelseaSourceRow}:Q${chelseaSourceRow}`],['Reviewed Specifications',`B${chelseaSourceSpec}:F${chelseaSourceSpec+5}`],['Moulds and Aliases',`A${chelseaAliasRow}:F${chelseaAliasRow}`],['Dropbox Groups',`A${chelseaSourceGroup}:H${chelseaSourceGroup}`]]:process.argv.includes('--mcp4-rust-kept')?
 [['Summary','E5:G12'],['Current Reviews',`A${mcpRustRow}:F${mcpRustRow}`],['Current Reviews',`G${mcpRustRow}:L${mcpRustRow}`],['Photograph Gaps',`A${newPhotoFirst+5}:F${newPhotoFirst+5}`],['Group References',`A${loopedRow}:D${loopedRow}`],['Group References',`E${loopedRow}:F${loopedRow}`],['Group References',`G${loopedRow}:L${loopedRow}`]]:process.argv.includes('--mcp4-verdigris-and-rust')?
 [['Summary','E5:G12'],['Current Reviews',`A${mcpVerdigrisRow}:F${mcpVerdigrisRow}`],['Current Reviews',`G${mcpVerdigrisRow}:L${mcpVerdigrisRow}`],['Current Reviews',`A${mcpRustRow}:F${mcpRustRow}`],['Current Reviews',`G${mcpRustRow}:L${mcpRustRow}`],['Reviewed Specifications',`B${mcpRustSpec}:F${mcpRustSpec+5}`],['Group References',`A${asymmetricRow}:D${asymmetricRow}`],['Group References',`E${asymmetricRow}:F${asymmetricRow}`],['Group References',`G${asymmetricRow}:L${asymmetricRow}`],['Photograph Gaps',`A${newPhotoFirst+5}:F${newPhotoFirst+5}`],['Photograph Gaps',`G${newPhotoFirst+5}:L${newPhotoFirst+5}`],['Current Reviews','N6:Q9'],...[mcpVerdigrisRow,mcpRustRow,...coverageReviewRows].map(row=>['Current Reviews',`N${row}:Q${row}`])]:process.argv.includes('--brancusi-coverage')?
 [['Summary','A5:C19'],...coverageReviewRows.map(row=>['Current Reviews',`G${row}:L${row}`]),...coveragePhotoRows.flatMap(row=>[['Photograph Gaps',`A${row}:F${row}`],['Photograph Gaps',`G${row}:I${row}`],['Photograph Gaps',`J${row}:L${row}`]])]:process.argv.includes('--brancusi-two')?
 [['Summary','E5:G12'],['Current Reviews',`A${brancusiBaseRow}:F${brancusiBaseRow}`],['Current Reviews',`G${brancusiBaseRow}:L${brancusiBaseRow}`],['Current Reviews',`A${brancusiGoldRow}:F${brancusiGoldRow}`],['Current Reviews',`G${brancusiGoldRow}:L${brancusiGoldRow}`],['Reviewed Specifications',`B${brancusiGoldSpec}:F${brancusiGoldSpec+5}`]]:process.argv.includes('--brancusi-and-row')?
 [['Summary','E5:G12'],['Current Reviews',`A${brancusiBaseRow}:F${brancusiBaseRow}`],['Current Reviews',`G${brancusiBaseRow}:L${brancusiBaseRow}`],['Current Reviews',`A${brancusiGoldRow}:F${brancusiGoldRow}`],['Current Reviews',`G${brancusiGoldRow}:L${brancusiGoldRow}`],['Reviewed Specifications',`B${brancusiGoldSpec}:F${brancusiGoldSpec+5}`],['Group References',`A${fourPanelRowRef}:D${fourPanelRowRef}`]]:process.argv.includes('--white-black-and-row')?
 [['Summary','E5:G12'],['Current Reviews',`A${whiteBlackRow}:F${whiteBlackRow}`],['Current Reviews',`G${whiteBlackRow}:L${whiteBlackRow}`],['Reviewed Specifications',`B${whiteBlackSpec}:F${whiteBlackSpec+5}`],['Group References',`A${fourPanelRowRef}:D${fourPanelRowRef}`],['Group References',`E${fourPanelRowRef}:F${fourPanelRowRef}`],['Group References',`G${fourPanelRowRef}:L${fourPanelRowRef}`]]:process.argv.includes('--mcp4-silver-followup')?
 [['Current Reviews',`A${mcpSilverRow}:F${mcpSilverRow}`],['Current Reviews',`G${mcpSilverRow}:L${mcpSilverRow}`],...silverGroupRows.map(row=>['Dropbox Groups',`A${row}:H${row}`])]:process.argv.includes('--current-acanthus-followups')?
 [['Summary','E5:G12'],...finishFollowupViews,['Group References',`A${threePanelRow}:D${threePanelRow}`],['Group References',`E${threePanelRow}:F${threePanelRow}`],['Group References',`G${threePanelRow}:L${threePanelRow}`]]:process.argv.includes('--latest-owner-followups')?
 [['Summary','E5:G12'],['Current Reviews',`A${goldRow}:F${goldRow}`],['Current Reviews',`G${goldRow}:L${goldRow}`],['Reviewed Specifications',`B${goldSpecRow}:F${goldSpecRow+5}`],['Group References',`A${fourPanelRow}:D${fourPanelRow}`],['Group References',`E${fourPanelRow}:F${fourPanelRow}`],['Group References',`G${fourPanelRow}:L${fourPanelRow}`],['Group References',`G${doubleCurlRow}:L${doubleCurlRow}`]]:process.argv.includes('--preserve-previews')?[]:process.argv.includes('--mcp4-final-labels')?
 [['Summary','A28:C29'],['Individual Sculptures',`A${formerSourceRow}:E${formerSourceRow}`]]:process.argv.includes('--mcp4-consolidation')?
 [['Summary','A28:C29'],['Current Reviews',`A${mcpDesignRow}:F${mcpDesignRow}`],['Current Reviews',`A${mcpWhiteRow}:F${mcpWhiteRow+2}`],['Current Reviews',`H${mcpWhiteRow}:L${mcpWhiteRow+2}`],['Reviewed Specifications',`B${mcpWhiteSpec}:F${mcpWhiteSpec+5}`],['Reviewed Specifications',`B${mcpWhiteSpec+6}:F${mcpWhiteSpec+7}`],['Reviewed Specifications',`B${mcpWhiteSpec+12}:F${mcpWhiteSpec+13}`],['Individual Sculptures',`A${formerSourceRow}:E${formerSourceRow}`],['Dropbox Groups',`A${mcpWhiteGroupRow}:H${mcpWhiteGroupRow}`],['Dropbox Groups',`A${formerWhiteGroupRow}:H${formerWhiteGroupRow}`],['Dropbox Files',`A${movedWhiteFileRow}:E${movedWhiteFileRow}`],['Dropbox Files',`I${movedWhiteFileRow}:I${movedWhiteFileRow}`],['Moulds and Aliases',`A${canonicalAliasRow}:F${canonicalAliasRow}`],['Summary','E5:G12']]:process.argv.includes('--latest-followups')?
 [['Summary','E5:G12'],['Current Reviews',`A${soundwaveRow}:D${soundwaveRow}`],['Current Reviews',`E${soundwaveRow}:F${soundwaveRow}`],['Current Reviews',`G${soundwaveRow}:L${soundwaveRow}`],['Group References',`A${followupGroupRow}:D${followupGroupRow}`],['Group References',`E${followupGroupRow}:F${followupGroupRow}`],['Group References',`G${followupGroupRow}:L${followupGroupRow}`],['Photograph Gaps',`A${newPhotoFirst+2}:F${newPhotoFirst+2}`]]:process.argv.includes('--latest-group')?
 [['Summary','E5:G12'],['Group References',`A${latestGroupRow-1}:D${latestGroupRow}`],['Group References',`E${latestGroupRow}:F${latestGroupRow}`],['Group References',`G${latestGroupRow}:L${latestGroupRow}`]]:process.argv.includes('--photo-only')?
 [['Photograph Gaps',`A${newPhotoFirst}:F${newPhotoFirst+additions.length-1}`],['Photograph Gaps',`J${newPhotoFirst}:L${newPhotoFirst+additions.length-1}`]]:process.argv.includes('--groups-only')?
 [['Group References','A6:F9'],['Group References','G6:J9']]:process.argv.includes('--links-only')?
 [['Summary','E5:G18'],['Photograph Gaps','J6:L9'],['Photograph Gaps',`J${newPhotoFirst}:L${newPhotoFirst+additions.length-1}`],['Current Reviews','H6:K10'],['Current Reviews',`H${aliasIndex}:K${aliasIndex}`],['Reviewed Specifications','H6:K10'],['Group References','G6:J9'],['Group References','E7:F9']]:process.argv.includes('--affected-aliases')?
 [['Current Reviews',`A${aliasIndex}:F${aliasIndex}`],['Current Reviews',`H${aliasIndex}:K${aliasIndex}`],['Reviewed Specifications',`B${weightIndex}:F${weightIndex+1}`],['Photograph Gaps',`A${newPhotoFirst}:F${newPhotoFirst+additions.length-1}`],['Photograph Gaps',`J${newPhotoFirst}:L${newPhotoFirst+additions.length-1}`],['Summary','A22:C26']]:
 [['Summary','A5:C19'],['Summary','E5:G18'],['Individual Sculptures','A6:D10'],['Listing Actions','A6:D9'],['Photograph Gaps','A6:F9'],['Photograph Gaps','J6:L9'],['Component BOM','A6:D9'],['Platform Mapping','A6:F9'],['Proposed Specifications','A6:D9'],['Evidence >>','A2:C7'],['Specification Evidence','A6:D8'],['Dropbox Groups','A6:D9'],['Dropbox Files','A6:E9'],['Unresolved Media','A6:D9'],['Moulds and Aliases','A6:D9'],['Mixed Image Links','A6:D9'],['Current Reviews','A6:F10'],['Reviewed Specifications','B6:F10'],['Group References','A6:D9']];
const priorReceipt=await fs.readFile(path.join(here,'export-receipt.json'),'utf8').then(JSON.parse).catch(()=>null);
const previewFiles=(process.argv.includes('--all-remaining-97')||process.argv.includes('--working-and-weights-91')||process.argv.includes('--next-working-and-fixing-choice')||process.argv.includes('--commercial-policy-and-leaves')||process.argv.includes('--white-black-and-owner-weight')||process.argv.includes('--pale-blue-and-fountain-white')||process.argv.includes('--bronze-canonical-source-gap')||process.argv.includes('--moonspirals-and-duplicate')||process.argv.includes('--offset-and-ms1-context')||process.argv.includes('--acanthus-working-and-fingerprint')||process.argv.includes('--silver-and-twins')||process.argv.includes('--gold2-and-keyhole')||process.argv.includes('--rust-material-and-multiple')||process.argv.includes('--gold-working-and-fingerprint')||process.argv.includes('--mcp4-rust-weight')||process.argv.includes('--rust-dimensions-and-silver')||process.argv.includes('--affected-aliases')||process.argv.includes('--links-only')||process.argv.includes('--groups-only')||process.argv.includes('--photo-only')||process.argv.includes('--latest-group')||process.argv.includes('--latest-followups')||process.argv.includes('--mcp4-consolidation')||process.argv.includes('--mcp4-final-labels')||process.argv.includes('--preserve-previews')||process.argv.includes('--latest-owner-followups')||process.argv.includes('--current-acanthus-followups')||process.argv.includes('--mcp4-silver-followup')||process.argv.includes('--white-black-and-row')||process.argv.includes('--brancusi-and-row')||process.argv.includes('--brancusi-two')||process.argv.includes('--brancusi-coverage')||process.argv.includes('--mcp4-verdigris-and-rust')||process.argv.includes('--mcp4-rust-kept')||process.argv.includes('--chelsea-and-looped')||process.argv.includes('--chelsea-comparison-links'))?[...(priorReceipt?.previews??[])]:[];
const finalViews=process.argv.includes('--gold-working-status')?[['Reviewed Specifications',`B${brancusiGoldSpec}:F${brancusiGoldSpec+5}`]]:views;
if(process.argv.includes('--gold-working-status')){
  for(let index=previewFiles.length-1;index>=0;index--)if(previewFiles[index].sheet==='Reviewed Specifications'&&previewFiles[index].range===`B${brancusiGoldSpec}:F${brancusiGoldSpec+5}`)previewFiles.splice(index,1);
}
const renderSelection=process.argv.find(x=>x.startsWith('--preview-indices='));
const selectedPreviewIndices=renderSelection?new Set(renderSelection.split('=')[1].split(',').map(Number)):null;
for(const [index,[sheetName,range]]of [...finalViews.entries()].filter(([index])=>!selectedPreviewIndices||selectedPreviewIndices.has(index))){
  const blob=await wb.render({sheetName,range,scale:1,format:'png'});
  const prefix=process.argv.includes('--all-remaining-97')?'owner97_':process.argv.includes('--working-and-weights-91')?'owner91_':process.argv.includes('--next-working-and-fixing-choice')?'owner87_':process.argv.includes('--commercial-policy-and-leaves')?'owner83_':process.argv.includes('--white-black-and-owner-weight')?'owner78_':process.argv.includes('--pale-blue-and-fountain-white')?'owner76_':process.argv.includes('--bronze-canonical-source-gap')?'owner74_':process.argv.includes('--moonspirals-and-duplicate')?'owner72_':process.argv.includes('--offset-and-ms1-context')?'owner67_':process.argv.includes('--acanthus-working-and-fingerprint')?'owner65_':process.argv.includes('--silver-and-twins')?'owner63_':process.argv.includes('--gold2-and-keyhole')?'owner61_':process.argv.includes('--rust-material-and-multiple')?'owner58_':process.argv.includes('--gold-working-status')?'owner56fix_':process.argv.includes('--gold-working-and-fingerprint')?'owner56_':process.argv.includes('--mcp4-rust-weight')?'owner52_':process.argv.includes('--rust-dimensions-and-silver')?'owner51_':process.argv.includes('--chelsea-comparison-links')?'links48_':process.argv.includes('--chelsea-and-looped')?'owner48_':process.argv.includes('--mcp4-rust-kept')?'owner46_':process.argv.includes('--mcp4-verdigris-and-rust')?'owner44_':process.argv.includes('--brancusi-coverage')?'coverage41_':process.argv.includes('--brancusi-two')?'owner40_':process.argv.includes('--brancusi-and-row')?'owner39_':process.argv.includes('--white-black-and-row')?'owner37_':process.argv.includes('--mcp4-silver-followup')?'owner35_':process.argv.includes('--current-acanthus-followups')?'owner34_':process.argv.includes('--latest-owner-followups')?'owner30_':process.argv.includes('--mcp4-final-labels')?'mcp4_final_':process.argv.includes('--mcp4-consolidation')?'mcp4_':process.argv.includes('--latest-followups')?'followups_':process.argv.includes('--latest-group')?'latest_group_':process.argv.includes('--photo-only')?'photo_':process.argv.includes('--groups-only')?'groups_':process.argv.includes('--links-only')?'links_':process.argv.includes('--affected-aliases')?'alias_':'';
  const target=path.join(previewDir,prefix+String(index).padStart(2,'0')+'_'+sheetName.replaceAll(' ','_')+'.png');
  await fs.writeFile(target,new Uint8Array(await blob.arrayBuffer()));
  const existingPreview=previewFiles.findIndex(p=>p.path===target);
  if(existingPreview>=0)previewFiles[existingPreview]={sheet:sheetName,range,path:target};else previewFiles.push({sheet:sheetName,range,path:target});
}
const inspect=await wb.inspect({kind:'table',range:'Summary!E5:G12',include:'values,formulas',tableMaxRows:8,tableMaxCols:3,maxChars:4500});
await fs.writeFile(path.join(here,'summary-inspection.ndjson'),inspect.ndjson);
await(await SpreadsheetFile.exportXlsx(wb)).save(data.output);
await fs.writeFile(path.join(here,'native-hyperlinks.json'),JSON.stringify(nativeLinks,null,2)+'\n');
const receipt={output:data.output,output_sha256:sha(await fs.readFile(data.output)),captured_utc:data.as_of_utc,new_sheets:newSheets,allowed_existing_cell_changes:allowedChanges,added_photograph_gap_rows:additions.length,previous_workbook:data.previous_workbook,source_files:data.source_files,previews:previewFiles,formula_error_inspection:errors.ndjson,native_hyperlink_plan_sha256:sha(await fs.readFile(path.join(here,'native-hyperlinks.json'))),native_hyperlink_count:nativeLinks.length,status:'EXPORTED;NATIVE_HYPERLINKS_AND_INDEPENDENT_CHECK_REQUIRED'};
await fs.writeFile(path.join(here,'export-receipt.json'),JSON.stringify(receipt,null,2)+'\n');
console.log(JSON.stringify({output:data.output,review_scopes:data.reviews.length,specification_entries:data.specifications.length,source_platform_records:81,preview_images:previewFiles.length,status:receipt.status}));
