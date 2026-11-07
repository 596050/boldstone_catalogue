export function helpers(chrome,fs,out){
 const idx=(s,re)=>{const m=s.split('\n').filter(l=>/^\s*\d+ /.test(l)&&re.test(l));if(m.length!==1)throw Error('Expected one '+re+' got '+m.length);return +m[0].trim().match(/^\d+/)[0];};
 const esc=s=>s.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
 const value=(s,re)=>s.split('\n').find(l=>re.test(l))?.match(/Value: (.*?)(?:, Placeholder:|$)/)?.[1];
 const state=()=>chrome.getAXState({emit:false,disableDiffing:true});
 async function until(test){let s=await state();for(let i=0;i<3&&!test(s);i++){await chrome.getScreenshot({emit:false});s=await state();}if(!test(s))throw Error('Native page did not reach expected state');return s;}
 async function focus(){let s=await state();if(!s.includes('Home – Faire')){await chrome.click(idx(s,/^\s*\d+ Window$/));const m=await state();await chrome.click(idx(m,/^\s*\d+ (?:.*Furnitures.*|Meta Business Suite|Boldstone Sculpture – Faire|Home – Faire|Faire \/ Boldstone Sculpture:).*ID: makeKeyAndOrderFront:/));s=await state();}return s;}
 async function furnitureBatch(limit=3){
  const plan=JSON.parse(await fs.readFile(out+'/furnitures-upload-plan.json','utf8'));
  const receipts=JSON.parse(await fs.readFile(out+'/furnitures-field-receipts.json','utf8'));
  const bindings=JSON.parse(await fs.readFile(out+'/furnitures-native-bindings.json','utf8'));
  let n=0;
  for(const r of plan.records){
   if(receipts.some(x=>x.sku===r.sku&&x.status==='VERIFIED_SAVED'))continue;
   let s=await focus();
   if(!/Address and search bar[^\n]*Value: (?:https:\/\/)?furnitures\.co\.uk\/dashboard\/products/.test(s))throw Error('Open Furnitures Products first');
   const binding=bindings.find(x=>x.sku===r.sku);if(!binding||binding.catalogue_id!==r.catalogue_id)throw Error('Missing native binding');
   await chrome.pressKey('super+l');await chrome.setValue(idx(s,/text field .*Address and search bar/),binding.edit_url);
   s=await state();if(value(s,/text field .*Address and search bar/)!==binding.edit_url)throw Error('Address entry differs from verified native URL');
   await chrome.pressKey('Return');
   s=await until(t=>value(t,/text field.*Product name,/)===r.title);
   const path=s.match(/Address and search bar, Value: (furnitures\.co\.uk\/dashboard\/products\/[a-z0-9-]+)/)?.[1];if(!path)throw Error('Native identity missing');
   const actual=Number(value(s,/text field.*Price \(£\),/));if(actual!==r.price_gbp)throw Error('Price mismatch '+r.sku);
   const rec={sku:r.sku,catalogue_id:r.catalogue_id,title:r.title,edit_url:'https://'+path,status:'UPDATING',utc:new Date().toISOString()};receipts.push(rec);
   await fs.writeFile(out+'/furnitures-field-receipts.json',JSON.stringify(receipts,null,2));
   for(const [re,v]of [[/text field .*\) Material,/,r.material],[/text field .*\) Dimensions,/,r.dimensions],[/text field .*\) Colour,/,r.colour]])if(value(s,re)!==v)await chrome.setValue(idx(s,re),v);
   if(r.sku==='SQ1068535'&&!s.includes('The delivery charge for your order is shown at checkout.'))await chrome.setValue(idx(s,/text entry area .*\) Description,/),r.description);
   s=await state();await chrome.click(idx(s,/button Save changes$/));s=await until(t=>t.includes('Saved — changes are live.'));
   for(const [re,v]of [[/text field .*\) Material,/,r.material],[/text field .*\) Dimensions,/,r.dimensions],[/text field .*\) Colour,/,r.colour]])if(value(s,re)!==v)throw Error('Saved specification mismatch '+r.sku);
   if(!s.includes('Sally Price')||!s.includes('The delivery charge for your order is shown at checkout.'))throw Error('Description not retained');
   const images=s.match(/text entry area.*Images \(one URL per line, up to 6\).*Value: ([\s\S]*?)(?=\n\s*\d+ )/)?.[1].trim().split('\n');
   if(JSON.stringify(images)!==JSON.stringify(r.image_urls))throw Error('Saved image list mismatch '+r.sku);
   Object.assign(rec,{status:'VERIFIED_SAVED',price_gbp:actual,image_count:images.length,description_verified:true});
   await fs.writeFile(out+'/furnitures-field-receipts.json',JSON.stringify(receipts,null,2));await fs.writeFile(out+'/evidence/furnitures-'+r.catalogue_id+'-saved.txt',s);
   if(++n>=limit)break;
  }
  return {newly_verified:n,total_verified:receipts.filter(x=>x.status==='VERIFIED_SAVED').length};
 }
 return {idx,value,state,until,focus,furnitureBatch};
}
