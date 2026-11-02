// Import only inside cua_repl. All remote interaction uses the visible UI.
// Reuses prior native listing IDs and verifies the SKU before editing.
import fs from 'node:fs/promises';

export function marketplaceDescriptionUpdates({tab,records,root}) {
  const directory=`${root}/catalogue-copy-disclosures`;
  const receiptsPath=`${directory}/marketplace-copy-receipts.json`;
  const intentPath=`${directory}/marketplace-copy-intent.json`;
  const aliasesPath=`${directory}/marketplace-edit-id-aliases.json`;
  const read=async p=>JSON.parse(await fs.readFile(p,'utf8'));
  const write=async(p,d)=>{await fs.writeFile(p+'.tmp',JSON.stringify(d,null,2)+'\n');await fs.rename(p+'.tmp',p);};
  const textbox=label=>tab.playwright.getByRole('textbox',{name:label,exact:true});
  const value=label=>textbox(label).evaluate(e=>e.value);
  async function snapshot() {
    return {sku:await value('SKU'),description:await value('Description'),material:await value('Material'),
      other:{title:await value('Title'),price:await value('Price'),
        tags:{value:await tab.playwright.getByRole('textbox',{name:/^Product tags/}).evaluate(e=>e.value),
          selected:await tab.playwright.getByRole('form',{name:'Marketplace',exact:true}).getByRole('list').allTextContents()},
        choices:await tab.playwright.getByRole('form',{name:'Marketplace',exact:true}).getByRole('combobox')
          .evaluateAll(es=>es.map(e=>({text:e.innerText,value:e.value}))),
        checks:await tab.playwright.getByRole('form',{name:'Marketplace',exact:true})
          .evaluate(e=>Array.from(e.querySelectorAll('[role="checkbox"],[role="switch"]')).map(x=>({label:x.getAttribute('aria-label'),checked:x.getAttribute('aria-checked')}))),
        photos:await tab.playwright.getByRole('img',{name:'Listing photo: No photo description available.',exact:true})
          .evaluateAll(es=>es.map(e=>new URL(e.src).pathname))}};
  }
  async function open(url,sku,reload=false) {
    if(await tab.url()!==url)await tab.goto(url);else if(reload)await tab.reload();
    await textbox('Description').waitFor({state:'visible',timeoutMs:15000});
    await tab.playwright.domSnapshot();
    const data=await snapshot();
    if(data.sku!==sku)throw Error('Existing Marketplace SKU mismatch '+sku+' / '+data.sku);
    return data;
  }
  async function resolveEditId(binding,record) {
    // Advertising/catalogue target IDs can open incomplete, non-editable
    // records. Obtain the real edit URL through the seller's own listing UI.
    await tab.goto('https://www.facebook.com/marketplace/you/selling');
    await textbox('Search your listings').fill(record.title);
    await textbox('Search your listings').press('Enter');
    const control=tab.playwright.getByRole('button',{name:'More options for '+record.title+' | Wall Sculpture',exact:true});
    await control.waitFor({state:'visible',timeoutMs:15000});
    if(await control.count()!==1)throw Error('Ambiguous native Marketplace result '+record.sku);
    await control.click();
    const edit=tab.playwright.getByRole('menuitem',{name:'Edit listing',exact:true});
    await edit.waitFor({state:'visible',timeoutMs:10000});await edit.click();
    await textbox('Description').waitFor({state:'visible',timeoutMs:15000});
    await tab.playwright.domSnapshot();
    const data=await snapshot(),url=await tab.url();
    if(data.sku!==record.sku)throw Error('Resolved edit page does not match catalogue SKU');
    const listing_id=url.match(/[?&]listing_id=(\d+)/)?.[1];
    if(!listing_id)throw Error('No native edit ID');
    const aliases=await read(aliasesPath).catch(()=>[]);
    aliases.push({prior_id:binding.listing_id,listing_id,url,sku:record.sku,at:new Date().toISOString(),evidence:'Seller list search -> More options -> Edit listing -> exact SKU readback'});
    await write(aliasesPath,aliases);
    return {data,url,listing_id};
  }
  async function run(limit=6) {
    const old=await read(`${root}/marketplace-material-receipts.json`);
    const remaining=await read(`${root}/marketplace-material-remaining.json`);
    const bindings=[...old,...remaining].map(b=>({...b,listing_id:b.listing_id||b.url?.match(/\/item\/(\d+)/)?.[1]}));
    const aliases=await read(aliasesPath).catch(()=>[]);
    const unique=[...new Map(bindings.map(b=>[b.listing_id,b])).values()];
    const receipts=await read(receiptsPath).catch(()=>[]);
    const pending=await read(intentPath).catch(()=>null);
    if(pending?.phase==='UPDATE_REQUESTED'&&!receipts.some(r=>r.listing_id===pending.listing_id)) {
      const saved=await open(pending.url,pending.sku,true);
      if(saved.description===pending.after && saved.material==='Gypsum-based material' && JSON.stringify(saved.other)===JSON.stringify(pending.before.other)) {
        receipts.push({...pending,status:'UPDATED_AND_REOPENED',at:new Date().toISOString()});await write(receiptsPath,receipts);
      } else if(saved.description!==pending.before.description || JSON.stringify(saved.other)!==JSON.stringify(pending.before.other)) {
        throw Error('Uncertain Marketplace save needs reconciliation '+pending.listing_id);
      }
    }
    const completed=[],started=Date.now();
    for(const binding of unique) {
      let alias=aliases.find(r=>r.prior_id===binding.listing_id);
      let listing_id=alias?.listing_id||binding.listing_id;
      if(receipts.some(r=>r.listing_id===listing_id))continue;
      const record=records.find(r=>r.catalogue_id===binding.catalogue_id);
      if(!record||!binding.listing_id)throw Error('Missing source or native listing binding');
      let url=`https://www.facebook.com/marketplace/edit/?listing_id=${listing_id}`;
      let before;
      try {before=await open(url,record.sku);} catch(error) {
        if(!String(error).includes('Existing Marketplace SKU mismatch'))throw error;
        const visible=await snapshot();
        if(visible.sku || visible.other.title!==record.title+' | Wall Sculpture' || !visible.description.includes(record.source_website_url))throw error;
        const resolved=await resolveEditId(binding,record);
        ({url,listing_id}=resolved);before=resolved.data;
        aliases.push({prior_id:binding.listing_id,listing_id,url,sku:record.sku});
      }
      if(receipts.some(r=>r.listing_id===listing_id))continue;
      if(!before.description.includes(record.source_website_url))throw Error('Source product link mismatch '+record.sku);
      const after=record.description_text+'\n\nRoom settings and group arrangements are illustrative; this listing is for the individual sculpture described above.\n\nWebsite price: £'+record.price_gbp+'. Full details, photographs and online ordering: '+record.source_website_url;
      if(!after.includes('designer Sally Price')||after.length>5000)throw Error('Description validation failed');
      const intent={sku:record.sku,catalogue_id:record.catalogue_id,listing_id,prior_id:binding.listing_id,url,before,after,phase:'PREPARED',at:new Date().toISOString()};
      await write(intentPath,intent);
      if(before.description!==after||before.material!=='Gypsum-based material') {
        await textbox('Description').fill(after);
        await textbox('Material').fill('Gypsum-based material');
        await textbox('Material').press('Tab');
        await tab.getAXState({emit:false});
        if(await value('Description')!==after)throw Error('Marketplace input mismatch');
        await write(intentPath,{...intent,phase:'UPDATE_REQUESTED'});
        await tab.playwright.getByRole('button',{name:'Update',exact:true}).click();
        await tab.playwright.getByText('Listing updated',{exact:true}).waitFor({state:'visible',timeoutMs:20000});
      }
      const saved=await open(url,record.sku,true);
      if(saved.description!==after||saved.material!=='Gypsum-based material'||JSON.stringify(saved.other)!==JSON.stringify(before.other)) {
        await write(`${directory}/marketplace-copy-mismatch.json`,{intent,saved});
        throw Error('Marketplace saved data mismatch '+record.sku);
      }
      receipts.push({...intent,phase:'VERIFIED',status:'UPDATED_AND_REOPENED',at:new Date().toISOString()});
      await write(receiptsPath,receipts); completed.push(record.sku);
      if(completed.length>=limit||Date.now()-started>40000)break;
    }
    return {saved:completed,total_verified_listings:receipts.length,total_listings:unique.length,unique_components:new Set(receipts.map(r=>r.sku)).size};
  }
  return {run};
}
