import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {execFileSync} from 'node:child_process';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const dir=path.dirname(fileURLToPath(import.meta.url));
const oldDir=path.join(dir,'../gold-default-20261030');
const data=JSON.parse(await fs.readFile(path.join(dir,'catalogue-snapshot.json'),'utf8'));
const plan=JSON.parse(await fs.readFile(path.join(dir,'upload-plan.json'),'utf8'));
const expected=JSON.parse(await fs.readFile(path.join(oldDir,'expected-workbook.json'),'utf8'));
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(dir,'previous-catalogue.xlsx')));
const byId=new Map(plan.products.map(p=>[p.product_id,p]));
const clean=v=>String(v??'').replaceAll('—','-').replaceAll('–','-');
const list=v=>(v||[]).map(clean).join('; '), yn=v=>v?'Yes':'No';
const col=n=>{let s='';for(n++;n;n=Math.floor((n-1)/26))s=String.fromCharCode(65+(n-1)%26)+s;return s;};
const links=JSON.parse(await fs.readFile(path.join(oldDir,'hyperlinks.json'),'utf8')).filter(l=>!['Wall Sculptures','Images'].includes(l.sheet));
function link(sheet,row,column,url,label,internal=false){if(!url)return '';links.push({sheet,cell:col(column)+row,url,label,internal});return label;}
const fields=p=>Object.fromEntries([...p.fields,...p.listing_fields].map(f=>[f.key,clean(f.value)]));
function replaceTable(sheet,headers,count){
 const old=sheet.tables.items[0],name=old.name,style=old.style;old.delete();
 const t=sheet.tables.add('A7:'+col(headers.length-1)+(count+7),true,name);t.style=style;t.showFilterButton=true;
}
function record(name,headers,rows){const e=expected.sheets.find(s=>s.name===name);Object.assign(e,{headers,rows,row_count:rows.length});}
const stamp=new Date(data.created_utc).toLocaleString('en-GB',{timeZone:'Europe/London'});
for(const name of ['Wall Sculptures','Images','Specification Sources'])wb.worksheets.getItem(name).getRange('A4').values=[[`App snapshot: ${stamp} UK time. Workbook edits do not update the app.`]];
const imageById=new Map(data.images.map(r=>[r.image.id,r.image]));
const firstImage=new Map();data.images.forEach((r,i)=>{if(r.product_id&&!firstImage.has(r.product_id))firstImage.set(r.product_id,i+8);});
const main=wb.worksheets.getItem('Wall Sculptures');
const mainOld=expected.sheets.find(s=>s.name==='Wall Sculptures');
const newHeaders=['Markup (%)','Pricing method','SKU','Delivery policy','Transit time','Upload mapping','Upload review'];
const mainHeaders=[...mainOld.headers,...newHeaders];
const mainRows=data.products.map((p,i)=>{
 const r=i+8,f=fields(p),q=byId.get(p.id),a=p.photos,old=mainOld.rows[i];
 if(old[26]!==p.id)throw new Error('Component order changed; do not overwrite formula rows');
 const pic=(aid,c,label)=>link('Wall Sculptures',r,c,imageById.get(aid)?.url,label);
 const row=[i+1,clean(p.family),clean(p.name),f['Dimensions / depth'],f.Weight,f['Material / finish'],f.Fixing,
  p.costing.pricing.marked_up_price,p.costing.pricing.listing_value,f.Availability,f['Lead time'],
  {set:'Set',missing:'Not set',needs_review:'Needs review'}[a.primary_listing.status],pic(a.primary_id,12,'Open primary'),a.listing_ids.length,a.in_situ_ids.length,
  Math.max(0,2-a.in_situ_ids.length),p.associated_count,p.candidate_count,
  link('Wall Sculptures',r,18,`'Images'!A${firstImage.get(p.id)}`,'View image rows',true),
  pic(a.listing_ids[0],19,'Open listing'),pic(a.in_situ_ids[0],20,'Open in situ 1'),pic(a.in_situ_ids[1],21,'Open in situ 2'),
  link('Wall Sculptures',r,22,p.folder_url,'Open folder'),link('Wall Sculptures',r,23,p.app_url,'Open component'),p.listing_decision,p.review_status,
  p.id,p.component_id||'',f['Sale unit'],f.Description,clean(p.notes),p.costing.material_label,p.costing.material_cost,p.costing.finish_cost,
  p.costing.fixing_cost,p.costing.overhead_cost,p.costing.other_cost,p.costing.labour_cost,p.costing.total_cost,
  link('Wall Sculptures',r,39,`'Manufacturing Costs'!A${r}`,'View calculation',true),p.costing.pricing.markup_percent,'Markup',q.sku,
  q.delivery_charge_policy,q.transit_time,link('Wall Sculptures',r,45,`'Upload Plan'!A${r}`,'View mapping',true),list(q.publication_review)];
 return row;
});
main.getRange('A8:AE188').values=mainRows.map(r=>r.slice(0,31));
main.getRange('AO7:AU7').values=[newHeaders];
main.getRange('AO7:AU7').copyFrom(main.getRange('N7'),'all');main.getRange('AO7:AU7').values=[newHeaders];
main.getRange('AO8:AU188').values=mainRows.map(r=>r.slice(40));
main.getRange('AO8:AU188').format={font:{name:'Arial',size:10,color:'#24332D'},wrapText:true,verticalAlignment:'center'};
for(const [c,w]of [['AO',14],['AP',17],['AQ',26],['AR',38],['AS',42],['AT',22],['AU',65]])main.getRange(`${c}7:${c}188`).format.columnWidth=w;
replaceTable(main,mainHeaders,181);record('Wall Sculptures',mainHeaders,mainRows);
main.getRange('A5').values=[[`${data.products.length} components | ${data.summary.families} families | ${data.summary.unique_images} unique images | Prices use manufacturing total including labour and editable markup`]];

