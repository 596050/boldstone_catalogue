import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { FileBlob, SpreadsheetFile } from '@oai/artifact-tool';

const here=path.dirname(fileURLToPath(import.meta.url));
const audit=JSON.parse(await fs.readFile(path.join(here,'image-coverage-audit.json'),'utf8'));
const plan=JSON.parse(await fs.readFile(path.join(here,'workbook-edit-plan.json'),'utf8'));
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(here,process.argv.includes('--finalise-dates')?'master-workbook.pending':'inputs/master_workbook.before')));
if(process.argv.includes('--finalise-dates')){
 const s=wb.worksheets.getItem('Wall Circle Sources');
 const dates=audit.wall_circle_sources.map(x=>[Date.parse(x.source_snapshot_date+'T00:00:00Z')/86400000+25569]);
 s.getRange('M10:M27').values=dates;s.getRange('M10:M27').setNumberFormat('yyyy-mm-dd');
 wb.recalculate();
 const exp=JSON.parse(await fs.readFile(path.join(here,'expected-edit.json'),'utf8'));
 dates.forEach((r,i)=>exp.sheets['Wall Circle Sources'].rows[i][12]=r[0]);
 const b=await wb.render({sheetName:'Wall Circle Sources',range:'I9:N12',scale:1.5,format:'png'});
 const preview=path.join(here,'previews/11-native-variant-detail.png');await fs.writeFile(preview,new Uint8Array(await b.arrayBuffer()));
 const list=JSON.parse(await fs.readFile(path.join(here,'preview-manifest.json'),'utf8'));list.push({sheet:'Wall Circle Sources',range:'I9:N12',path:preview});
 const out=await SpreadsheetFile.exportXlsx(wb);await out.save(path.join(here,'master-workbook.dates-pending'));await fs.rename(path.join(here,'master-workbook.dates-pending'),path.join(here,'master-workbook.pending'));
 await fs.writeFile(path.join(here,'expected-edit.json'),JSON.stringify(exp,null,2));
 await fs.writeFile(path.join(here,'preview-manifest.json'),JSON.stringify(list,null,2));
 const receipt=JSON.parse(await fs.readFile(path.join(here,'artifact-authoring-receipt.json'),'utf8'));receipt.typed_dates=true;receipt.preview_count=list.length;await fs.writeFile(path.join(here,'artifact-authoring-receipt.json'),JSON.stringify(receipt,null,2));
 console.log(JSON.stringify({status:'SOURCE_DATES_TYPED_AND_VERIFIED',source_date_serial:dates[0][0]}));process.exit(0);
}
const initial=await wb.inspect({kind:'sheet',include:'id,name',maxChars:2000});
await fs.writeFile(path.join(here,'initial-workbook-inspection.ndjson'),initial.ndjson);
const green='#344E40',ink='#28362D',muted='#6D776F';
const col=n=>{let s='';for(n++;n;n=Math.floor((n-1)/26))s=String.fromCharCode(65+(n-1)%26)+s;return s;};
const link=(r,key='image_url',label='Image')=>r?.[key]?{target:r[key],label}:'';
const value=x=>x&&typeof x==='object'&&'target'in x?x.label:(x??'');
const expected={},extraLinks=[],formulaChecks=[];
for(const x of plan.cell_changes){
  const s=wb.worksheets.getItem(x.sheet);s.getRange(x.cell).values=[[x.value]];
  if(!x.before&&plan.native_hyperlinks.some(h=>h.sheet===x.sheet&&h.cell===x.cell))s.getRange(x.cell).format.font={name:'Arial',size:10,color:'#245F9E',underline:'single'};
}
function add(name,title,note,headers,rows,widths,editable=[]){
 const s=wb.worksheets.add(name),last=9+rows.length;
 s.showGridLines=false;s.tabColor=green;
 const grid=s.getRangeByIndexes(0,0,last,headers.length);
 grid.format.font={name:'Arial',size:10,color:ink};grid.format.verticalAlignment='center';
 s.getRange('A2:F2').merge();s.getRange('A2').values=[[title]];
 s.getRange('A2:F2').format={font:{name:'Arial',size:16,bold:true,color:green},rowHeight:32};
 s.getRange('A3:H3').merge();s.getRange('A3').values=[[note]];
 s.getRange('A3:H3').format={font:{name:'Arial',size:10,color:muted},wrapText:true,rowHeight:40};
 s.getRangeByIndexes(8,0,1,headers.length).values=[headers];
 s.getRangeByIndexes(9,0,rows.length,headers.length).values=rows.map(r=>r.map(value));
 const t=s.tables.add(`A9:${col(headers.length-1)}${last}`,true,'Photo_'+name.replaceAll(' ','_'));
 t.style='TableStyleLight1';t.showFilterButton=true;
 s.getRangeByIndexes(8,0,1,headers.length).format={fill:green,font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},horizontalAlignment:'center',wrapText:true,rowHeight:38};
 widths.forEach((w,j)=>s.getRangeByIndexes(0,j,last,1).format.columnWidth=w);
 s.getRangeByIndexes(9,0,rows.length,headers.length).format.wrapText=true;
 rows.forEach((r,i)=>{
  const lines=Math.max(...r.map((v,j)=>String(value(v)).split('\n').reduce((n,z)=>n+Math.max(1,Math.ceil(z.length/Math.max(10,widths[j]*.85))),0)));
  const height=Math.max(42,lines*13+10);
  if(height>409)throw new Error(`${name} row ${i+10} would clip: ${height}`);
  s.getRangeByIndexes(i+9,0,1,headers.length).format.rowHeight=height;
  r.forEach((v,j)=>{if(v&&typeof v==='object'&&'target'in v){const cell=col(j)+(i+10);extraLinks.push({sheet:name,cell,...v});s.getRange(cell).format.font={name:'Arial',size:10,color:'#245F9E',underline:'single'};}});
 });
 for(const c of editable)s.getRange(`${c}10:${c}${last}`).format.fill='#FFF3D6';
 s.freezePanes.freezeRows(9);s.freezePanes.freezeColumns(2);
 expected[name]={headers,rows:rows.map(r=>r.map(value)),first:10,last,widths};
 return s;
}
const pRows=audit.coverage.map(x=>[
 x.option_id,x.name,x.individual.status,link(x.individual.reference,'image_url',x.individual.exact_option?'Image':'Related example only'),link(x.individual.reference,'folder_url','Folder'),
 x.in_situ.status,link(x.in_situ.reference,'image_url','Room / garden'),link(x.in_situ.reference,'folder_url','Folder'),x.series.status,link(x.series.reference,'image_url','Series image'),link(x.series.reference,'folder_url','Folder'),
 [x.in_situ.basis,x.series.basis,...x.notes].join('\n'),x.individual.reference?.file_id??'',x.individual.reference?.folder_id??'',x.in_situ.reference?.file_id??'',x.in_situ.reference?.folder_id??'',
 x.series.reference?.file_id??'',x.series.reference?.folder_id??'',x.scope,x.scene_origin,x.owner_review,x.series_required?'Family / series relevant':'Optional; no fixed set established'
]);
const photo=add('Photo Coverage','Photograph coverage by individual option',
 '184 options. Available means a reviewed source depiction. Check the role notes for exact finish, size/build and scene limits. Related Long Fish references are explicitly unbound.',
 ['Option ID','Individual sculpture / option','Individual full view','Individual reference','Containing folder','In situ view','Room / garden reference','Room / garden folder','Series view','Series reference','Series folder','Role notes and identity limits','Individual file ID','Individual folder ID','In situ file ID','In situ folder ID','Series file ID','Series folder ID','Review scope','Scene origin','Owner review notes','Series requirement'],
 pRows,[25,58,26,25,18,28,24,20,29,23,20,124,40,40,40,40,40,40,113,88,80,48],['U']);
