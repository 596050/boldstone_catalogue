import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';

const project=path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const model=JSON.parse(await fs.readFile(path.join(project,'evidence/catalogue_model.json'),'utf8'));
const outDir=path.join(project,'outputs');
const previewDir=path.join(project,'reviews/workbook');
await fs.mkdir(previewDir,{recursive:true});
const wb=Workbook.create();
const sheets={};
for(const name of ['Family Review','Reviewed Sculptures','Sculpture Register','Icarus Details','Offer Links','Offers','Source Specs','Native Source Fields','Assets','Decisions','Reference Notes','Sources']) sheets[name]=wb.worksheets.add(name);
const font='Arial',ink='#223A30',muted='#66766C',header='#304B3D';
const col=n=>{let s='';for(n++;n;n=Math.floor((n-1)/26))s=String.fromCharCode(65+(n-1)%26)+s;return s;};
const literal=v=>typeof v==='string'&&v.startsWith('=')?"'"+v:v??null;
const joined=a=>a.join('; ');
function table(name,title,subtitle,headers,rows,widths,{headerRow=6,numeric=[],dateCols=[],wrapCols=[]}={}){
 const sh=sheets[name];const last=headerRow+rows.length;
 sh.showGridLines=false;
 sh.getRangeByIndexes(0,0,last,headers.length).format.font={name:font,size:10,color:ink};
 sh.getRangeByIndexes(0,0,last,headers.length).format.verticalAlignment='center';
 sh.getRange('A2').values=[[title]];sh.getRange('A2').format.font={name:font,size:15,bold:true,color:ink};
 sh.getRange('A3').values=[[subtitle]];sh.getRange('A3').format.font={name:font,size:10,italic:true,color:muted};
 sh.getRangeByIndexes(headerRow-1,0,1,headers.length).values=[headers];
 for(let start=0;start<rows.length;start+=800){const block=rows.slice(start,start+800).map(row=>row.map(literal));sh.getRangeByIndexes(headerRow+start,0,block.length,headers.length).values=block;}
 const tbl=sh.tables.add(`A${headerRow}:${col(headers.length-1)}${last}`,true,'Tbl_'+name.replace(/[^a-zA-Z0-9]/g,''));
 tbl.style='TableStyleLight1';
 tbl.showFilterButton=true;
 sh.getRangeByIndexes(headerRow-1,0,1,headers.length).format={fill:header,font:{name:font,size:10,bold:true,color:'#FFFFFF'},horizontalAlignment:'center',verticalAlignment:'center',wrapText:true,rowHeight:32};
 sh.getRangeByIndexes(headerRow,0,rows.length,headers.length).format.rowHeight=27;
 for(let c=0;c<headers.length;c++)sh.getRangeByIndexes(0,c,last,1).format.columnWidth=widths[c]??24;
 for(const c of wrapCols)sh.getRangeByIndexes(headerRow,c,rows.length,1).format.wrapText=true;
 for(const c of numeric)sh.getRangeByIndexes(headerRow,c,rows.length,1).setNumberFormat('#,##0');
 for(const c of dateCols)sh.getRangeByIndexes(headerRow,c,rows.length,1).setNumberFormat('yyyy-mm-dd hh:mm:ss');
 for(let r=0;r<rows.length;r++){
  const lines=Math.max(1,...wrapCols.map(c=>String(rows[r][c]??'').split('\n').reduce((n,line)=>n+Math.max(1,Math.ceil(line.length/Math.max(12,(widths[c]??24)*.95))),0)));
  if(lines>1)sh.getRangeByIndexes(headerRow+r,0,1,headers.length).format.rowHeight=Math.min(409,Math.max(27,lines*13+9));
 }
 sh.freezePanes.freezeRows(headerRow);sh.freezePanes.freezeColumns(name==='Assets'?3:2);
 return {sh,last,first:headerRow+1};
}

