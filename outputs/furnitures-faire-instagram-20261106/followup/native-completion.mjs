export function completion(chrome,fs,out,h){
 const esc=s=>s.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
 const own=s=>s.includes('HTML content Seller Dashboard | Furnitures')&&/Address and search bar[^\n]*Value: (?:https:\/\/)?furnitures\.co\.uk\/dashboard(?:\/|,|$)/.test(s);
 async function focus(){
  let s=await h.state();
  if(!own(s)){
   await chrome.click(h.idx(s,/^\s*\d+ tab .*Seller Dashboard \| Furnitures, Value: off$/));
   s=await h.state();
  }
  if(!own(s))throw Error('Catalogue editing window is not available');
  return s;
 }
 async function list(s){
  if(!s.includes('heading Products (176),')){
   await chrome.click(h.idx(s,/link Products, Value: furnitures\.co\.uk\/(?:dashboard\/products|da…)/));
   s=await h.until(t=>own(t)&&t.includes('heading Products (176),'));
  }
  return s;
 }
 async function batch(limit=3){
  const plan=JSON.parse(await fs.readFile(out+'/furnitures-upload-plan.json','utf8'));
  const bindings=JSON.parse(await fs.readFile(out+'/furnitures-native-bindings.json','utf8'));
  const journal=JSON.parse(await fs.readFile(out+'/furnitures-field-receipts.json','utf8'));
  const save=()=>fs.writeFile(out+'/furnitures-field-receipts.json',JSON.stringify(journal,null,2));
  let count=0;
  try{
   for(const r of plan.records){
    if(journal.some(j=>j.sku===r.sku&&j.status==='VERIFIED_SAVED'))continue;
    let s=await list(await focus());
    const b=bindings.find(b=>b.catalogue_id===r.catalogue_id&&b.sku===r.sku);
    if(!b)throw Error('Missing binding');
    await chrome.click(h.idx(s,new RegExp('link Edit '+esc(r.title)+', Value:')));
    s=await h.until(t=>own(t)&&h.value(t,/text field.*Product name,/ )===r.title);
    const identity=t=>own(t)&&t.includes(b.native_id)&&h.value(t,/text field.*Product name,/ )===r.title&&Number(h.value(t,/text field.*Price \(£\),/))===r.price_gbp&&t.includes(r.sku);
    if(!identity(s))throw Error('Native product identity/price differs');
    const receipt={sku:r.sku,catalogue_id:r.catalogue_id,title:r.title,edit_url:b.edit_url,status:'UPDATING',utc:new Date().toISOString()};
    journal.push(receipt);await save();
    for(const [re,v]of[[/text field.*\) Material,/,r.material],[/text field.*\) Dimensions,/,r.dimensions],[/text field.*\) Colour,/,r.colour]]){
     s=await h.until(identity);
     if(h.value(s,re)!==v)await chrome.setValue(h.idx(s,re),v);
    }
    s=await h.until(identity);
    await chrome.click(h.idx(s,/button Save changes$/));
    s=await h.until(t=>identity(t)&&t.includes('Saved — changes are live.'));
    for(const[re,v]of[[/text field.*\) Material,/,r.material],[/text field.*\) Dimensions,/,r.dimensions],[/text field.*\) Colour,/,r.colour]])if(h.value(s,re)!==v)throw Error('Saved specification differs');
    const images=s.match(/text entry area.*Images \(one URL per line, up to 6\).*Value: ([\s\S]*?)(?=\n\s*\d+ )/)?.[1].trim().split('\n');
    if(JSON.stringify(images)!==JSON.stringify(r.image_urls))throw Error('Saved ordered gallery differs');
    if(!s.includes('Sally Price')||!s.includes('The delivery charge for your order is shown at checkout.'))throw Error('Saved description differs');
    Object.assign(receipt,{status:'VERIFIED_SAVED',price_gbp:r.price_gbp,image_count:images.length,description_verified:true});
    await save();await fs.writeFile(out+'/evidence/furnitures-'+r.catalogue_id+'-saved.txt',s);
    count++;
    if(count>=limit)break;
   }
   return {newly_verified:count,total_verified:new Set(journal.filter(j=>j.status==='VERIFIED_SAVED').map(j=>j.sku)).size};
  }catch(e){const current=await h.state();return {newly_verified:count,total_verified:new Set(journal.filter(j=>j.status==='VERIFIED_SAVED').map(j=>j.sku)).size,stopped:String(e.message),window:current.split('\n')[0]};}
 }
 return {batch};
}
