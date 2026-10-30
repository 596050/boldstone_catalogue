import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {Workbook, SpreadsheetFile, FileBlob} from '@oai/artifact-tool';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '../../..');
const source = path.join(here, 'canonical-products.json');
const data = JSON.parse(await fs.readFile(source, 'utf8'));
const outputDir = path.join(root, 'outputs/01a13fbf-1cbc-7511-8416-cf339051083e');
await fs.mkdir(outputDir, {recursive:true});
await fs.mkdir(path.join(here, 'previews'), {recursive:true});
const output = path.join(outputDir, 'Boldstone_Individual_Products_Reconciled_2026-10-20.xlsx');
if(process.argv.includes('--render-saved-closure')){
 const saved=await SpreadsheetFile.importXlsx(await FileBlob.load(output));
 const refRow=data.references.findIndex(r=>r.reference_id==='REF-G050')+7;
 const mixRow=data.scope_reconciliation.findIndex(r=>r.source_scope==='BC-MIX-SPIRALS|BASE')+7;
 const ranges=[['References',`A${refRow}:E${refRow}`],['References',`F${refRow}:J${refRow}`],['Reconciliation',`A${mixRow}:F${mixRow}`],['Needs information','A13:D21']];
 const closure=[];
 for(let i=0;i<ranges.length;i++){
  const [sheetName,range]=ranges[i];const blob=await saved.render({sheetName,range,scale:1,format:'png'});
  const dest=path.join(here,'previews',`${String(i+19).padStart(2,'0')}-saved-closure.png`);
  await fs.writeFile(dest,new Uint8Array(await blob.arrayBuffer()));closure.push({sheet:sheetName,range,path:dest});
 }
 await fs.writeFile(path.join(here,'saved-closure-preview-manifest.json'),JSON.stringify(closure,null,2));
 console.log(JSON.stringify({saved_workbook_rendered:true,views:closure.length}));process.exit(0);
}
const wb = Workbook.create();
const ink = '#28362D', green = '#344E40', muted = '#6D776F', amber = '#FFF3D6';
const links = [], views = {}, expected = {};
const fields = ['Dimensions / depth','Weight','Material / finish','Fixing','Individual price','Availability'];
const readable = code => String(code??'').toLowerCase().replaceAll('_',' ').replace(/^./,c=>c.toUpperCase());
const coverageLabel = code => ({
 'SUPPORTED_CURRENT_TARGETS_WITH_SOURCE_MATCH_LIMITS':'Current products linked; source limits retained',
 'COVERED_FAMILY_EXACT_SOURCE_SCOPE_PENDING':'Family linked; exact source scope unresolved',
 'COVERED_FAMILY_EXACT_SCOPE_PENDING':'Family linked; exact source scope unresolved',
 'SOURCE_CANDIDATE_ONLY':'Source candidate',
 'REFERENCE_ONLY_HISTORICAL_DRAFT':'Historical draft reference',
 'EXACT_CURRENT_SCOPE_SUPPORTED':'Current review scope linked',
 'REFERENCE_ONLY':'Reference only'
}[code]??readable(code));
const col = n => {let s=''; for(n++;n;n=Math.floor((n-1)/26))s=String.fromCharCode(65+(n-1)%26)+s; return s;};
const literal = v => typeof v==='string' && v.startsWith('=') ? "'"+v : v ?? '';
const hyperlink = (url,label) => url ? {url,label} : '';
const value = v => v && typeof v==='object' && 'url' in v ? v.label : literal(v);
function lineCount(text, width) {
  return String(text ?? '').split('\n').reduce((n,part)=>n+Math.max(1,Math.ceil(part.length/Math.max(10,width*.77))),0);
}
function add(name,title,note,headers,rows,widths) {
  const sheet = wb.worksheets.add(name), last = 6+rows.length;
  sheet.showGridLines = false;
  sheet.tabColor = ['Products','Specifications'].includes(name) ? green : '#8A9B8D';
  const area=sheet.getRangeByIndexes(0,0,last,headers.length);
  area.format.font={name:'Arial',size:10,color:ink};
  area.format.verticalAlignment='center';
  sheet.getRange('A2').values=[[title]];
  sheet.getRange('A2').format.font={name:'Arial',size:15,bold:true,color:ink};
  sheet.getRange('A3').values=[[note]];
  sheet.getRange('A3').format.font={name:'Arial',size:10,italic:true,color:muted};
  sheet.getRangeByIndexes(5,0,1,headers.length).values=[headers];
  if(rows.length)sheet.getRangeByIndexes(6,0,rows.length,headers.length).values=rows.map(row=>row.map(value));
  const table=sheet.tables.add(`A6:${col(headers.length-1)}${last}`,true,'BS_'+name.replaceAll(' ','_'));
  table.style='TableStyleLight1';table.showFilterButton=true;
  sheet.getRangeByIndexes(5,0,1,headers.length).format={fill:green,font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},horizontalAlignment:'center',verticalAlignment:'center',wrapText:true,rowHeight:36};
  widths.forEach((width,i)=>sheet.getRangeByIndexes(0,i,last,1).format.columnWidth=width);
  if(rows.length)sheet.getRangeByIndexes(6,0,rows.length,headers.length).format.wrapText=true;
  rows.forEach((row,i)=>{
    const count=Math.max(...row.map((v,j)=>lineCount(value(v),widths[j])),1);
    const height=Math.min(409,Math.max(42,count*13+10));
    sheet.getRangeByIndexes(i+6,0,1,headers.length).format.rowHeight=height;
    row.forEach((v,j)=>{if(v && typeof v==='object' && 'url' in v){
      const cell=`${col(j)}${i+7}`;
      links.push({sheet:name,cell,target:v.url,label:v.label});
      sheet.getRange(cell).format.font={name:'Arial',size:10,color:'#245F9E'};
    }});
  });
  sheet.freezePanes.freezeRows(6);sheet.freezePanes.freezeColumns(2);
  expected[name]={headers,rows:rows.map(r=>r.map(value)),first:7,last,widths};
  views[name]={sheet,first:7,last};
  return sheet;
}