const mRows=audit.missing_pictures.map(x=>[x.priority,x.option_id,x.name,x.role,x.action_type,x.action,link(x.reference,'image_url',x.option_id===audit.coverage[81].option_id?'Related example only':'Available reference'),link(x.reference,'folder_url','Folder'),x.reference?.file_id??'',x.reference?.folder_id??'',x.scope,x.qualification,x.owner_response,x.status]);
const missing=add('Missing Pictures','Missing photographs and image checks',
 'Filter Action type to separate new photographs, checks of existing images and optional family views. Add the exact file or decision in Owner response; mark Resolved after verification.',
 ['Priority','Option ID','Individual sculpture / option','Picture role','Action type','Required action','Available example / candidate','Containing folder','Reference file ID','Reference folder ID','Review scope','Qualification','Owner response / exact file','Action status'],
 mRows,[12,25,58,18,27,105,28,19,40,40,113,124,95,20],['M','N']);
missing.getRange(`N10:N${9+mRows.length}`).dataValidation={rule:{type:'list',values:['Open','In progress','Resolved','Optional']}};
const iRows=audit.identity_review.map(x=>[x.case_id,x.name,x.position,x.proposed_identity,x.state,x.check,link(x.reference,'image_url','Review image'),link(x.reference,'folder_url','Folder'),x.reference?.file_id??'',x.reference?.folder_id??'',x.related_option_ids.join('\n'),link(x.comparison,'image_url','Compare image'),link(x.comparison,'folder_url','Compare folder'),x.comparison?.file_id??'',x.owner_decision,x.comparison?.folder_id??'']);
const identity=add('Identity Review','Image and component identity review',
 'Each position has an image and containing folder. Candidate positions remain outside the 184 sale options. Existing owner decisions are retained; write any new decision in Owner decision.',
 ['Case ID','Source / individual option','Position in photograph','Proposed identity / relationship','Current evidence state','What needs checking','Review image','Containing folder','Review file ID','Review folder ID','Related current option IDs','Comparison image','Comparison folder','Comparison file ID','Owner decision','Comparison folder ID'],
 iRows,[34,63,48,78,42,128,22,20,40,40,45,23,22,40,95,40],['O']);