const groupRows=model.groups.map(g=>[g.group_id,g.family,g.group_name,g.kind,g.design_id,g.assets,g.confirmed_offers.length,g.media_state,g.spec_state,joined(g.confirmed_offers),joined(g.candidate_offers),joined(g.family_reference_offers),g.leaf_id,g.path,g.issues,g.next_action,g.plan_review?'PROVISIONAL':'',g.plan_target,g.sculpture_id]);
const groups=table('Sculpture Register','Dropbox sculpture and media groups','Every current folder is accounted for. A folder is not automatically one manufactured sculpture. Only reviewed designs receive a design ID.',
 ['Register ID','Family','Current member / finish / arrangement label','Record kind','Reviewed design ID','Current files','Direct offer-image links','Image review','Specification status','Direct image-linked offers','Candidate / gallery references','Other family reference offers','Stable folder ID','Current Dropbox path','Open questions / cautions','Next action','Preserved plan flag','Preserved plan label','Reviewed sculpture / finish ID'],groupRows,[23,27,58,32,20,13,16,52,63,50,45,70,44,110,100,85,24,75,27],{numeric:[5,6],wrapCols:[2,3,7,8,9,10,11,13,14,15,17]});
groups.sh.getRange(`H7:I${groups.last}`).conditionalFormats.add('containsText',{text:'OPEN',format:{fill:'#FFF0CF',font:{color:'#775211'}}});

const families=table('Family Review','Wall sculpture specification register','Incremental review of the current library. Export values are dated source claims; specifications are not copied across unverified members.',
 ['Review batch','Family','Current groups','Current files','Groups with image links','Related native offers','Provisional storage groups','Family review state','Next action','Stable family ID'],model.families.map(f=>[f.batch_id,f.family,f.groups,f.assets,f.groups_with_image_links,f.linked_offers,f.provisional_groups,f.review_state,f.next_action,f.family_id]),[20,30,15,15,20,20,24,58,90,45],{headerRow:12,numeric:[2,3,4,5,6],wrapCols:[7,8]});
families.sh.tabColor=header;
families.sh.getRange('A4:H4').values=[['Families',null,'Groups',null,'Files',null,'Offers',null]];
families.sh.getRange('B4').formulas=[[`=COUNTA('Family Review'!B13:B${families.last})`]];
families.sh.getRange('D4').formulas=[[`=COUNTA('Sculpture Register'!A7:A${groups.last})`]];
families.sh.getRange('A6:H6').values=[['Groups linked',null,'Spec claims',null,'Native rows',model.counts.native_rows,'Files viewed',model.counts.individually_viewed_assets]];
families.sh.getRange('B6').formulas=[[`=COUNTIFS('Sculpture Register'!G7:G${groups.last},">0")`]];
families.sh.getRange('A8:H8').values=[['Families reviewed',model.counts.families_reviewed_with_open_questions,'Designs',model.counts.reviewed_designs,'Finish records',model.counts.reviewed_sculpture_finish_records,'Next batch','Ammonite']];
families.sh.getRange('A10').values=[['Inventory membership is complete. Group identity, material, dimensions, finish, quantities and image provenance are reviewed separately.']];
families.sh.getRange('A10').format.font={name:font,size:10,italic:true,color:muted};
families.sh.getRange('A4:H8').format.rowHeight=28;
for(const c of ['B4','D4','F4','H4','B6','D6','F6','H6','B8','D8','F8']){families.sh.getRange(c).format.font={name:font,size:13,bold:true,color:ink};families.sh.getRange(c).format.horizontalAlignment='center';families.sh.getRange(c).setNumberFormat('#,##0');}
families.sh.getRange(`H13:H${families.last}`).conditionalFormats.add('containsText',{text:'OPEN',format:{fill:'#FFF0CF',font:{color:'#775211'}}});

