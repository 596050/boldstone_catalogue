import fs from 'node:fs/promises';
import path from 'node:path';
import {Workbook} from '@oai/artifact-tool';

const [rootArg, sourceArg, outArg] = process.argv.slice(2);
const root=path.resolve(rootArg), source=path.resolve(sourceArg), out=path.resolve(outArg);
await fs.mkdir(out,{recursive:true});
const read=async p=>JSON.parse(await fs.readFile(p,'utf8'));
const catalogue=await read(path.join(root,'current-prepared-catalogue.json'));
const csv=await Workbook.fromCSV(await fs.readFile(source,'utf8'),{sheetName:'Inventory'});
const values=csv.worksheets.getItem('Inventory').getUsedRange().values;
const headers=values[0], ix=Object.fromEntries(headers.map((h,i)=>[h,i]));
const bySku=new Map();
for(const row of values.slice(1)){
  const sku=String(row[ix.SKU]);
  if(bySku.has(sku) && catalogue.records.some(r=>r.sku===sku)) throw Error('Duplicate existing SKU '+sku);
  bySku.set(sku,row);
}
const prior=await read(path.join(root,'../moonshell-lava-channel-refresh-20261031/channel-supplement-manifest.json'));
const gm=new Map(prior.google.rows.map(r=>[r.id,r])), mm=new Map(prior.meta.rows.map(r=>[r.id,r]));
const rows=[], google=[], meta=[], mapping=[];
for(const record of catalogue.records){
  const old=bySku.get(record.sku); if(!old)throw Error('Missing SKU '+record.sku);
  if(old[ix.Title]!==record.title || Number(old[ix.Price])!==Number(record.price_gbp) || old[ix.Visible]!=='Yes') throw Error('Current source mismatch '+record.sku);
  const productId=String(old[ix['Product ID [Non Editable]']]), variantId=String(old[ix['Variant ID [Non Editable]']]);
  if(!productId||!variantId||!gm.has(variantId)||!mm.has(variantId))throw Error('Missing channel identity '+record.sku);
  if(!record.description_text.includes('designer Sally Price'))throw Error('Missing customisation '+record.sku);
  if(record.surface_effect && !record.description_text.includes('will differ from the photographs'))throw Error('Missing variation '+record.sku);
  const row=[...old];row[ix.Description]=record.description_html;rows.push(row);
  google.push({...gm.get(variantId),description:record.description_text,max_handling_time:'10'});
  meta.push({...mm.get(variantId),description:record.description_text});
  mapping.push({sku:record.sku,catalogue_id:record.catalogue_id,product_id:productId,variant_id:variantId,
    url:record.source_website_url,surface_effect:record.surface_effect,description_html:record.description_html,
    description_text:record.description_text});
}
if(rows.length!==176||new Set(mapping.map(r=>r.product_id)).size!==176)throw Error('Count or ID collision');
const quote=v=>'"'+String(v??'').replace(/"/g,'""')+'"';
async function save(name,values){
  const book=Workbook.create(),sheet=book.worksheets.add('Update');
  sheet.getRangeByIndexes(0,0,values.length,values[0].length).values=values;
  await fs.writeFile(path.join(out,name),values.map(r=>r.map(quote).join(',')).join('\r\n')+'\r\n');
}
await save('squarespace-description-update-176.csv',[headers,...rows]);
for(const [name,data] of [['google-description-supplement-176.csv',google],['meta-description-supplement-176.csv',meta]]){
  const hs=Object.keys(data[0]);await save(name,[hs,...data.map(r=>hs.map(h=>r[h]??''))]);
}
await fs.copyFile(source,path.join(out,'squarespace-before.csv'));
await fs.writeFile(path.join(out,'channel-mapping.json'),JSON.stringify({at:new Date().toISOString(),count:176,
  new_products:0,changed_fields:['Description'],mapping},null,2));
console.log(JSON.stringify({matched_existing_products:176,new_products:0,description_updates:176,google:176,meta:176}));