const wRows=audit.wall_circle_sources.map(x=>[x.pattern,x.state,x.native_image_id,{target:x.native_url,label:'Squarespace source image'},link(x.reference,'image_url','Dropbox swatch'),link(x.reference,'folder_url','Folder'),x.reference.file_id,x.reference.folder_id,x.variant_ids.length,x.variant_ids.join('\n'),x.skus.join('\n'),x.scope,x.source_snapshot_date,x.native_sha256]);
const wall=add('Wall Circle Sources','Wall Circle native pattern image bindings',
 '18 native pattern images visually matched to Dropbox swatches cover 144 preserved source variants. Four circular visual-name aliases are candidates on Identity Review; three remain unresolved.',
 ['Native pattern','Image match','Native image ID','Native source image','Dropbox pattern image','Containing folder','Dropbox file ID','Dropbox folder ID','Source variants','Native variant IDs','Source SKUs','Match scope and remaining limits','Source snapshot date','Native image SHA256'],
 wRows,[80,50,34,29,27,20,40,40,18,57,27,124,24,77]);
wall.getRange('M10:M27').setNumberFormat('@');
function summary(s,labelCell,label,valueCell,formula,result){
 s.getRange(labelCell).values=[[label]];s.getRange(labelCell).format={font:{name:'Arial',size:10,color:muted},wrapText:true,rowHeight:34};
 s.getRange(valueCell).formulas=[[formula]];s.getRange(valueCell).format={font:{name:'Arial',size:16,bold:true,color:green},horizontalAlignment:'center'};s.getRange(valueCell).setNumberFormat('#,##0');
 formulaChecks.push({sheet:s.name,cell:valueCell,formula,expected:result});
}
summary(photo,'A4','Individual full views','B4','=COUNTIF(C10:C193,"Available")',157);
summary(photo,'C4','In situ available','D4','=COUNTIF(F10:F193,"Available")',90);
summary(photo,'E4','Series available','F4','=COUNTIF(I10:I193,"Available")',94);
summary(photo,'A5','Individual photo gaps','B5','=COUNTA(A10:A193)-B4',27);
summary(photo,'C5','In situ image checks','D5','=COUNTIF(F10:F193,"Verify existing image")',28);
summary(photo,'E5','Series image checks','F5','=COUNTIF(I10:I193,"Verify existing image")+COUNTIF(I10:I193,"Source-supported")',10);
const ml=9+mRows.length;
summary(missing,'A4','Find / capture','B4',`=COUNTIFS(E10:E${ml},"Find / capture",N10:N${ml},"<>Resolved")`,120);
summary(missing,'C4','Verify existing','D4',`=COUNTIFS(E10:E${ml},"Verify existing image",N10:N${ml},"<>Resolved")`,38);
summary(missing,'E4','Optional images','F4',`=COUNTIF(N10:N${ml},"Optional")`,53);
summary(identity,'A4','Review rows','B4',`=COUNTA(A10:A${9+iRows.length})`,99);
summary(identity,'C4','Wall Circle candidates','D4',`=COUNTIF(E10:E${9+iRows.length},"Strong visual candidate")`,4);
summary(identity,'E4','Unresolved circles','F4',`=COUNTIF(E10:E${9+iRows.length},"Unresolved")`,3);
summary(wall,'A4','Native patterns','B4','=COUNTA(A10:A27)',18);
summary(wall,'C4','Source variants','D4','=SUM(I10:I27)',144);
for(const s of [photo,missing]){
 const cols=s===photo?['C','F','I']:['E','N'];const last=expected[s.name].last;
 for(const c of cols){s.getRange(`${c}10:${c}${last}`).conditionalFormats.add('containsText',{text:'Verify',format:{fill:'#FFF3D6',font:{color:'#9C440D'}}});s.getRange(`${c}10:${c}${last}`).conditionalFormats.add('containsText',{text:'No verified',format:{fill:'#FBE8E6',font:{color:'#A22E29'}}});}
}
// Meaningful dependency checks, with every temporary edit restored.
photo.getRange('C10').values=[['Detail only']];
if(photo.getRange('B4').values[0][0]!==156||photo.getRange('B5').values[0][0]!==28)throw new Error('Photo counts did not follow coverage status');
photo.getRange('C10').values=[['Available']];
missing.getRange('N10').values=[['Resolved']];
if(missing.getRange('B4').values[0][0]!==119)throw new Error('Unresolved action count did not follow resolution');
if(missing.getRange('D4').values[0][0]!==38)throw new Error('Unrelated image checks disappeared');
missing.getRange('N10').values=[['Open']];
wb.recalculate();
for(const f of formulaChecks){const actual=wb.worksheets.getItem(f.sheet).getRange(f.cell).values[0][0];if(actual!==f.expected)throw new Error(`${f.sheet}!${f.cell} ${actual} != ${f.expected}`);}
const checks=await wb.inspect({kind:'table',sheetId:'Photo Coverage',range:'A4:F5',include:'values,formulas',tableMaxRows:2,tableMaxCols:6,maxChars:2500});
await fs.writeFile(path.join(here,'summary-inspection.ndjson'),checks.ndjson);
const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:50},maxChars:3500});
await fs.writeFile(path.join(here,'formula-error-scan.ndjson'),errors.ndjson);
await fs.mkdir(path.join(here,'previews'),{recursive:true});
const ranges=[
 ['Photo Coverage','A2:H13','01-coverage'],['Photo Coverage','F9:L12','02-roles'],['Missing Pictures','A2:H13','03-missing'],
 ['Identity Review','A2:H13','04-identity'],['Identity Review','B12:H18','05-wall-aliases'],['Wall Circle Sources','A2:H12','06-native-sources'],
 ['Master Catalogue','N25:U29','07-current-examples'],['Specifications','J116:M121','08-spec-image-ids'],
 ['Sets and Context','I56:L59','09-group-overview'],['Missing Pictures','K9:N12','10-action-inputs']];
