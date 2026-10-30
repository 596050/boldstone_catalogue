import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {FileBlob,Workbook,SpreadsheetFile} from '@oai/artifact-tool';

const root=path.dirname(path.dirname(fileURLToPath(import.meta.url)));
if(process.argv.includes('--inspect-one-leaf-before')){
 const previous=JSON.parse(await fs.readFile(path.join(root,'evidence/pre-acanthus-one-leaf-left-2026-10-17/component_workbook_manifest.json'),'utf8'));
 const saved=await SpreadsheetFile.importXlsx(await FileBlob.load(previous.output));
 const dest=path.join(root,'reviews/one-leaf-left-before');await fs.mkdir(dest,{recursive:true});
 const rows=previous.sheets['Proposed Specifications'];const first=rows.first+rows.values.findIndex(r=>r[0]==='BC-AC-ONE');
 for(const [name,range]of [['Individual Sculptures','A12:I12'],['Proposed Specifications',`A${first}:H${first+2}`]]){
  const blob=await saved.render({sheetName:name,range,scale:1,format:'png'});
  await fs.writeFile(path.join(dest,name.replace(/[^A-Za-z]/g,'_')+'.png'),new Uint8Array(await blob.arrayBuffer()));
 }
 console.log('Existing One Leaf name and proposal layout rendered.');process.exit(0);
}
if(process.argv.includes('--inspect-panel-headers')){
 const manifest=JSON.parse(await fs.readFile(path.join(root,'evidence/component_workbook_manifest.json'),'utf8'));
 const saved=await SpreadsheetFile.importXlsx(await FileBlob.load(manifest.output));
 const dest=path.join(root,'reviews/workbook-ammonite-panel-specifications-2026-10-17');
 for(const [i,range]of ['V6:AA6','AB6:AG6'].entries()){
  const blob=await saved.render({sheetName:'Component BOM',range,scale:1,format:'png'});
  await fs.writeFile(path.join(dest,'Panel_Headers_'+(i+1)+'.png'),new Uint8Array(await blob.arrayBuffer()));
 }
 console.log('Saved panel column headers rendered.');process.exit(0);
}
if(process.argv.includes('--inspect-ammonite-before')){
 const previous=JSON.parse(await fs.readFile(path.join(root,'evidence/pre-ammonite-refresh-2026-10-17/component_workbook_manifest.json'),'utf8'));
 const before=await SpreadsheetFile.importXlsx(await FileBlob.load(previous.output));
 const dest=path.join(root,'reviews/ammonite-before');await fs.mkdir(dest,{recursive:true});
 for(const [sheetName,range] of [['Individual Sculptures','A13:F16'],['Component BOM','A37:F40']]){
  const rendered=await before.render({sheetName,range,scale:1,format:'png'});
  await fs.writeFile(path.join(dest,sheetName.replace(/[^A-Za-z]/g,'_')+'.png'),new Uint8Array(await rendered.arrayBuffer()));
 }
 console.log((await before.inspect({kind:'table',range:'Individual Sculptures!A14:F15',include:'values,formulas',tableMaxRows:2,tableMaxCols:6,maxChars:1500})).ndjson);process.exit(0);
}
const data=JSON.parse(await fs.readFile(path.join(root,'evidence/component_register.json'),'utf8'));
const refresh=Boolean(data.updated_utc),date=data.updated_utc?.slice(0,10)??'2026-10-16',amRefresh=Boolean(data.size_variants?.length),slug=data.refresh_slug??'bone-spiral-refresh-'+date;
const out=path.join(root,'outputs',...(refresh?[slug]:[])),previews=path.join(root,'reviews',amRefresh?'workbook-'+slug:(refresh?'workbook-'+date:'workbook'));
await fs.mkdir(out,{recursive:true});await fs.mkdir(previews,{recursive:true});
const wb=Workbook.create(),manifest={sheets:{},counts:data.counts,source_sha256:data.source_sha256};
const colors={ink:'#27392F',green:'#344E40',muted:'#66746C',amber:'#FFF0CE'};
const col=n=>{let s='';for(n++;n;n=Math.floor((n-1)/26))s=String.fromCharCode(65+(n-1)%26)+s;return s;};
const safe=v=>typeof v==='string'&&v.startsWith('=')?"'"+v:v??'';
const list=v=>Array.isArray(v)?v.join('\n'):v??'';
const tables={};
function table(name,title,note,columns,records,{header=6,output=false,review=false}={}){
 const sh=wb.worksheets.add(name),rows=records.map(r=>columns.map(c=>{let v=typeof c.get==='function'?c.get(r):list(r[c.key]);if(c.key==='example_file_ids'&&typeof v==='string')v=v.split('\n').slice(0,6).join('\n');return safe(v);}));
 const last=header+rows.length,end=col(columns.length-1);sh.showGridLines=false;
 sh.getRangeByIndexes(0,0,last,columns.length).format.font={name:'Arial',size:10,color:colors.ink};
 sh.getRangeByIndexes(0,0,last,columns.length).format.verticalAlignment='center';
 sh.getRange('A2').values=[[title]];sh.getRange('A2').format.font={name:'Arial',size:15,bold:true,color:colors.ink};
 sh.getRange('A3').values=[[note]];sh.getRange('A3').format.font={name:'Arial',size:10,italic:true,color:colors.muted};
 sh.getRangeByIndexes(header-1,0,1,columns.length).values=[columns.map(c=>c.label)];
 if(rows.length)sh.getRangeByIndexes(header,0,rows.length,columns.length).values=rows;
 const tbl=sh.tables.add(`A${header}:${end}${last}`,true,'T_'+name.replace(/[^a-zA-Z]/g,''));tbl.style='TableStyleLight1';tbl.showFilterButton=true;
 sh.getRangeByIndexes(header-1,0,1,columns.length).format={fill:colors.green,font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},wrapText:true,horizontalAlignment:'center',verticalAlignment:'center',rowHeight:44};
 sh.getRangeByIndexes(header,0,Math.max(1,rows.length),columns.length).format.rowHeight=31;
 columns.forEach((c,i)=>{
  sh.getRangeByIndexes(0,i,last,1).format.columnWidth=c.width??35;
  if(rows.length){sh.getRangeByIndexes(header,i,rows.length,1).format.wrapText=true;if(c.number)sh.getRangeByIndexes(header,i,rows.length,1).setNumberFormat('#,##0');}
 });
 for(let n=0;n<rows.length;n++){
  const lines=Math.max(1,...rows[n].map((v,i)=>String(v??'').split('\n').reduce((a,s)=>a+Math.max(1,Math.ceil(s.length/Math.max(12,(columns[i].width??35)*.95))),0)));
  if(lines>1)sh.getRangeByIndexes(header+n,0,1,columns.length).format.rowHeight=Math.min(409,Math.max(31,lines*13+9));
 }
 sh.freezePanes.freezeRows(header);sh.freezePanes.freezeColumns(Math.min(2,columns.length));if(output)sh.tabColor=colors.green;
 if(review&&rows.length){const rng=sh.getRangeByIndexes(header,columns.length-1,rows.length,1);rng.format.fill='#FFF6DB';}
 tables[name]={sh,first:header+1,last,count:rows.length,columns,rows};
 manifest.sheets[name]={first:header+1,count:rows.length,headers:columns.map(c=>c.label),values:rows};return sh;
}
const C=(key,label,width=35,number=false)=>({key,label,width,number});
const summary=wb.worksheets.add('Summary');summary.showGridLines=false;summary.tabColor=colors.green;
summary.getRange('A1:D110').format.font={name:'Arial',size:10,color:colors.ink};
summary.getRange('A1:D110').format.verticalAlignment='center';
for(const [c,w]of[['A',59],['B',15],['C',90],['D',15]])summary.getRange(`${c}1:${c}110`).format.columnWidth=w;
summary.getRange('A2').values=[['Boldstone · Individual Sculpture Register']];summary.getRange('A2').format.font={name:'Arial',size:15,bold:true,color:colors.ink};
summary.getRange('A3').values=[[data.review_caption??(amRefresh?'Bone Spiral and Ammonite updated: 17 October 2026. Baseline platform evidence: 16 October 2026.':(refresh?'Bone Spiral update: 17 October 2026. Baseline inventory and platform evidence: 16 October 2026.':'16 October 2026 · Source claims, component proposals and unresolved work kept separate'))]];summary.getRange('A3').format.font={name:'Arial',size:10,italic:true,color:colors.muted};
summary.getRange('A5:C5').values=[['Catalogue checkpoint','Count','Meaning']];summary.getRange('A5:C5').format={fill:colors.green,font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},rowHeight:29};

