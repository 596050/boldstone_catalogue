import fs from 'node:fs/promises';
import path from 'node:path';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';
const out=path.dirname(new URL(import.meta.url).pathname);
const d=JSON.parse(await fs.readFile(out+'/readiness.json','utf8'));
const book=Workbook.create();
const products=[...d.products].sort((a,b)=>(a.family+' '+a.title).localeCompare(b.family+' '+b.title));
const cols=[['product_id','Product ID'],['sku','SKU'],['title','Product'],['native_action','Required action'],['existing_lot_id','Existing draft'],['retail_gbp','Catalogue retail GBP'],['catawiki_target_price_gbp','Catawiki proposed GBP'],['catawiki_target_price_eur','Estimate EUR'],['reserve_price_eur_proposed','Reserve proposal EUR'],['reserve_status','Reserve status'],['photo_candidate_count','Selected photo candidates'],['shortfall_to_five_candidates','Candidate shortfall to five'],['selected_non_in_situ_candidates','Non-in-situ candidates'],['known_below_2000px_long_edge','Below recommended 2000px long edge'],['original_dimensions_unknown','Original dimensions unknown'],['first_batch_candidate_rank','First batch candidate rank'],['shipping_profile','Quote group'],['packed_length_cm_estimate','Estimated packed length cm'],['packed_width_cm_estimate','Estimated packed width cm'],['packed_height_cm_estimate','Estimated packed height cm'],['packed_weight_kg_estimate','Estimated packed kg'],['shipping_quote_status','Quote status'],['planned_cast_label','Planned physical cast label'],['cast_reservation_state','Cast reservation state'],['signature','Signature'],['era','Production era'],['exact_year','Exact year (unknown stays blank)'],['actual_cast_photographs','Actual sale-cast photos'],['existing_edit_url','Draft edit URL'],['website','Website URL']];
function sheetTable(name,headers,rows){
 const s=book.worksheets.add(name);s.showGridLines=false;
 s.getRangeByIndexes(0,0,rows.length+1,headers.length).values=[headers,...rows];
 const range=s.getRangeByIndexes(0,0,rows.length+1,headers.length);
 range.format.font={name:'Arial',size:10};range.format.rowHeight=40;range.format.columnWidth=24;range.format.wrapText=true;
 s.getRangeByIndexes(0,0,1,headers.length).format={fill:'#34473A',font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},rowHeight:55,wrapText:true};
 s.freezePanes.freezeRows(1);return s;
}
const s=sheetTable('All 176 products',cols.map(c=>c[1]),products.map(p=>cols.map(c=>p[c[0]]??'')));
s.getRange('C1:C177').format.columnWidth=48;s.getRange('D1:D177').format.columnWidth=28;
s.getRange('F2:G177').setNumberFormat('"£"#,##0.00');s.getRange('H2:I177').setNumberFormat('"€"#,##0');
s.getRange('J1:J177').format.columnWidth=45;s.getRange('V1:AB177').format.columnWidth=50;
sheetTable('Shipping quote groups',['Profile','Products','Maximum length cm estimate','Maximum width cm estimate','Maximum height cm estimate','Maximum weight kg estimate','Maximum proposed value GBP','Service assessment','Status','Estimate warning'],d.profiles.map(p=>[p.profile,p.product_count,p.max_length_cm_estimate,p.max_width_cm_estimate,p.max_height_cm_estimate,p.max_weight_kg_estimate,p.max_declared_value_gbp_proposed,p.type,p.quote_status,p.basis]));
const qe=JSON.parse(await fs.readFile(out+'/shipping-quote-evidence.json','utf8'));
sheetTable('Quote evidence',['Provider','Verified status','Amount EUR incl tax','Route / scope','Decision / remaining confirmation','Evidence'],qe.quotes.map(q=>[q.provider,q.status,q.displayed_total_eur_including_taxes??'',q.destination??q.scope,q.decision??'Specialist profile prices and fragile gypsum damage cover pending. No booking.',(q.evidence??[]).join('; ')]));
book.worksheets.getItem('Quote evidence').getRange('B1:F3').format.columnWidth=65;
book.worksheets.getItem('Quote evidence').getRange('A2:F3').format.rowHeight=110;
const photos=products.flatMap(p=>p.photos.map(i=>[p.product_id,p.sku,p.title,i.name,i.listing?'Listing':'',i.in_situ?'In situ':'',i.primary?'Primary':'',i.width_px??'',i.height_px??'',i.dropbox_url,i.url,i.ai_status]));
sheetTable('Selected image links',['Product ID','SKU','Product','Image','Listing','In situ','Primary','Width px','Height px','Dropbox original URL','Current public image URL','Actual image review'],photos);
sheetTable('Policy and sources',['Topic','Instruction / evidence'],Object.entries(d.policy).filter(([k])=>k!=='no_reserve_original_product_ids').map(([k,v])=>[k,typeof v==='string'?v:JSON.stringify(v)]).concat([
 ['Original no-reserve product IDs',d.policy.no_reserve_original_product_ids.join(';')],
 ['Source catalogue',JSON.parse(await fs.readFile(out+'/source-pointer-before.json','utf8')).current_app_review_workbook.path],
 ['Source SHA256',d.source_sha256],['Prepared UTC',d.created_utc],
 ['Direct from the Artist guidelines','https://www.catawiki.com/en/help/specific-guidelines-art/direct-from-the-artist-submission-guidelines'],
 ['Attribution guidance','https://www.catawiki.com/en/help/specific-guidelines-art/post-war-contemporary-art-prints-submission-guidelines'],
 ['AI policy','https://www.catawiki.com/en/help/seller-terms/ai-image-policy'],
 ['Bulk submissions','https://www.catawiki.com/en/help/submitting-lots/how-to-submit-multiple-bulk-objects-at-once'],
 ['PACK & SEND RFQ','https://www.packsend.co.uk/get-a-quote/'],
 ['PACK & SEND damage cover','https://www.packsend.co.uk/security-cover/warranty-protection/']
]));
book.worksheets.getItem('Policy and sources').getRange('B1:B30').format.columnWidth=130;
book.worksheets.getItem('Policy and sources').getRange('A1:B25').format.rowHeight=88;
book.recalculate();
await (await SpreadsheetFile.exportXlsx(book)).save(out+'/catawiki_all_176_readiness.xlsx');
const quote=v=>'"'+String(v??'').replaceAll('"','""')+'"';
const data=s.getRangeByIndexes(0,0,177,cols.length).values;
await fs.writeFile(out+'/all-176-products.csv',data.map(r=>r.map(quote).join(',')).join('\r\n')+'\r\n');
const rfqCols=['product_id','sku','title','shipping_profile','packed_length_cm_estimate','packed_width_cm_estimate','packed_height_cm_estimate','packed_weight_kg_estimate','catawiki_target_price_gbp'];
await fs.writeFile(out+'/supplier-rfq-products.csv',[rfqCols,...products.map(p=>rfqCols.map(k=>p[k]))].map(r=>r.map(quote).join(',')).join('\r\n')+'\r\n');
const image=await book.render({sheetName:'All 176 products',range:'A1:J7',scale:1.1,format:'png'});
await fs.writeFile(out+'/report-preview.png',new Uint8Array(await image.arrayBuffer()));
const qimage=await book.render({sheetName:'Shipping quote groups',range:'A1:G7',scale:1.2,format:'png'});
await fs.writeFile(out+'/profiles-preview.png',new Uint8Array(await qimage.arrayBuffer()));
console.log(JSON.stringify({status:'AUTHORED',products:products.length,selected_photo_rows:photos.length,shipping_profiles:d.profiles.length}));