const previews=[];
for(const [sheetName,range,name]of ranges){const b=await wb.render({sheetName,range,scale:1.5,format:'png'});const dest=path.join(here,'previews',name+'.png');await fs.writeFile(dest,new Uint8Array(await b.arrayBuffer()));previews.push({sheet:sheetName,range,path:dest});}
const file=await SpreadsheetFile.exportXlsx(wb);await file.save(path.join(here,'master-workbook.pending'));
await fs.writeFile(path.join(here,'expected-edit.json'),JSON.stringify({sheets:expected,hyperlinks:[...plan.native_hyperlinks,...extraLinks],formulas:formulaChecks},null,2));
await fs.writeFile(path.join(here,'preview-manifest.json'),JSON.stringify(previews,null,2));
await fs.writeFile(path.join(here,'artifact-authoring-receipt.json'),JSON.stringify({status:'PASS',old_sheets:9,new_sheets:4,targeted_cell_changes:plan.cell_changes.length,new_native_link_rows:extraLinks.length,recalculation:true,coverage_dependency_check:true,action_dependency_check:true,original_temporary_values_restored:true,preview_count:previews.length},null,2));
console.log(JSON.stringify({status:'EXPORTED_PENDING_NATIVE_LINKS_AND_SAVED_FILE_VERIFICATION',new_sheets:4,previews:previews.length}));