const components=data.components;
table('Individual Sculptures','Individual sculpture components','Working catalogue records, not a physical stock count. Local IDs stay stable; exact manufacture and source versions need confirmation.',[
 C('component_id','Component ID',23),C('name','Individual sculpture / component',61),C('family','Family',30),C('identity_status','Identity evidence',57),C('listing_action','Listing action',73),C('dimensions_available','Available component dimensions',95),C('weight_available','Available component weight',75),C('material_available','Available material claims',115),C('fixing_available','Available fixing instructions',115),C('standalone_offer_refs','Mapped standalone offer(s)',25),C('offer_refs','All source offer references',25),C('historic_individual_price','Dated individual price reference',90),C('missing_specification_fields','Specification gaps / conflicts',120),C('source_codes','Maker source code(s)',45),C('folder_ids','Stable Dropbox folder IDs',47),C('example_file_ids','Stable example file IDs',47),C('notes','Identity / version notes',115),{label:'Included in working count',width:24,get:r=>r.identity_status.startsWith('Source-only')||r.identity_status.startsWith('Concept')?0:1},{label:'Needs standalone offer',width:24,get:r=>!(r.identity_status.startsWith('Source-only')||r.identity_status.startsWith('Concept'))&&!r.standalone_offer_refs.length?1:0},C('current_individual_prices','Current public individual offer prices',80)
],components,{output:true});
const actions=components.filter(c=>!c.identity_status.startsWith('Source-only')&&!c.identity_status.startsWith('Concept')&&!c.standalone_offer_refs.length);
table('Listing Actions','Components without a mapped standalone offer','Review component proposals before creating sale records. Set prices and stock are not divided among the components.',[
 C('component_id','Component ID',23),C('name','Individual sculpture',61),C('family','Family',30),C('identity_status','Identity evidence',57),C('listing_action','Next listing action',75),C('offer_refs','Existing set / gallery offers',30),C('dimensions_available','Component dimensions available',95),C('weight_available','Component weight evidence',75),C('historic_individual_price','2025 white-standard price only',90),C('missing_specification_fields','Needed before complete listing',115),C('folder_ids','Stable Dropbox folder IDs',47),C('example_file_ids','Stable example file IDs',47),C('review','Maker confirmation / correction',85)
],actions,{output:true,review:true});
const config=data.configurations.filter(c=>!['BC-WALL-CIRCLE','BC-FFL-1'].includes(c.component_id));
table('Photograph Gaps','Component photographs to complete','Filtered work list by component and depicted finish. “Not identified” is a review finding, not proof that a photograph never existed.',[
 C('configuration_id','Component / finish reference',25),C('component_id','Component ID',23),C('component_name','Individual sculpture',61),C('finish_appearance','Depicted finish',38),C('individual_front','Individual front image',44),C('in_situ','In situ / context picture',45),C('series','Series / arrangement picture',54),C('scene_provenance','Scene provenance',80),C('photo_scope','Evidence scope',105),C('all_folder_ids','Stable Dropbox folder IDs',47),C('example_file_ids','Stable example file IDs',47),C('review','Image located / photo to create',85)
],config.filter(c=>c.individual_front!=='Identified'||c.in_situ==='No context image identified'||c.series==='No arrangement image identified'),{output:true,review:true});
table('Component BOM','Product and arrangement component positions','Every position remains explicit. Repeated moulds share a component ID; native set dimensions, prices and weights retain set scope.',[
 C('bom_id','BOM position ID',25),C('component_id','Component ID',23),C('component_name','Individual sculpture',61),C('offer_ref','Source offer',19),C('position','Position',15,true),C('quantity','Quantity at position',20,true),C('sku','Shared / native SKU',29),C('sq_id','Squarespace product ID',38),C('sh_handle','Shopify handle',53),C('scope','Sale-unit / proposal scope',80),C('component_dimensions_source_cm','Component dimension claim (cm)',58),C('dimensions_state','Dimensional scope',80),C('set_overall_cm','Whole-set dimension claim (cm)',42),C('set_weight_kg','Whole-set export weight (kg)',30),C('set_price','Whole-set native price',27),C('component_price','Individual price status',67),C('component_weight','Individual weight status',57),C('folder_ids','Stable component folder IDs',47),C('example_file_ids','Stable component example file IDs',47),C('mapping_state','Image correspondence',70),C('cautions','Composition / identity cautions',125),...(amRefresh?[C('variant_id','Component size variant ID',26),C('variant_name','Individual panel size variant',60),C('maker_panel_code','Maker panel code',25),C('panel_dimensions','Panel dimensions and source conflicts',100),C('panel_material','Panel material and finish sources',100),C('panel_fixing','Panel fixing evidence',115),C('panel_suitability','Panel suitability source',85),C('panel_lead_time','Panel production lead time',65),C('panel_care_packaging','Panel care and packed specifications',85),C('panel_photos','Panel photographs available',100),C('panel_gaps','Panel specification gaps',115),C('panel_sources','Panel specification source locators',125)]:[])
],data.bom,{output:true});
table('Platform Mapping','Squarespace and Shopify mapped to component records','80 Squarespace products and the unmatched Shopify draft. Historical exports and current public pages are distinguished.',[
 C('offer_ref','Offer reference',20),C('title','Native product title',75),C('platform','Platform correspondence',36),C('sku','SKU',29),C('sq_id','Squarespace product ID',38),C('sh_handle','Shopify handle',53),C('match_status','Cross-platform match status',75),C('native_parts','Source component count',24),C('proposed_bom_pieces','BOM positions in this register',26,true),C('sale_unit_state','Sale-unit state',70),C('image_state','Photograph / design correspondence',80),C('image_folder_id','Stable photographed folder ID',47),C('image_file_id','Stable photograph file ID',47),C('image_path','Current photograph path',160),C('source_each_cm','Source each-component dimensions (cm)',51),C('source_overall_cm','Source whole dimensions (cm)',48),C('source_set_weight_kg','Source whole weight (kg)',30),C('native_price','Native export price',26),C('native_currency','Price currency scope',48),C('page_status','Current public page status',43),C('source_url','Source URL',125),C('cautions','Scope and conflicts',125),C('native_description','Complete native description as text',175),C('raw_weight','Native Squarespace weight (unit unencoded)',34),C('raw_length','Native length (unit unencoded)',30),C('raw_width','Native width (unit unencoded)',30),C('raw_height','Native height (unit unencoded)',30),C('public_price','Current public whole-offer price',31),C('public_currency','Public price currency',26),C('public_low_price','Public price low',26),C('public_high_price','Public price high',26),C('public_sku','Current public offer SKU',32),C('public_sku_comparison','Current page SKU comparison',70),C('public_availability','Public availability claim',37)
],data.platform_records,{output:true});
table('Proposed Specifications','Image and related-source inferences','Proposals remain separate from sourced specifications. Unscaled images do not establish chemistry, physical mass or individual selling price.',[
 C('component_id','Component ID',23),C('component_name','Individual sculpture',61),C('field','Field / question',48),C('proposal','Proposed interpretation or estimate',145),C('basis','Image / related specification basis',135),C('confidence','Confidence and limits',85),C('status','Evidence state',49),C('needed','Confirmation needed',115),C('folder_ids','Stable Dropbox folder IDs',47),C('example_file_ids','Stable image reference IDs',47)
],data.inferences,{output:true});