let detailRows=[];
const detailStart={};
for(const p of data.products){
  detailStart[p.product_id]=7+detailRows.length;
  for(const field of fields){
    const f=p.specifications[field];
    const states=[...new Set(f.assertions.map(a=>a.state))].join('\n\n');
    const basis=[...new Set(f.assertions.map(a=>a.basis))].join('\n\n');
    detailRows.push([p.product_id,p.name,field,f.display,states,basis,f.assertions.map(a=>a.source_scope).join('\n'),f.assertions.map(a=>a.proposal_id).join('\n')]);
  }
}
const productRows=data.products.map(p=>[p.product_id,p.name,...fields.map(f=>p.specifications[f].display),p.orientation_options.join(' / '),hyperlink(p.image_url,'Image'),hyperlink(p.folder_url,'Folder'),hyperlink(`#'Specifications'!D${detailStart[p.product_id]}`,'Six specifications'),p.context_status,hyperlink(p.context_image_url,'Context image'),p.source_scopes.join('\n'),6]);
const productSheet=add('Products','Individual sculpture products','One record per reviewed design, finish, size and build. Estimates and source conflicts are retained. Source candidates are excluded from this product count.',
 ['Product ID','Individual sculpture','Dimensions / depth','Weight','Material / finish','Fixing','Individual price','Availability','Orientation options','Image','Folder','Specifications','Context status','Context reference','Source scopes','Fields recorded'],
 productRows,[25,56,59,55,59,65,66,59,24,19,19,23,42,20,52,16]);
add('Specifications','Working specification detail','Accepted working descriptions with their original qualifications and basis. Actual measurements, stock and installed hardware remain separate facts.',
 ['Product ID','Individual sculpture','Specification','Working detail','Recorded state','Evidence and qualifications','Source scopes','Proposal IDs'],
 detailRows,[25,56,25,99,74,118,56,64]);

const groupMapping=data.references.flatMap(ref=>ref.source_reference_ids.filter(k=>!k.includes('|')).map(k=>({source_scope:k,source_title:ref.name,disposition:ref.reference_id!=='REF-'+k?'ARRANGEMENT_REFERENCE_ALIAS':'ARRANGEMENT_REFERENCE',targets:[ref.reference_id],reason:ref.notes,image_url:ref.image_url,folder_url:ref.folder_url,source_locator:'Review97 Group References; owner group-photo policy'})));
const reconciliationRows=[...data.scope_reconciliation,...data.historical_alias_reconciliation,...groupMapping].map(m=>[
 m.source_scope,m.source_title,m.source_scope.includes('|')?'Component / finish / build scope':'Arrangement / collection source',readable(m.disposition),m.targets.join('\n'),m.reason,hyperlink(m.image_url,'Image'),hyperlink(m.folder_url,'Folder'),m.source_locator??'Review97 source record']);