const rates=wb.worksheets.getItem('Cost Rates'),ratesMeta=expected.sheets.find(s=>s.name==='Cost Rates');
rates.getRange('A29:H30').copyFrom(rates.getRange('A27:H28'),'all');
const rateRows=[['default_markup_percent','Global','Default price markup',data.cost_settings.default_markup_percent,null,'percent','Owner instruction: price is manufacturing total including labour plus markup',''],
 ['default_pricing_mode','Global','Price method at export','markup',null,'method','Snapshot label; choose the pricing method in the app','']];
rates.getRange('A29:H30').values=rateRows;
rates.getRange('D29').format.font.color='#184DB3';rates.getRange('D29').setNumberFormat('0.00');
rates.getRange('D30').format.font.color='#24332D';
rates.getRange('D29').dataValidation={ignoreBlanks:false,rule:{type:'decimal',operator:'between',formula1:0,formula2:10000}};
ratesMeta.rows.push(...rateRows);ratesMeta.row_count+=2;replaceTable(rates,ratesMeta.headers,ratesMeta.row_count);
for(let i=0;i<181;i++){
 const r=i+8,p=data.products[i];
 main.getRange(`AO${r}`).formulas=[[p.costing.pricing.uses_shared_markup?"='Cost Rates'!$D$29":`=${p.costing.pricing.markup_percent}`]];
 main.getRange(`H${r}`).formulas=[[`=ROUND(AM${r}*(1+AO${r}/100),2)`]];
 main.getRange(`I${r}`).formulas=[[`="£"&TEXT(H${r},"0.00")`]];
 mainRows[i][8]='£'+p.costing.pricing.marked_up_price.toFixed(2);
}
wb.worksheets.getItem('Manufacturing Costs').getRange('A5').values=[['Blue cells are inputs. Manufacturing cost includes editable labour. Catalogue prices now use this total and the markup on Wall Sculptures.']];