const sources=[{label:'Original all-fields workbook',kind:'Local supplied source',id:'',path:'/Users/tprice/Documents/boldstone/Boldstone_Wall_Sculptures_Matched_All_Fields_2026-10-15.xlsx',hash:data.source_sha256,scope:'Original preserved exports and catalogue evidence; workbook not modified'},...(data.refresh_sources??[]),
 ...data.document_sources.map(s=>({label:s.label,kind:'Maker document / source reference',id:s.head?.id??'',path:s.head?.path??s.local_path,hash:s.head?.content_hash??s.fingerprint?.content_hash??'',scope:'Source bytes and document metadata retained; no Dropbox writes',local:s.local_path})),
 ...data.platform_records.filter(p=>p.sq_id).map(p=>({label:p.offer_ref+' '+p.title,kind:'Current public Squarespace page',id:p.sq_id,path:p.source_url,hash:p.page_sha256??'',scope:p.page_status,local:path.join(root,'evidence/public-pages',p.sq_id+'.html')}))];
table('Evidence >>','Evidence sources and interpretation','Inputs and audit detail follow. A source statement is not a physical measurement. Image references retain stable Dropbox IDs and content hashes.',[
 C('label','Source reference',75),C('kind','Source type',48),C('id','Stable source file / product ID',47),C('path','Source path / URL',165),C('hash','Source SHA256 / Dropbox content hash',75),C('scope','Scope / retrieval state',110),C('local','Preserved local source copy',165)
],sources);
table('Specification Evidence','All recorded specification claims','Original offer scope is retained, including entire-set weights and prices. Maker templates and current pages are separately labelled.',[
 C('claim_id','Claim ID',28),C('component_id','Component ID',23),C('field','Source field',55),C('value','Source value / statement',170),C('unit','Unit / interpretation',65),C('scope','Applicability and scope',145),C('status','Evidence state',75),C('source_ref','Source locator',140)
],data.claims);
table('Dropbox Groups','Every indexed Dropbox image group',amRefresh?'Baseline review: 16 October 2026. Bone Spiral (five folders) and Ammonite (eight folders) updated 17 October. Other families have not been refreshed.':(refresh?'Baseline groups reviewed 16 October 2026. Bone Spiral now has five folders, checked 17 October. Other families have not been refreshed.':'All 350 groups reviewed through representative images; earlier complete group findings are retained where available. Empty folders are explicit.'),[
 C('group_ref','Review reference',20),C('family','Family',31),C('name','Current group name',75),C('id','Stable folder ID',47),C('files','Files',16,true),C('role','Media role',43),C('component_ids','Component associations',42),C('assignment_status','Component mapping scope',100),C('finish_appearance','Depicted finish',43),C('path','Current Dropbox path',165),C('selected','Viewed representative file IDs',47),C('review_basis','Visual review coverage',115),C('earlier_observations','Earlier complete review observations',170),{label:'Maker/source resolution',width:170,get:r=>Object.entries(r.source_decision??{}).filter(([k])=>['product_identity','component_numbers','finish','scene_origin'].includes(k)).map(([k,v])=>k+': '+v.finding).join('\n')}
],data.groups);
const groupById=new Map(data.groups.map(g=>[g.id,g]));
table('Dropbox Files','Every indexed Dropbox file and stable identity',`${data.counts.files.toLocaleString('en-GB')} indexed files. ${amRefresh?'Bone Spiral and Ammonite updated 17 October 2026. ':(refresh?'Bone Spiral paths refreshed 17 October 2026. ':'')}Parent-group candidates do not identify every subject in every photograph.`,[
 C('id','Stable file ID',47),C('folder_id','Stable parent folder ID',47),C('family','Family',31),C('group','Current image group',75),C('name','Current file name',115),C('content_hash','Dropbox content hash',75),C('bytes','Bytes',19,true),{label:'Parent-group component candidates',width:50,get:r=>groupById.get(r.folder_id)?.component_ids.join('\n')??''},C('path','Current Dropbox file path',190)
],data.assets);
const unresolved=[...data.unresolved.map((r,i)=>({...r,work_id:'GROUP-'+r.group_ref,kind:'Group/component question',file_id:r.example_file_ids,identity:r.finding,needed:r.next_action})),...data.unresolved_positions.map(r=>({...r,work_id:r.position_id,kind:'Fingerprint media position',identity:r.identity,needed:r.needed,group_name:r.file_path,files:r.depicted_count,state:r.physical_count}))];
table('Unresolved Media','Component mapping that remains open','These work items prevent a final distinct-sculpture count. Media positions may repeat a design or be a generated study; they are not added as physical stock.',[
 C('work_id','Stable review work ID',58),C('kind','Work item type',39),C('group_ref','Group reference',20),C('folder_id','Stable folder ID',47),C('file_id','Stable file ID(s)',47),C('group_name','Group / file context',140),C('files','Files / depicted count',29),C('state','Current mapping state',85),C('identity','Observation / component question',160),C('source_finding','Maker/source finding',150),C('needed','Evidence needed',120)
],unresolved);
table('Moulds and Aliases','Repeated moulds and numbering crosswalks','A rotated component can fill another position in a series. It does not automatically require another individual sculpture product.',[
 C('component_id','Component ID',25),C('canonical','Maker / canonical code',42),C('alias','Alias / position code',48),C('relationship','Relationship',70),C('rotation','Orientation',40),C('source','Source locator',70)
],data.aliases);
table('Mixed Image Links','File-specific components in mixed photographs','These associations identify visible designs in selected mixed photographs. Background components and exact size/finish are not certified.',[
 C('component_id','Component ID',25),C('file_id','Stable file ID',47),C('folder_id','Stable folder ID',47),C('scope','Match scope',120),C('basis','Visual evidence',100),C('file_path','Current file path',190)
],data.mixed_bindings);