const offerByKey=new Map(model.offers.map(o=>[o.offer_key,o]));
const reviewedRows=model.reviewed_sculptures.map(r=>[r.sculpture_id,r.design_id,r.title,r.finish,r.files,joined(r.group_ids),joined(r.offer_keys),r.offer_keys.map(k=>offerByKey.get(k).sku).join('; '),r.dimensions_cm||'Not found for this finish',r.weight_kg||'Not stated for this finish',r.material||'Not found for this finish',r.fixing||'Not found for this finish',r.public_price??null,r.public_price_currency??'',r.public_observed??'',r.review_state,r.source_scope,r.unresolved,r.shopify_state,r.public_url??'']);
const sculptureSummary=table('Reviewed Sculptures','Reviewed sculpture designs and finishes','First two families: 11 design/finish records, including detail-only candidates and context-only variants. Blank source fields are not borrowed from other finishes.',
 ['Sculpture / finish ID','Design ID','Reviewed design name','Finish / depiction','Current files','Mapped register groups','Native Squarespace offer','Source SKU','Source dimensions (cm, source order)','Source weight (kg)','Source material','Source fixing','Public price','Currency','Public observation','Review state','Source and applicability','Questions / missing facts','Shopify source state','Public source URL'],reviewedRows,[27,20,44,70,14,65,43,27,72,31,100,100,18,13,20,105,120,130,100,120],{numeric:[4],wrapCols:[2,3,5,6,7,8,9,10,11,15,16,17,18,19]});
sculptureSummary.sh.getRange(`M7:M${sculptureSummary.last}`).setNumberFormat('#,##0.00');
sculptureSummary.sh.getRange(`P7:P${sculptureSummary.last}`).conditionalFormats.add('containsText',{text:'PROVISIONAL',format:{fill:'#FFF0CF',font:{color:'#775211'}}});
sculptureSummary.sh.getRange(`P7:P${sculptureSummary.last}`).conditionalFormats.add('containsText',{text:'OPEN',format:{fill:'#FFF0CF',font:{color:'#775211'}}});
sculptureSummary.sh.tabColor='#647B68';

const batch=model.batch01;
const batchRows=batch.specifications.map(r=>[r.field,r.value,r.unit,r.scope,r.status,r.field==='Public price'?'https://boldstonesculpture.com/buy/p/icarus-wall-sculpture':r.field==='Material class'?'SS Wall Products row 66; https://jesmonite.com/product-range/ac730/':'SS Wall Products row 66; product ID '+batch.squarespace_product_id]);
const reviewed=table('Icarus Details','Batch 01: Icarus / Abstract Cave Paintings 1','BSC-0001. All 13 current files viewed. Material, weight, fixing, packing and context-image provenance remain open.',
 ['Specification','Source value','Unit','Applies to','Verification state','Evidence'],batchRows,[33,100,18,72,65,115],{wrapCols:[0,1,3,4,5]});
reviewed.sh.tabColor='#647B68';
reviewed.sh.getRange(`E7:E${reviewed.last}`).conditionalFormats.add('containsText',{text:'OPEN',format:{fill:'#FFF0CF',font:{color:'#775211'}}});
reviewed.sh.getRange(`E7:E${reviewed.last}`).conditionalFormats.add('containsText',{text:'CONFLICT',format:{fill:'#F7DDDA',font:{color:'#8D332B',bold:true}}});
reviewed.sh.getRange(`E7:E${reviewed.last}`).conditionalFormats.add('containsText',{text:'MISSING',format:{fill:'#FFF0CF',font:{color:'#775211'}}});

const linkRows=model.links.map(r=>[r.link_id,r.offer_key,r.family,r.group_id,r.basis,r.scope,r.accepted_image?'YES':'NO',r.asset_id,r.leaf_id,r.detail,r.image_correspondence?'YES':'NOT ASSERTED']);
table('Offer Links','Native offers linked to Dropbox','Image-confirmed links, historical family links and proposals retain separate scopes. None is a cross-platform merge instruction.',
 ['Link ID','Native offer key','Family','Register ID','Evidence class','Link scope','Direct member link accepted','Source file ID','Source folder ID','Cautions','Specific gallery image correspondence'],linkRows,[24,43,28,24,57,84,25,44,44,130,30],{wrapCols:[4,5,9,10]});