add('Reconciliation','Source record reconciliation','Every current review scope and historical alias keeps its source identity. Only accepted individual scopes and the documented Leaf Form orientation option supply product specifications.',
 ['Source key','Earlier or source name','Source type','Disposition','Canonical targets','Reason','Image','Folder','Evidence locator'],
 reconciliationRows,[57,58,31,42,49,105,19,19,92]);

const offerRows=data.source_offer_coverage.map(o=>[
 'Platform offer',o.offer_ref,o.source_title,o.related_product_ids?.join('\n')??'',coverageLabel(o.canonical_graph_coverage_state),(o.component_ids??[]).join('\n'),(o.flags??[]).map(readable).join('\n'),hyperlink(o.source_url,'Source page'),o.scope_note??o.source_cautions??'',o.exact_supported_target_ids?.length?'Existing source-to-scope crosswalk; specimen match unverified':'Exact source scope unresolved']);
const configRows=data.source_configuration_coverage.map(c=>[
 'Media configuration',c.configuration_id,c.source_component_name+' — '+c.baseline_finish_appearance,c.related_product_ids?.join('\n')??'',coverageLabel(c.canonical_graph_coverage_state),c.source_component_id,(c.flags??[]).map(readable).join('\n'),'',(c.notes??[]).join('\n'),c.exact_supported_target_ids?.length?'Existing source-to-scope crosswalk; specimen match unverified':'Exact source scope unresolved']);
add('Source coverage','Platform and media coverage','Source: the preserved 16 October platform/component register, reconciled against review97 and its owner-confirmed aliases. An association is not an exact current offer or finish match.',
 ['Record type','Source ID','Source description','Related product IDs','Coverage state','Source components','Flags','Source','Scope and source qualifications','Exact variant match'],
 [...offerRows,...configRows],[29,30,73,50,65,38,70,21,115,30]);

const referenceRows=data.references.map(r=>[r.reference_id,r.name,r.name_status,r.component_identification,r.sale_unit_status,r.notes,hyperlink(r.image_url,'Reference image'),hyperlink(r.folder_url,'Folder'),r.source_reference_ids.join('\n'),r.name_display_correction??'']);
add('References','Arrangements and collection references','Group photographs retain context without creating additional individual products. Two identical-picture Fingerprint names share one reference; both original sources are retained.',
 ['Reference ID','Reference name','Name status','Component scope','Sale unit','Notes','Image','Folder','Original reference IDs','Display correction'],
 referenceRows,[60,62,52,69,71,115,23,19,65,98]);

const attentionRows=data.source_candidates.map(c=>[
 c.candidate_id,c.name,c.record_type==='OPTION_FAMILY_CANDIDATE'?'Options family':'Individual design candidate',c.required_information,c.source_scopes.join('\n'),hyperlink(c.image_url,'Source reference'),hyperlink(c.folder_url,'Folder'),'Excluded from working product count']);
for(const c of data.additional_source_candidates??[])attentionRows.push([
 c.candidate_id,c.name,'Finish reference',c.required_information,(c.source_configuration_ids??[]).join('\n'),hyperlink(c.image_url,'Source reference'),hyperlink(c.folder_url,'Folder'),'Unresolved source appearance; no product created']);
add('Needs information','Source candidates requiring information','These sources are accounted for but do not yet establish additional, individually sellable product records. Existing owner-deferred group identification remains deferred.',
 ['Candidate ID','Source design or appearance','Candidate type','Information needed','Source scopes / configurations','Source reference','Folder','Catalogue treatment'],
 attentionRows,[37,65,42,116,69,24,19,63]);