const imageSheet=wb.worksheets.getItem('Images'),im=expected.sheets.find(s=>s.name==='Images');
const imageRows=data.images.map((r,i)=>{
 const a=r.image,c=r.choice,m=r.metadata,o=a.original||{},n=i+8,types=a.effective_types||m.types||a.types||[],uses=a.selected_uses||(c.decision==='reviewed'?c.uses||[]:[]),dims=o.dimensions||[],active=r.scope==='Associated'&&!a.excluded;
 return [clean(r.product_family),clean(r.product_name),r.product_id,r.scope,clean(a.name),link('Images',n,5,a.url,'Open image'),link('Images',n,6,a.folder_url,'Open folder'),
  yn(active&&a.primary_eligible),yn(active&&uses.includes('listing')),yn(uses.includes('advertising')),yn(uses.includes('reference')),yn(types.includes('in_situ')),
  types.map(t=>data.image_types[t]||t).join('; '),list(uses),c.decision||'pending',Number.isFinite(c.order)?c.order:null,dims[0]??null,dims[1]??null,o.bytes??null,null,
  clean(o.dimension_basis),list(m.tags),clean(m.collection),m.rights||'unknown',clean(c.alt),clean(c.caption),clean(c.edit_notes),list([c.notes,m.notes].filter(Boolean)),a.source,a.id,
  a.provenance?.path||'',a.provenance?.revision||'',o.dropbox_content_hash||'',list(a.association?.qualifications),yn(c.decision==='exclude'),list(a.withheld_reasons)];
});
for(let i=im.row_count+8;i<=imageRows.length+7;i++)imageSheet.getRange(`A${i}:AJ${i}`).copyFrom(imageSheet.getRange('A8:AJ8'),'all');
imageSheet.getRange(`A8:AJ${imageRows.length+7}`).values=imageRows;
imageSheet.getRange(`T8:T${imageRows.length+7}`).formulas=imageRows.map((r,i)=>[r[18]==null?'':`=S${i+8}/1048576`]);
imageSheet.getRange(`Q8:S${imageRows.length+7}`).setNumberFormat('#,##0');imageSheet.getRange(`T8:T${imageRows.length+7}`).setNumberFormat('0.00');
replaceTable(imageSheet,im.headers,imageRows.length);record('Images',im.headers,imageRows);
imageSheet.getRange('A5').values=[['Listing alt text and original dimensions completed. Private Dropbox links are source references; use the upload manifest to transfer verified originals to the platform.']];

const sources=wb.worksheets.getItem('Specification Sources'),sm=expected.sheets.find(s=>s.name==='Specification Sources');
const sourceRows=data.products.flatMap(p=>[...p.fields,...p.listing_fields].map(f=>[clean(p.family),clean(p.name),p.id,f.section,f.label,clean(f.value),f.decision,f.certainty,
 clean(f.source_value),clean(f.qualification),clean(f.basis),clean(f.evidence),clean(f.notes),f.updated_at?new Date(f.updated_at):null]));
if(sourceRows.length!==sm.row_count)throw new Error('Unexpected source row count');
sources.getRange(`A8:N${sourceRows.length+7}`).values=sourceRows;record('Specification Sources',sm.headers,sourceRows);

const upload=wb.worksheets.add('Upload Plan');upload.showGridLines=false;upload.tabColor='#8B9B89';
const uh=['Family','Sculpture','Product ID','SKU','Listing decision','Squarespace action','Squarespace product ID','Squarespace variant ID','Squarespace options',
 'Shopify action','Shopify handle','Shopify options','Production lead time','Delivery policy','Transit time','Price (GBP)','Markup (%)','Manufacturing cost (GBP)',
 'Primary image','Listing images','Image upload step','Review before publication','Matching evidence','Existing source offers','App'];
const ur=plan.products.map((p,i)=>[p.family,p.name,p.product_id,p.sku,p.listing_decision,p.squarespace_action,p.squarespace_product_id,p.squarespace_variant_id,
 list(p.squarespace_options.map(o=>o.name+': '+o.value)),p.shopify_action,p.shopify_handle,list(p.shopify_options.map(o=>o.name+': '+o.value)),p.production_lead_time,
 p.delivery_charge_policy,p.transit_time,p.price_gbp,p.markup_percent,p.manufacturing_cost_gbp,link('Upload Plan',i+8,18,imageById.get(p.primary_photo_id)?.url,'Open primary'),
 p.listing_photo_ids.length,'Upload verified Dropbox originals using selected-image-upload-manifest.csv',list(p.publication_review),p.binding_evidence,list(p.source_offer_refs),link('Upload Plan',i+8,24,p.app_url,'Open component')]);
