import fs from 'node:fs/promises';
import path from 'node:path';
import {Workbook} from '@oai/artifact-tool';

const out=path.dirname(new URL(import.meta.url).pathname);
const read=async p=>JSON.parse(await fs.readFile(path.resolve(out,p),'utf8'));
const catalogue=await read('current-prepared-catalogue.json');
const before=await read('../tiktok-ebay-upload-20261101/catalogue-snapshot.json');
const current=await read('../tiktok-ebay-upload-20261101/catalogue-snapshot-goal-start.json');
if(JSON.stringify(before.products)!==JSON.stringify(current.products)||JSON.stringify(before.images)!==JSON.stringify(current.images))throw Error('Prepared records need refresh');
const records=catalogue.records;
if(records.length!==176||new Set(records.map(x=>x.sku)).size!==176)throw Error('Invalid source count or SKU');
const csvValue=v=>'"'+String(v??'').replace(/"/g,'""')+'"';
const writeCsv=async(name,values)=>fs.writeFile(path.join(out,name),'\ufeff'+values.map(r=>r.map(csvValue).join(',')).join('\r\n')+'\r\n');
const template=await fs.readFile('/Users/tprice/Downloads/eBay-draft-listing-template-Nov-1-2026-0-58-3.csv','utf8');
const eb=await Workbook.fromCSV(template,{sheetName:'eBay drafts'});
const es=eb.worksheets.getItem('eBay drafts');
const ep=await eb.render({sheetName:'eBay drafts',range:'A5:D6',format:'png',scale:1});
await fs.writeFile(path.join(out,'ebay-template.png'),new Uint8Array(await ep.arrayBuffer()));
const ebrows=records.map(r=>{
  if(r.title.length>80||!r.photos.length||/GFRC|Royal Mail/i.test(r.description_html))throw Error('Invalid public content '+r.sku);
  return ['Draft',r.sku,'553',r.title,'',Number(r.price_gbp),1,[...new Set(r.photos.map(p=>p.url))].slice(0,24).join('|'),'NEW',r.description_html,'FixedPrice'];
});
es.getRangeByIndexes(5,0,ebrows.length,11).values=ebrows;
eb.recalculate();
const ebayPrefix=template.split(/\r?\n/).slice(0,5).join('\r\n')+'\r\n';
const writeEbay=async(name,rows)=>fs.writeFile(path.join(out,name),ebayPrefix+rows.map(r=>r.map(csvValue).join(',')).join('\r\n')+'\r\n');
await writeEbay('ebay-in6192-176-wall-sculpture-drafts.csv',es.getRangeByIndexes(5,0,176,11).values);
const reconciliation=await read('../marketplace-ebay-expansion-20261031/ebay-reconciliation.json');
const missingIds=new Set(reconciliation.missing.map(r=>r.catalogue_id));
const saprRows=ebrows.filter((_,i)=>missingIds.has(records[i].catalogue_id));
if(saprRows.length!==157)throw Error('Unexpected missing eBay set');
await writeEbay('ebay-sapr-157-missing-wall-sculpture-drafts.csv',saprRows);

const sq=await Workbook.fromCSV(await fs.readFile('/Users/tprice/Downloads/products_Oct-31_06-43-52PM.csv','utf8'),{sheetName:'Squarespace source'});
const ss=sq.worksheets.getItem('Squarespace source');
const source=ss.getUsedRange().values;
const headers=source[0];
const index=Object.fromEntries(headers.map((h,i)=>[h,i]));
const bysku=new Map(source.slice(1).map(r=>[String(r[index.SKU]),r]));
const nativeBefore=await sq.render({sheetName:'Squarespace source',range:'F1:F3',format:'png',scale:1});
await fs.writeFile(path.join(out,'squarespace-template.png'),new Uint8Array(await nativeBefore.arrayBuffer()));
// Verified existing Wescover items: Strata and the Icarus item now titled Feather Fall.
// The Frozen Deco Waves pair is a distinct pair offer, not a duplicate individual finish listing.
const wesExisting=[
  {catalogue_id:'BSI-A0FFC102A6F1',existing_title:'Strata in Verdigris'},
  {catalogue_id:'BSI-123AABD474C1',existing_title:'Feather Fall — Icarus Wall Sculpture',sku:'SQ0717348'}
];
const wesExistingIds=new Set(wesExisting.map(r=>r.catalogue_id));
const wesRecords=records.filter(r=>!wesExistingIds.has(r.catalogue_id));
if(wesRecords.length!==174||wesRecords.some(r=>wesExistingIds.has(r.catalogue_id)))throw Error('Wescover duplicate guard failed');
const batches=[wesRecords.slice(0,1)];
for(let i=1;i<wesRecords.length;i+=50)batches.push(wesRecords.slice(i,i+50));
const manifest={created_utc:new Date().toISOString(),source_cutoff:current.event_cutoff,material_policy_utc:catalogue.material_policy_utc,ebay:{account:'in6192',action:'Draft',count:176,upload_state:'Already accepted; do not upload again without reconciling saved drafts.',records:records.map(r=>({catalogue_id:r.catalogue_id,sku:r.sku,title:r.title,price_gbp:r.price_gbp}))},wescover:{existing_matched:wesExisting,batches:[]}};
for(let i=0;i<batches.length;i++){
  const rows=batches[i].map(r=>{
    if(!bysku.has(r.sku))throw Error('Missing native export SKU '+r.sku);
    const row=[...bysku.get(r.sku)];
    row[index.Title]=r.title;row[index.Description]=r.description_html;
    row[index.Price]=Number(r.price_gbp);row[index['Sale Price']]=0;row[index['On Sale']]='No';
    row[index['Hosted Image URLs']]=[...new Set(r.photos.map(p=>p.url))].join(' ');
    return row;
  });
  const wb=Workbook.create();const sh=wb.worksheets.add('Squarespace import');
  sh.getRangeByIndexes(0,0,rows.length+1,headers.length).values=[headers,...rows];
  wb.recalculate();
  const name=`wescover-squarespace-batch-${i+1}-${rows.length}.csv`;
  await writeCsv(name,sh.getRangeByIndexes(0,0,rows.length+1,headers.length).values);
  if(i===0){const p=await wb.render({sheetName:'Squarespace import',range:'F1:H2',format:'png',scale:1});await fs.writeFile(path.join(out,'wescover-import-preview.png'),new Uint8Array(await p.arrayBuffer()));}
  manifest.wescover.batches.push({file:name,count:rows.length,records:batches[i].map(r=>({catalogue_id:r.catalogue_id,sku:r.sku,title:r.title,price_gbp:r.price_gbp,photo_count:r.photos.length}))});
}
await fs.writeFile(path.join(out,'import-manifest.json'),JSON.stringify(manifest,null,2));
// Wescover's own import template separates image URLs and can carry currency.
const wt=await Workbook.fromCSV(await fs.readFile(path.join(out,'wescover-template.csv'),'utf8'),{sheetName:'Wescover native'});
const wh=wt.worksheets.getItem('Wescover native').getUsedRange().values[0];
const fx={date:'2026-10-30',eur_usd:1.1172,eur_gbp:0.8338,usd_per_gbp:1.1172/0.8338,sources:['https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/eurofxref-graph-usd.en.html','https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/eurofxref-graph-gbp.en.html']};
await fs.writeFile(path.join(out,'currency-reference.json'),JSON.stringify(fx,null,2));
manifest.wescover.native_batches=[];
for(let i=0;i<batches.length;i++){
  // Wescover's description field is plain text. Importing HTML and stripping its
  // tags joins adjacent list items ("BoldstoneProduct type"). Use the catalogue's
  // already-formatted text, keeping each specification on its own line.
  const rows=batches[i].map(r=>{if(!r.description_text?.includes('\nBrand:'))throw Error('Missing formatted description '+r.sku);const values={TITLE:r.title,DESCRIPTION:r.description_text,PRICE:Number(r.price_gbp),CURRENCY_CODE:'GBP',QUANTITY:0,TAGS:'wall sculpture,handmade,made to order,outdoor',SKU:r.sku};r.photos.slice(0,10).forEach((p,n)=>values['IMAGE'+(n+1)]=p.url);return wh.map(h=>values[h]??'');});
  const wb=Workbook.create();const sh=wb.worksheets.add('Wescover import');
  sh.getRangeByIndexes(0,0,rows.length+1,wh.length).values=[wh,...rows];
  const name=`wescover-native-batch-${i+1}-${rows.length}.csv`;
  await writeCsv(name,sh.getRangeByIndexes(0,0,rows.length+1,wh.length).values);
  manifest.wescover.native_batches.push({file:name,count:rows.length,records:batches[i].map(r=>({sku:r.sku,title:r.title,price_gbp:r.price_gbp,selected_photos:r.photos.length,template_photos:Math.min(10,r.photos.length)}))});
}
await fs.writeFile(path.join(out,'import-manifest.json'),JSON.stringify(manifest,null,2));
console.log(JSON.stringify({source_cutoff:current.event_cutoff,ebay_drafts:ebrows.length,wescover_batches:manifest.wescover.batches.map(b=>({file:b.file,count:b.count}))}));
