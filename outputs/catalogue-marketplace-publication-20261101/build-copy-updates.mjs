import fs from 'node:fs/promises';
import {Workbook} from '@oai/artifact-tool';
const dir=new URL('.',import.meta.url).pathname;
const read=async p=>JSON.parse(await fs.readFile(dir+p,'utf8'));
const catalogue=await read('current-prepared-catalogue.json');
const source='/Users/tprice/Downloads/products_Nov-01_01-45-58AM.csv';
const wb=await Workbook.fromCSV(await fs.readFile(source,'utf8'),{sheetName:'Current inventory'});
const s=wb.worksheets.getItem('Current inventory');
const values=s.getUsedRange().values;
const headers=values[0],ix=Object.fromEntries(headers.map((h,i)=>[h,i]));
const bySku=new Map(values.slice(1).map(r=>[String(r[ix.SKU]),r]));
const prior=await read('../moonshell-lava-channel-refresh-20261031/channel-supplement-manifest.json');
const gm=new Map(prior.google.rows.map(r=>[r.id,r])),mm=new Map(prior.meta.rows.map(r=>[r.id,r]));
const mapping=[],rows=[],google=[],meta=[];
for(const record of catalogue.records){
  const old=bySku.get(record.sku);if(!old)throw Error('Missing SKU '+record.sku);
  if(old[ix.Title]!==record.title||Number(old[ix.Price])!==Number(record.price_gbp)||old[ix.Visible]!=='Yes')throw Error('Live mapping changed '+record.sku);
  const productId=String(old[ix['Product ID [Non Editable]']]),variantId=String(old[ix['Variant ID [Non Editable]']]);
  if(!productId||!variantId||!gm.has(variantId)||!mm.has(variantId))throw Error('Unmatched native IDs '+record.sku);
  if(!record.description_html.includes('Made from a gypsum-based material.'))throw Error('Missing material '+record.sku);
  const updated=[...old];updated[ix.Description]=record.description_html;
  for(let i=0;i<headers.length;i++)if(i!==ix.Description&&updated[i]!==old[i])throw Error('Unintended change');
  rows.push(updated);
  google.push({...gm.get(variantId),description:record.description_text});
  meta.push({...mm.get(variantId),description:record.description_text});
  mapping.push({catalogue_id:record.catalogue_id,sku:record.sku,product_id:productId,variant_id:variantId,url:record.source_website_url,surface_effect:record.surface_effect,previous_description:old[ix.Description],description_html:record.description_html,description_text:record.description_text});
}
if(rows.length!==176||new Set(mapping.map(x=>x.product_id)).size!==176)throw Error('Count/identity mismatch');
const csvValue=v=>'"'+String(v??'').replace(/"/g,'""')+'"';
async function save(name,values){const doc=Workbook.create();const sheet=doc.worksheets.add('Update');sheet.getRangeByIndexes(0,0,values.length,values[0].length).values=values;doc.recalculate();await fs.writeFile(dir+name,values.map(r=>r.map(csvValue).join(',')).join('\r\n')+'\r\n');return doc;}
const update=await save('squarespace-material-update-176.csv',[headers,...rows]);
const preview=await update.render({sheetName:'Update',range:'F1:H3',format:'png',scale:1});await fs.writeFile(dir+'material-update-preview.png',new Uint8Array(await preview.arrayBuffer()));
for(const [name,records]of[['google-material-supplement-176.csv',google],['meta-material-supplement-176.csv',meta]]){const hs=Object.keys(records[0]);await save(name,[hs,...records.map(r=>hs.map(h=>r[h]??''))]);}
await fs.copyFile(source,dir+'squarespace-inventory-before.csv');
await fs.writeFile(dir+'material-channel-mapping.json',JSON.stringify({created_utc:new Date().toISOString(),count:176,created_products:0,changed_fields:['Description'],mapping},null,2));
console.log(JSON.stringify({squarespace_updates:rows.length,new_products:0,google:google.length,meta:meta.length}));
