import fs from 'node:fs/promises';
import path from 'node:path';
import { Workbook, SpreadsheetFile, FileBlob } from '@oai/artifact-tool';

const work = path.dirname(new URL(import.meta.url).pathname);
const output = '/Users/tprice/Documents/boldstone/sculpture-catalogue/outputs/01a13fe6-495b-7253-b923-31823b4cbca8/matched-listing-2026-10-25';
const data = JSON.parse(await fs.readFile(path.join(output, 'listing-data.json'), 'utf8'));
const audit = JSON.parse(await fs.readFile(path.join(work, 'all-source-association-audit.json'), 'utf8'));
const baseline = JSON.parse(await fs.readFile('/Users/tprice/Documents/boldstone/sculpture-catalogue/components/reconciliation/coral-depth-wording-master-2026-10-25/canonical-master-register.json', 'utf8'));
const byOffer = Object.fromEntries(baseline.source_offer_edges.map(e => [e.offer_ref, e.source_offer]));
const wb = Workbook.create();
const products = wb.worksheets.add('Products');
const matches = wb.worksheets.add('Listing matches');
const changes = wb.worksheets.add('Changes');
const sources = wb.worksheets.add('Source associations');
const sheets = [products, matches, changes, sources];
const friendly = s => s.replaceAll('_', ' ').toLowerCase().replace(/^./, c => c.toUpperCase());
const clean = s => String(s ?? '').replaceAll('**', '').replace(/\s+/g, ' ').trim();
const col = n => { let s=''; for(let v=n+1;v;v=Math.floor((v-1)/26))s=String.fromCharCode(65+(v-1)%26)+s; return s; };
const expected = {};

function setup(sheet, title, context, headers, rows, widths, linkColumns = {}) {
  sheet.showGridLines = false;
  const lastRow = rows.length + 7;
  const lastCol = col(headers.length - 1);
  sheet.getRange(`A1:${lastCol}${lastRow}`).format.font = { name:'Arial',size:10,color:'#25332D' };
  sheet.getRange('B2').values = [[title]];
  sheet.getRange('B2').format.font = { name:'Arial',size:16,bold:true,color:'#263B32' };
  sheet.getRange('B3').values = [[context]];
  sheet.getRange('B3').format.font = { italic:true,size:10,color:'#626B64' };
  sheet.getRange(`A6:${lastCol}6`).format.borders = {bottom:{style:'thin',color:'#A6B5AC'}};
  sheet.getRange(`A7:${lastCol}7`).values = [headers];
  sheet.getRange(`A8:${lastCol}${lastRow}`).values = rows;
  sheet.getRange(`A7:${lastCol}7`).format = {
    fill:'#30483D',font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},
    wrapText:true,horizontalAlignment:'center',verticalAlignment:'center',rowHeight:34
  };
  sheet.getRange(`A8:${lastCol}${lastRow}`).format.wrapText = true;
  sheet.getRange(`A8:${lastCol}${lastRow}`).format.verticalAlignment = 'top';
  for(let i=0;i<widths.length;i++) sheet.getRange(`${col(i)}1:${col(i)}${lastRow}`).format.columnWidth = widths[i];
  for(let i=0;i<rows.length;i++) {
    let maxLines = 1;
    for(let j=0;j<rows[i].length;j++) {
      const value = linkColumns[j] ? 'Open reference' : clean(rows[i][j]);
      maxLines = Math.max(maxLines, Math.ceil(value.length / Math.max(10, widths[j] * 1.15)));
    }
    sheet.getRange(`A${i+8}:${lastCol}${i+8}`).format.rowHeight = Math.max(34, maxLines * 13 + 12);
    if(i%2) sheet.getRange(`A${i+8}:${lastCol}${i+8}`).format.fill = '#F3F5F1';
  }
  for(const [index, label] of Object.entries(linkColumns)) {
    const c = col(Number(index));
    // Artifact Tool's HYPERLINK evaluator returns an unimplemented message.
    // Author friendly labels here; attach standard native OOXML hyperlinks
    // after export using the narrowly scoped missing-feature adapter.
    sheet.getRange(`${c}8:${c}${lastRow}`).values = rows.map(row => [row[index] ? label : '']);
    sheet.getRange(`${c}8:${c}${lastRow}`).format.font = { name:'Arial',size:10,color:'#176273',underline:'single' };
  }
  sheet.tables.add(`A7:${lastCol}${lastRow}`, true, sheet.name.replaceAll(' ','')+'Table');
  // Reapply the intentional header over the table's default style.
  sheet.getRange(`A7:${lastCol}7`).format.fill = '#30483D';
  sheet.getRange(`A7:${lastCol}7`).format.font = { name:'Arial',size:10,bold:true,color:'#FFFFFF' };
  sheet.freezePanes.freezeRows(7);
  sheet.freezePanes.freezeColumns(2);
  expected[sheet.name] = {headers, rows, linkColumns};
}

const pHeaders = ['Catalogue ID','Sculpture / option','Family','Dimensions and depth','Approximate weight','Material and finish','Fixing choices','Price (GBP)','Price status','Availability','Lead min (weeks)','Lead max (weeks)','Image qualification','Image','Folder','All photographs'];
const pRows = data.products.map(p => [p.catalogue_option_id,p.product_name,p.family,p.dimensions_and_depth,p.weight,p.material_and_finish,p.fixing_choices,p.individual_price_gbp,p.price_status,p.availability,p.lead_time_min_weeks,p.lead_time_max_weeks,p.individual_image_role,p.image_url,p.folder_url,p.all_images_review]);
setup(products,'Boldstone sculpture catalogue','Working specifications. Estimates and source claims retain their qualifications.',pHeaders,pRows,[23,43,24,64,55,65,25,14,20,18,12,12,23,17,17,20],{13:'Image',14:'Folder',15:'All photographs'});
products.tabColor='#30483D';
products.getRange('B4').values=[['Active options']];products.getRange('C4').formulas=[['=COUNTA(A8:A195)']];
products.getRange('E4').values=[['New material proposals']];products.getRange('F4').formulas=[['=COUNTIFS(Changes!$D$8:$D$37,"Material / finish")']];
products.getRange('H4').values=[['New face estimates']];products.getRange('I4').formulas=[['=COUNTIFS(Changes!$D$8:$D$37,"Dimensions / depth")']];
products.getRange('H8:H195').setNumberFormat('"£"#,##0.00');
products.getRange('K8:L195').setNumberFormat('0');