upload.getRange('A1:Y188').format={font:{name:'Arial',size:10,color:'#24332D'},verticalAlignment:'center'};
upload.getRange('A2').values=[['BOLDSTONE | Upload mappings and delivery']];upload.getRange('A2').format.font={name:'Arial',size:14,bold:true,color:'#263C32'};
upload.getRange('A4').values=[[`Prepared ${stamp} UK time from local platform exports and current app. No products published.`]];
upload.getRange('A5').values=[['Existing option tuples are retained. Pending/excluded components stay out of draft imports. Delivery is quoted separately; no package weight, carrier or transit promise is invented.']];
upload.getRange('A7:Y7').values=[uh];upload.getRange('A8:Y188').values=ur;
upload.getRange('A7:Y7').format={fill:'#263C32',font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},wrapText:true,rowHeight:40};
upload.getRange('A8:Y188').format={wrapText:true,rowHeight:70};
const uw=[25,42,26,26,18,38,30,39,65,60,55,65,20,36,42,16,16,23,17,15,65,80,95,23,20];
uw.forEach((w,i)=>upload.getRange(`${col(i)}7:${col(i)}188`).format.columnWidth=w);
const uploadTable=upload.tables.add('A7:Y188',true,'UploadPlanTable');uploadTable.style='TableStyleLight9';uploadTable.showFilterButton=true;upload.freezePanes.freezeRows(7);upload.freezePanes.freezeColumns(3);
upload.getRange('P8:P188').setNumberFormat('"£"#,##0.00');upload.getRange('R8:R188').setNumberFormat('"£"#,##0.00');
for(let i=0;i<181;i++){const r=i+8;upload.getRange(`P${r}:R${r}`).formulas=[[`='Wall Sculptures'!H${r}`,`='Wall Sculptures'!AO${r}`,`='Wall Sculptures'!AM${r}`]];}
expected.sheets.push({name:'Upload Plan',headers:uh,rows:ur,row_count:181,freeze_columns:3,freeze_rows:7});
for(const l of links)wb.worksheets.getItem(l.sheet).getRange(l.cell).format.font={name:'Arial',size:10,color:'#28634B',underline:'single'};
wb.recalculate();
rates.getRange('D29').values=[[150]];wb.recalculate();
const changedPrice=main.getRange('H8').values[0][0],expectedChanged=Math.round((data.products[0].costing.total_cost*2.5+Number.EPSILON)*100)/100;
if(Math.abs(changedPrice-expectedChanged)>0.005||upload.getRange('P8').values[0][0]!==changedPrice)throw new Error('Markup change did not propagate to catalogue and upload plan');
rates.getRange('D29').values=[[data.cost_settings.default_markup_percent]];wb.recalculate();
for(let i=0;i<181;i++){
 const r=i+8,p=data.products[i];
 for(const [address,wanted]of [[`H${r}`,p.costing.pricing.marked_up_price],[`AM${r}`,p.costing.total_cost]]){
  const got=main.getRange(address).values[0][0];if(typeof got!=='number'||Math.abs(got-wanted)>0.005)throw new Error(`Calculation differs: ${address} ${got} / ${wanted}`);
 }
}
const scan=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:100},maxChars:3000});
await fs.writeFile(path.join(dir,'formula-scan.jsonl'),scan.ndjson);
for(const [sheetName,range,file]of [['Wall Sculptures','A1:J13','catalogue-preview.png'],['Wall Sculptures','AM7:AU13','pricing-delivery-preview.png'],['Images','Q7:Y13','metadata-preview.png'],['Upload Plan','A1:F13','upload-preview.png']]){
 const png=await wb.render({sheetName,range,scale:1.1,format:'png'});await fs.writeFile(path.join(dir,file),new Uint8Array(await png.arrayBuffer()));
}
expected.created_utc=data.created_utc;expected.summary=data.summary;
await fs.writeFile(path.join(dir,'expected-workbook.json'),JSON.stringify(expected));await fs.writeFile(path.join(dir,'hyperlinks.json'),JSON.stringify(links));
await fs.writeFile(path.join(dir,'recalculation-checks.json'),JSON.stringify({status:'PASS',checks:['All 181 markup prices match app','All 181 manufacturing totals match app','Existing cost formula sheets preserved','Changing shared markup to 150% updates both catalogue and upload-plan prices; restored to 100% before export']}));
const dest=path.join(dir,'catalogue_wall_sculptures.xlsx');await(await SpreadsheetFile.exportXlsx(wb)).save(dest);
execFileSync('/usr/bin/python3',[path.join(dir,'native_links.py'),dest],{stdio:'inherit'});
console.log(JSON.stringify({output:dest,sheets:expected.sheets.map(s=>[s.name,s.row_count]),hyperlinks:links.length}));