const offerRows=model.offers.map(o=>{const p=o.raw;return[o.offer_key,o.platform,o.title,o.sku,o.product_id||o.handle,o.source_sheet,o.source_row,o.related_sq,p.Price??p['Variant Price']??'',p.Weight??p['Variant Grams']??'',o.platform==='Squarespace'?'Unencoded export weight unit':'Variant Grams field = g',p.Length??'',p.Width??'',p.Height??'',p.Stock??p['Variant Inventory Qty']??'',p.Visible??p.Status??'',p['Product URL']??'',p['Variant Weight Unit']??''];});
const offers=table('Offers','Squarespace and Shopify source offers','127 version-specific offers: 80 Squarespace, 38 main Shopify, six older-format and three seed records. Historical versions remain separate.',
 ['Native offer key','Source platform / version','Source title','Source SKU','Product ID / handle','Source sheet','Source row','Related Squarespace ID','Native price','Native weight','Weight unit policy','Native length','Native width','Native height','Native stock','Native visibility / status','Squarespace slug','Shopify weight display unit'],offerRows,[43,26,65,28,40,24,12,35,18,18,44,18,18,18,22,25,55,24],{numeric:[6],wrapCols:[2,10]});
families.sh.getRange('H4').formulas=[[`=COUNTA('Offers'!A7:A${offers.last})`]];

const factRows=model.facts.map(r=>[r.fact_id,r.offer_key,r.platform,r.title,r.sku,r.field,r.value,r.unit,r.scope,r.status,r.source_sheet,r.source_row,r.locator]);
const specs=table('Source Specs','All extracted specification claims','Statements and raw values remain attached to native offers and source versions. A matching image does not validate measurements or material composition.',
 ['Specification ID','Native offer key','Platform / version','Source title','SKU','Specification topic','Source claim or raw value','Unit policy','Claim scope','Verification state','Source sheet','Source row','Source field / location'],factRows,[24,43,26,60,27,42,110,35,110,53,24,12,100],{numeric:[11],wrapCols:[3,5,6,7,8,9,12]});
families.sh.getRange('D6').formulas=[[`=COUNTA('Source Specs'!A7:A${specs.last})`]];

const nativeRows=model.native_fields.map(r=>[r.row_key,r.offer_key,r.platform,r.source_sheet,r.source_row,r.field,r.part,r.parts,r.raw_value,r.numeric_value,r.unit]);
table('Native Source Fields','Exact native export values','6,028 populated native values from 349 rows. Long values use ordered parts and reassemble without loss. Full schemas, including blanks, are retained in evidence/native_records.json.',
 ['Native row key','Native offer key','Source platform','Source sheet','Source row','Native field','Part','Parts','Exact raw source text','Numeric value where unambiguous','Unit / interpretation'],nativeRows,[26,43,25,24,12,42,9,9,120,25,49],{numeric:[4,6,7],wrapCols:[5,8,10]});

const assetRows=model.assets.map(r=>[r.file_id,r.group_id,r.family,r.group_name,r.name,r.bytes,r.modified,r.path,r.review,r.binary_verified?'YES':'NO',r.original_register?'YES':'NO']);
const assets=table('Assets','Complete current Dropbox file inventory','Every one of the 6,656 files has a current parent-group mapping. Historical source IDs absent from this snapshot are not declared deleted.',
 ['Dropbox stable file ID','Register ID','Family','Current group','Current filename','Bytes','Server modified UTC','Current namespace path','Individual review scope','Downloaded binary verified','In source asset register'],assetRows,[44,24,30,65,90,16,27,130,96,24,24],{numeric:[5],dateCols:[6],wrapCols:[3,4,7,8]});
families.sh.getRange('F4').formulas=[[`=COUNTA('Assets'!A7:A${assets.last})`]];

table('Decisions','Questions and conflicts to resolve','Original catalogue issues remain open. New batch questions are keyed to the native record and design, so decisions survive sorting and refreshes.',
 ['Issue ID','Scope','Priority','Evidence / question','Required decision or evidence','Status','Affected native offers','Source'],model.issues.map(r=>[r.issue_id,r.scope,r.priority,r.description,r.action,r.status,r.offer_keys,r.source]),[23,56,15,115,115,30,82,80],{wrapCols:[1,3,4,5,6,7]});
table('Reference Notes','Preserved historical specifications and cautions','Brochure, manufacturing, trade and older Shopify text are retained as dated references. They do not override native offer specifications.',
 ['Reference row','Record type','Product / family','Full source note','Finish as stated','Suitability as stated','Qualification','Source path','Source date / status'],model.reference_notes.map(r=>[r._row,r['Record type'],r['Product / family'],r['Full description or specification note'],r.Finish,r.Suitability,r['SEO text or qualification'],r['Source path'],r['Source date / status']]),[15,35,45,135,55,60,110,110,55],{numeric:[0],wrapCols:[2,3,4,5,6,7,8]});