productSheet.getRange('A4').values=[['Working products']];
productSheet.getRange('B4').formulas=[[`=COUNTA(A7:A${views.Products.last})`]];
productSheet.getRange('C4').values=[['Accepted review scopes']];
productSheet.getRange('D4').formulas=[[`=COUNTIF(Reconciliation!$D$7:$D$${views.Reconciliation.last},"Individual product")+COUNTIF(Reconciliation!$D$7:$D$${views.Reconciliation.last},"Orientation option")`]];
productSheet.getRange('E4').values=[['Products with six fields']];
productSheet.getRange('F4').formulas=[[`=COUNTIF(P7:P${views.Products.last},6)`]];
productSheet.getRange('G4').values=[['Source reviews needing information']];
productSheet.getRange('H4').formulas=[[`=COUNTA('Needs information'!A7:A${views['Needs information'].last})`]];
for(const address of ['B4','D4','F4','H4']){productSheet.getRange(address).format.font={name:'Arial',size:12,bold:true,color:green};productSheet.getRange(address).setNumberFormat('#,##0');}
productSheet.getRange(`P7:P${views.Products.last}`).formulas=productRows.map((_,i)=>[`=COUNTA(C${i+7}:H${i+7})`]);
productSheet.getRange(`P7:P${views.Products.last}`).setNumberFormat('0');
productSheet.getRange(`P7:P${views.Products.last}`).conditionalFormats.add('cellIs',{operator:'notEqual',formula:6,format:{fill:amber,font:{color:'#9C440D',bold:true}}});
wb.recalculate();

await fs.writeFile(path.join(here,'workbook-inspection.ndjson'),(await wb.inspect({kind:'region',sheetId:'Products',range:'A4:H4',maxChars:3000,tableMaxRows:1,tableMaxCols:8})).ndjson);
const errorCheck=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:50},summary:'Formula error scan'});
await fs.writeFile(path.join(here,'formula-error-scan.ndjson'),errorCheck.ndjson);

const leafIndex=data.products.findIndex(p=>p.orientation_options.length>0)+7;
const longestIndex=data.products.map((p,i)=>({i:i+7,size:Math.max(...fields.map(f=>p.specifications[f].display.length))})).sort((a,b)=>b.size-a.size)[0].i;
const longestBasisIndex=detailRows.map((r,i)=>({i:i+7,size:r[5].length})).sort((a,b)=>b.size-a.size)[0].i;
const renderPlan=[
 ['Products','A2:D9'],['Products','E6:H9'],['Products','I6:P10'],
 ['Products',`A${leafIndex}:D${leafIndex}`],['Products',`E${leafIndex}:H${leafIndex}`],
 ['Products',`C${longestIndex}:H${longestIndex}`],['Products',`A${views.Products.last-2}:H${views.Products.last}`],
 ['Specifications','A6:D8'],['Specifications','E6:H8'],['Specifications',`C${longestBasisIndex}:F${longestBasisIndex}`],
 ['Reconciliation','A6:D10'],['Reconciliation','E6:I9'],
 ['Source coverage','A6:E9'],['Source coverage','F6:J9'],
 ['References','A6:E8'],['References','F6:J8'],
 ['Needs information','A6:D9'],['Needs information','E6:H9']
];
const previewManifest=[];
for(let i=0;i<renderPlan.length;i++){
 const [sheetName,range]=renderPlan[i];
 const blob=await wb.render({sheetName,range,scale:1,format:'png'});
 const dest=path.join(here,'previews',`${String(i+1).padStart(2,'0')}-${sheetName.replaceAll(' ','_')}.png`);
 await fs.writeFile(dest,new Uint8Array(await blob.arrayBuffer()));
 previewManifest.push({sheet:sheetName,range,path:dest});
}
const book=await SpreadsheetFile.exportXlsx(wb);await book.save(output);
await fs.writeFile(path.join(here,'expected-workbook.json'),JSON.stringify(expected));
await fs.writeFile(path.join(here,'native-hyperlinks.json'),JSON.stringify(links,null,2));
await fs.writeFile(path.join(here,'preview-manifest.json'),JSON.stringify(previewManifest,null,2));
const receipt={status:'EXPORTED_PENDING_NATIVE_LINKS_AND_INDEPENDENT_READBACK',output,canonical_source_sha256:crypto.createHash('sha256').update(await fs.readFile(source)).digest('hex'),output_sha256:crypto.createHash('sha256').update(await fs.readFile(output)).digest('hex'),sheet_counts:Object.fromEntries(Object.entries(expected).map(([name,view])=>[name,view.rows.length])),native_hyperlinks_planned:links.length,previews:previewManifest.length};
await fs.writeFile(path.join(here,'export-receipt.json'),JSON.stringify(receipt,null,2));
console.log(JSON.stringify(receipt));