const t=tables['Individual Sculptures'];
const metrics=[
 ['Working component records',`=SUM('Individual Sculptures'!R${t.first}:R${t.last})`,'95 standard designs plus 28 visual/bespoke proposals; not physical stock.'],
 ['Standard design records',`=COUNTIFS('Individual Sculptures'!D${t.first}:D${t.last},"Documented or visually distinct design")`,'Design records supported by labelled sources or distinct reviewed forms.'],
 ['Visual / bespoke proposals',`=B6-B7`,'11 visual proposals plus 17 bespoke positions; identity or mould repetition remains open.'],
 ['Without a mapped standalone offer',`=SUM('Individual Sculptures'!S${t.first}:S${t.last})`,'Candidate listing work: confirm identity, specifications, individual price and availability.'],
 ['With a mapped standalone offer',`=B6-B9`,'Source offer correspondence only; not current stock or complete finish/size coverage.'],
 ['Squarespace–Shopify SKU pairs',37,'The supplied main exports have 37 unique exact-SKU pairs.'],
 ['Squarespace-only / Shopify-only', '43 / 1','The unmatched Shopify item is a blank-SKU Frozen Fish draft.'],
 ['Dropbox families / groups / files',`${data.counts.families} / ${data.counts.groups} / ${data.counts.files.toLocaleString('en-GB')}`,amRefresh?'Baseline: 16 October. Bone Spiral and Ammonite refreshed 17 October. Ammonite has four explicit panel/size variants.':(refresh?'Inventory from 16 October; Bone Spiral refreshed 17 October. Other families have not been refreshed.':'Complete fresh file/folder inventory; no Dropbox content changed.')],
 ['Component/finish groups without context',data.counts.component_finish_groups_without_context,data.counts.component_finish_groups_without_context+' image work groups, spanning '+new Set(config.filter(c=>c.in_situ==='No context image identified').map(c=>c.component_id)).size+' component records.'],
 ['Component/finish groups without series',data.counts.component_finish_groups_without_series,'An optional series picture is not treated as missing for a standalone design.'],
 ['Current public pages read / unavailable','78 / 2','The two unavailable pages returned 404; original export specifications are preserved.'],
 ['Source-only / concept families excluded','1 / 1','Frozen Fish Long is a source-only option; Wall Circle options are not counted as physical sculptures.'],
 ['Unresolved group / media work items',`${data.counts.unresolved_group_work_items} / ${data.counts.unresolved_media_position_records}`,'Fingerprint studies, crops and mixed scenes remain visible; final unique count is not settled.'],
 ['Physical specifications fully verified',0,'Source claims and proposed templates are recorded; current casts have not been physically measured.']
];
for(let i=0;i<metrics.length;i++){
 const row=i+6;summary.getRange(`A${row}:C${row}`).values=[[metrics[i][0],typeof metrics[i][1]==='string'&&metrics[i][1].startsWith('=')?null:metrics[i][1],metrics[i][2]]];
 if(typeof metrics[i][1]==='string'&&metrics[i][1].startsWith('='))summary.getRange(`B${row}`).formulas=[[metrics[i][1]]];
 summary.getRange(`A${row}:C${row}`).format.rowHeight=38;summary.getRange(`C${row}`).format.wrapText=true;
 summary.getRange(`B${row}`).format.font={name:'Arial',size:12,bold:true,color:colors.ink};summary.getRange(`B${row}`).format.horizontalAlignment='center';
}
summary.getRange('A22').values=[['What remains to finish']];summary.getRange('A22').format.font={name:'Arial',size:13,bold:true,color:colors.ink};
const todo=[['1. Resolve identity and repeated components','Review bespoke positions, Fingerprint studies, title/photo conflicts and mixed background works.'],['2. Complete individual specifications','Use labelled each-component dimensions and historic templates; resolve current size, material, depth and weight conflicts.'],['3. Complete pictures for each finish','Use Photograph Gaps; add individual fronts, context or series imagery where no suitable image was identified.'],['4. Prepare purchasable component offers','Use Listing Actions; assign standalone prices and sale/availability decisions, then link set BOMs to the same components.']];
for(let i=0;i<todo.length;i++){summary.getRange(`A${23+i}:C${23+i}`).values=[[todo[i][0],null,todo[i][1]]];summary.getRange(`A${23+i}:C${23+i}`).format.rowHeight=38;summary.getRange(`C${23+i}`).format.wrapText=true;}
summary.getRange('A29:C29').values=[['Family','Component records','Unresolved group work items']];summary.getRange('A29:C29').format={fill:colors.green,font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},rowHeight:30};
const families=[...new Set(data.groups.map(g=>g.family))].sort();
const familyRows=families.map(f=>[f,components.filter(c=>c.family===f&&!c.identity_status.startsWith('Source-only')&&!c.identity_status.startsWith('Concept')).length,data.unresolved.filter(u=>u.family===f).length]);
summary.getRange(`A30:C${29+familyRows.length}`).values=familyRows;summary.getRange(`A30:C${29+familyRows.length}`).format.rowHeight=25;
manifest.sheets.Summary={metrics:metrics.map((m,i)=>({row:i+6,label:m[0],expected:typeof m[1]==='string'&&m[1].startsWith('=')?([123,95,28,84,39][i]):m[1]})),familyRows};
// Bounded, reactive warning cues; no decorative PASS cells.
for(const name of ['Photograph Gaps','Unresolved Media']){
 const {sh,first,last}=tables[name];sh.getRange(`D${first}:I${last}`).conditionalFormats.add('containsText',{text:'No ',format:{fill:colors.amber,font:{color:'#775211'}}});
}
wb.recalculate();
console.log((await wb.inspect({kind:'table',range:'Summary!A5:C19',include:'values,formulas',tableMaxRows:15,tableMaxCols:3,maxChars:3300})).ndjson);
console.log((await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:20},summary:'Final formula error scan',maxChars:1000})).ndjson);
const refreshViews={'Summary':['A1:C26'],'Individual Sculptures':['A19:F22'],'Listing Actions':['A14:F17'],'Photograph Gaps':['A21:I25'],'Component BOM':['A65:F68'],'Platform Mapping':['A39:G41'],'Proposed Specifications':['A32:F35'],'Evidence >>':['A6:F9'],'Dropbox Groups':['A31:H34','A356:H359'],'Dropbox Files':[`A${data.assets.length+3}:E${data.assets.length+6}`]};
if(amRefresh){
 const amIds=new Set(['BC-AM-1','BC-AM-2']);
 const blocks=(name,index,end)=>{const t=tables[name],indices=t.rows.flatMap((r,i)=>amIds.has(r[index])?[t.first+i]:[]);const runs=[];for(const row of indices){const last=runs.at(-1);if(last&&last[1]===row-1)last[1]=row;else runs.push([row,row]);}return runs.map(([a,b])=>`A${a}:${end}${b}`);};
 refreshViews['Individual Sculptures']=blocks('Individual Sculptures',0,'G');refreshViews['Listing Actions']=blocks('Listing Actions',0,'H');
 refreshViews['Component BOM']=blocks('Component BOM',1,'I');
 for(const [i,r]of data.bom.entries())if(r.offer_ref==='O018'&&r.position===1){const n=tables['Component BOM'].first+i;refreshViews['Component BOM'].push(`P${n}:W${n+1}`);break;}
 for(const [i,r]of data.bom.entries())if(['O018','O048'].includes(r.offer_ref)&&r.position===1){const n=tables['Component BOM'].first+i;refreshViews['Component BOM'].push(`V${n}:AA${n+1}`,`AB${n}:AG${n+1}`);}
 refreshViews['Proposed Specifications']=blocks('Proposed Specifications',0,'F');refreshViews['Photograph Gaps']=['A12:I16'];
 refreshViews['Dropbox Groups']=['A25:H28','A360:H363'];refreshViews['Dropbox Files']=[`A${data.assets.length+3}:E${data.assets.length+6}`];
 refreshViews['Evidence >>']=['A6:F11'];refreshViews['Specification Evidence']=[`A${data.claims.length+3}:H${data.claims.length+6}`];
}
if(process.argv.includes('--panel-specifications-only')){
 for(const name of Object.keys(refreshViews))if(!['Individual Sculptures','Listing Actions','Component BOM','Proposed Specifications','Specification Evidence'].includes(name))delete refreshViews[name];
 refreshViews['Individual Sculptures']=['F14:I15'];
 refreshViews['Listing Actions']=['G10:H11'];
 refreshViews['Component BOM']=['P30:Q31','V30:X31','Y30:AA31','AB30:AD31','AE30:AG31','P86:Q87','V86:X87','Y86:AA87','AB86:AD87','AE86:AG87'];
 refreshViews['Proposed Specifications']=['C45:H48'];
}
if(process.argv.includes('--one-leaf-left-only')){
 for(const name of Object.keys(refreshViews))delete refreshViews[name];
 const ranges=(name,key,end)=>{const t=tables[name];return t.rows.flatMap((r,i)=>r[key]==='BC-AC-ONE'?[`A${t.first+i}:${end}${t.first+i}`]:[]);};
 refreshViews['Summary']=['A1:C5'];
 refreshViews['Individual Sculptures']=ranges('Individual Sculptures',0,'I');
 refreshViews['Listing Actions']=ranges('Listing Actions',0,'I');
 refreshViews['Photograph Gaps']=ranges('Photograph Gaps',1,'I');
 refreshViews['Proposed Specifications']=[`A${tables['Proposed Specifications'].last-6}:H${tables['Proposed Specifications'].last}`,...ranges('Proposed Specifications',0,'D').slice(0,1)];
 refreshViews['Evidence >>']=['A6:F12'];
}
for(const sh of ['Summary',...Object.keys(tables)]){
 if(refresh&&!refreshViews[sh])continue;
 const changed=new Set(['Summary','Individual Sculptures','Photograph Gaps','Platform Mapping','Proposed Specifications','Dropbox Groups','Evidence >>',...(amRefresh?Object.keys(refreshViews):[])]);
 if(!changed.has(sh)&&(await fs.stat(path.join(previews,sh.replace(/[^a-zA-Z]/g,'_')+'_1.png')).catch(()=>null)))continue;
 const ranges=refresh?refreshViews[sh]:(sh==='Summary'?['A1:C26','A29:C42']:[`A1:${col(Math.min(tables[sh].columns.length,6)-1)}${Math.min(tables[sh].last,tables[sh].first+3)}`]);
 for(let i=0;i<ranges.length;i++){const im=await wb.render({sheetName:sh,range:ranges[i],scale:1,format:'png'});await fs.writeFile(path.join(previews,sh.replace(/[^a-zA-Z]/g,'_')+'_'+(i+1)+'.png'),new Uint8Array(await im.arrayBuffer()));}
}
const output=path.join(out,`Boldstone_Individual_Sculptures_Component_Register_${date}.xlsx`);
await(await SpreadsheetFile.exportXlsx(wb)).save(output);manifest.output=output;
await fs.writeFile(path.join(root,'evidence/component_workbook_manifest.json'),JSON.stringify(manifest));
console.log(JSON.stringify({output,sheets:1+Object.keys(tables).length,components:components.length}));