const sources=model.source_register.map(r=>[r['Source ID'],r.Source,r['Date / observation'],r['File / object reference'],r['Scope and limitations'],r['Source URL / locator']]);
sources.unshift(['CURRENT-DB-20261016','Complete targeted wall-library inventory',model.inventory_time,'evidence/wall_inventory_2026-10-16.json','63 families, 347 groups, 6,656 files. Metadata membership only; no physical identity inferred.',model.scope]);
sources.push(['BATCH01','Abstract Cave Paintings / Icarus','2026-10-16','reviews/batch01.json','All 13 family files viewed; source-stated specs retained with four owner questions.','']);
sources.push(...batch.sources.map(r=>[r.id,'Public product / manufacturer read',r.observed,r.url,r.finding,r.url]));
sources.push(['BATCH02','Acanthus','2026-10-16','reviews/batch02.json','All 76 files viewed; 16 folders accounted for, including one empty. Four designs, ten finish records; six source and identity questions open.','']);
sources.push(...model.batch02.sources.map(r=>[r.id,'Batch 02 native source / public page verification',r.observed,r.url,r.finding,r.url]));
sources.push(['ESTABLISHED-IMAGE-REVIEW','Individual image review of previously family-linked offers','2026-10-16','evidence/established_image_decisions.json','17 current source images downloaded and content-hash verified. 13 direct member links and four gallery references with incompatible or unresolved composition.','']);
sources.push(['SOURCE-ID-LINEAGE','Retained-original / JPEG successor lineage','2026-10-16','evidence/source_id_lineage.json','Historical aliases guide image search only. Every newly accepted current image was downloaded and content-hash verified.','']);
table('Sources','Source versions and evidence','Current inventory, native source facts, historical references and review decisions retain separate dates and scopes.',
 ['Source ID','Source','Observation / date','Object or file reference','Scope and limitations','URL or namespace locator'],sources,[31,70,48,110,140,115],{wrapCols:[1,2,3,4,5]});

wb.recalculate();
const inspect=await wb.inspect({kind:'table',range:'Family Review!A4:H8',include:'values,formulas',tableMaxRows:5,tableMaxCols:8,maxChars:4500});
console.log(inspect.ndjson);
const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#NUM!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:30},summary:'Final formula error scan',maxChars:1500});
console.log(errors.ndjson);
// Render every sheet at its readable opening range, and the remaining Batch 01 facts.
for(const [name] of Object.entries(sheets)){
 const range=name==='Family Review'?'A1:I17':name==='Reviewed Sculptures'?'A1:E11':name==='Icarus Details'?'A1:E15':name==='Native Source Fields'?'D1:K11':name==='Source Specs'?'D1:J11':name==='Assets'?'A1:G10':name==='Sculpture Register'?'A1:I11':'A1:F10';
 const blob=await wb.render({sheetName:name,range,scale:1,format:'png'});
 await fs.writeFile(path.join(previewDir,name.replaceAll(' ','_')+'.png'),new Uint8Array(await blob.arrayBuffer()));
 console.log('Rendered '+name);
}
const tail=await wb.render({sheetName:'Icarus Details',range:'A16:E26',scale:1,format:'png'});await fs.writeFile(path.join(previewDir,'Icarus_Details_tail.png'),new Uint8Array(await tail.arrayBuffer()));
for(const range of ['H6:P11','H14:P17']){const detail=await wb.render({sheetName:'Reviewed Sculptures',range,scale:1,format:'png'});await fs.writeFile(path.join(previewDir,'Reviewed_Sculptures_'+range.replace(':','_')+'.png'),new Uint8Array(await detail.arrayBuffer()));}
const xlsx=await SpreadsheetFile.exportXlsx(wb);const output=path.join(outDir,'Boldstone_Sculpture_Specification_Register_2026-10-16.xlsx');await xlsx.save(output);
console.log(JSON.stringify({output,sheets:Object.keys(sheets).length,counts:model.counts}));