const mHeaders=['Catalogue ID','Sculpture / option','Listing treatment','Reason','Product / variant group','Creation role','Selected source','Squarespace product ID','Squarespace variant ID','Existing SKU','Proposed SKU','Local Shopify handle','Existing parent for new variant','Status','Image','Folder'];
const mRows=data.treatments.map(t=>[t.product_id,t.name,friendly(t.listing_treatment),t.reason,t.proposed_product_group_key,t.product_creation_role,t.selected_source_offer_refs.join('; '),t.selected_squarespace_product_id,t.selected_squarespace_variant_id,t.selected_existing_source_sku,t.proposed_listing_sku,t.selected_local_shopify_handle,t.suggested_existing_parent_product_id,friendly(t.status),t.selected_image.image_url,t.selected_image.folder_url]);
setup(matches,'Product and variant matching','Local disposition of all 188 options. Historical source links do not certify the live account.',mHeaders,mRows,[23,43,42,90,45,38,17,30,39,25,25,38,31,60,17,17],{14:'Image',15:'Folder'});
matches.tabColor='#658071';
matches.getRange('B4').values=[['Supported existing individual records']];matches.getRange('C4').values=[[47]];
matches.getRange('E4').values=[['Working Wall Circle pattern mappings']];matches.getRange('F4').values=[[4]];
matches.getRange('H4').values=[['Distinct proposed new products']];matches.getRange('I4').values=[[data.summary.new_proposed_product_groups]];
matches.getRange('N8:N195').conditionalFormats.add('containsText',{text:'unresolved',format:{fill:'#FFF0C2',font:{color:'#7C4B00'}}});
matches.getRange('N8:N195').conditionalFormats.add('containsText',{text:'held',format:{fill:'#FFF0C2',font:{color:'#7C4B00'}}});

const cHeaders=['Catalogue ID','Sculpture / option','Change type','Field','Previous detail','New working detail','Qualification','Basis','Image','Folder'];
const cRows=data.changes.map(c=>[c.product_id,c.name,c.basis_type,c.field,clean(c.before.display),clean(c.after.display),clean(c.after.state),clean(c.after.basis),c.image_url,c.folder_url]);
setup(changes,'Specification completion','27 material proposals and 3 face-size estimates. No new measurements or maker confirmations.',cHeaders,cRows,[23,43,30,24,70,78,70,95,17,17],{8:'Image',9:'Folder'});
changes.getRange('F8:F37').format.fill='#FFF5D8';

const sHeaders=['Catalogue ID','Sculpture / option','Source ref','Source relationship','Use for selected listing','Sale-unit evidence','Design evidence','Finish evidence','Size comparison','Source SKU','Native product ID','Source listing'];
const sRows=audit.entries.map(e=>[e.product_id,e.name,e.offer_ref,friendly(e.retained_relationship),e.selected_for_individual_listing?'Yes':'Related evidence only',friendly(e.recorded_sale_unit_state??'Not established'),friendly(e.design_scope??'Not established'),friendly(e.finish_scope??'Not established'),friendly(e.size_comparison??'Not established'),e.source_sku,e.source_id,byOffer[e.offer_ref]?.source_url??'']);
setup(sources,'Retained source associations','262 scoped links reviewed. Group, family and historical version evidence remain separate from exact variants.',sHeaders,sRows,[23,43,16,55,26,43,47,50,51,24,31,22],{11:'Source listing'});

wb.recalculate();
await fs.mkdir(path.join(work,'previews'),{recursive:true});
const inspections=[];
for(const s of sheets) {
  inspections.push((await wb.inspect({kind:'table',range:`'${s.name}'!A7:F10`,include:'values,formulas',tableMaxRows:4,tableMaxCols:6,maxChars:2000})).ndjson);
  const preview=await wb.render({sheetName:s.name,range:'A1:F10',scale:1,format:'png'});
  await fs.writeFile(path.join(work,'previews',s.name.replaceAll(' ','-')+'.png'),new Uint8Array(await preview.arrayBuffer()));
}
const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:50},summary:'Final formula error scan',maxChars:3000});
await fs.writeFile(path.join(work,'workbook-inspection.ndjson'),inspections.join('\n')+'\n'+errors.ndjson+'\n');
await fs.writeFile(path.join(work,'workbook-expected.json'),JSON.stringify(expected));
const target=path.join(output,'Boldstone_Matched_Product_List_2026-10-25.xlsx');
await (await SpreadsheetFile.exportXlsx(wb)).save(target);

const saved=await SpreadsheetFile.importXlsx(await FileBlob.load(target));
const readback={};
for(const s of sheets) {
  const got=saved.worksheets.getItem(s.name);
  readback[s.name]={values:got.getUsedRange().values,formulas:got.getUsedRange().formulas};
}
await fs.writeFile(path.join(work,'saved-workbook-readback.json'),JSON.stringify(readback));
console.log(JSON.stringify({output:target,sheets:sheets.map(s=>s.name),dataRows:pRows.length,sourceRows:sRows.length,changes:cRows.length,formulaErrorScan:errors.ndjson}));
