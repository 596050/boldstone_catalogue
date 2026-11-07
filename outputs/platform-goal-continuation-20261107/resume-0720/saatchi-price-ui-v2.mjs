// Price-only edits of exact, already-published artwork IDs through the visible UI.
export function createPriceUpdater(chrome, fs, out, initialArtworkId) {
  if(!/^\d+$/.test(initialArtworkId||''))throw Error('An exact starting overview ID is required');
  let item, intent, lastVerifiedId=initialArtworkId;
  const normalize=s=>s.toLowerCase().replace(/[^a-z0-9]+/g,'');
  const body=s=>s.split('Selected text:')[0];
  const lines=s=>body(s).split('\n');
  const index=(s,re)=>{const a=lines(s).filter(x=>re.test(x));if(a.length!==1)throw Error('Expected one control '+re+'; found '+a.length);return Number(a[0].trim().match(/^\d+/)[0]);};
  const state=()=>chrome.getAXState({emit:false,disableDiffing:true});
  const file=()=>`${out}/price-updates/${item.native_artwork_id}.json`;
  const save=async()=>{intent.updated_utc=new Date().toISOString();await fs.writeFile(file(),JSON.stringify(intent,null,2));};
  const sourceCurrent=async()=>{const p=JSON.parse(await fs.readFile('/Users/tprice/Documents/boldstone/sculpture-catalogue/current-master.json','utf8'));if(p.current_app_review_workbook.sha256!==item.source_workbook_sha256)throw Error('Catalogue workbook changed; reconcile price targets before writing');};
  const proof=async(label,s)=>{const p=`${out}/evidence/saatchi-${item.native_artwork_id}-${label}.txt`;await fs.writeFile(p,s);return p;};
  const phase=()=>({phase:intent.phase,id:item.native_artwork_id,title:item.title,target:item.catalogue_target_usd});
  function exactRoute(s,suffix){return lines(s).some(l=>/^\s*\d+ HTML content/.test(l)&&l.includes(`/studio/art/${item.native_artwork_id}/${suffix}`));}
  function text(s,re){const a=lines(s).map(l=>l.replace(/^\s*\d+ /,'')).filter(l=>re.test(l));if(a.length!==1)throw Error('Expected one value '+re);return a[0];}
  function overviewData(s){
    const title=text(s,/^text .* Views \d+ Favorites \d+$/).replace(/^text /,'').replace(/ Views \d+ Favorites \d+$/,'');
    if(normalize(title)!==normalize(item.title))throw Error('Artwork title conflict');
    const price=Number(text(s,/^text Price Artwork Price \$/).match(/Artwork Price \$([\d,.]+)/)[1].replaceAll(',',''));
    const keys={};
    for(const key of ['Visibility:','Subject, Category, Year','Method, Materials & Styles','Dimensions','Quantity','Weight & Packaging','Additional Details']) {
      keys[key]=text(s,new RegExp('^text '+key.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')));
    }
    if(!keys['Visibility:'].includes('Published'))throw Error('Artwork is not published');
    return {title,price,keys};
  }
  function fields(s){
    const numeric={};
    for(const line of lines(s)) {
      const m=line.match(/stepper \(settable, float\).*Value: ([^,\n]+), Placeholder: (.*)$/);
      if(m)numeric[m[2]]=m[1];
    }
    const radios=lines(s).filter(l=>/radio button .*Value: 1$/.test(l)).map(l=>l.replace(/^\s*\d+ /,'')).sort();
    if(!('Enter price' in numeric)||!('Enter weight' in numeric))throw Error('Missing price or packing control');
    return {numeric,radios};
  }
  function unchangedFields(before,after){
    for(const [key,value]of Object.entries(before.numeric))if(key!=='Enter price'&&after.numeric[key]!==value)throw Error('Unrequested numeric change '+key);
    if(JSON.stringify(before.radios)!==JSON.stringify(after.radios))throw Error('Unrequested option change');
  }
  function deliveryQuote(s){
    const shipping=lines(s).find(l=>/text Shipping Cost to\s+United States Paid by Collector US\$/.test(l));
    const total=lines(s).find(l=>/text List Price in\s+United States/.test(l));
    const amount=l=>{const m=l?.match(/US\$\s*([\d,.]+)/);return m?Number(m[1].replaceAll(',','')):null;};
    const ship=amount(shipping),all=amount(total);
    return {shipping_usd:ship,list_price_usd:all,ready:ship>0&&all>0&&Math.abs(all-item.catalogue_target_usd-ship)<0.01};
  }
  async function navigate(url){const s=await state();await chrome.click(index(s,/text field \(settable\) Address and search bar/));await chrome.pressKey('super+a');await chrome.paste(url);await chrome.pressKey('Return');await state();}
  async function verifySaved(s){
    const after=overviewData(s);
    if(after.price!==item.catalogue_target_usd)throw Error('Saved price not at target');
    if(JSON.stringify(after.keys)!==JSON.stringify(intent.before.keys))throw Error('A non-price overview field changed');
    if(intent.phase!=='WAIT_RELOAD'){
      intent.phase='WAIT_RELOAD';intent.reload_utc=new Date().toISOString();intent.after_save_evidence=await proof('price-after-save',s);await save();
      await chrome.click(index(s,/button Reload$/));await state();return phase();
    }
    if(Date.now()-Date.parse(intent.reload_utc)<1500)return phase();
    intent.after=after;intent.phase='VERIFIED_PRICE_ONLY_SAVE_AND_RELOAD';intent.verified_utc=new Date().toISOString();lastVerifiedId=item.native_artwork_id;
    intent.evidence=await proof('price-reloaded',s);intent.other_displayed_fields_unchanged=true;await save();return phase();
  }
  return {
    async start(next){
      if(intent&&!['VERIFIED_PRICE_ONLY_SAVE_AND_RELOAD','VERIFIED_ALREADY_CURRENT'].includes(intent.phase))throw Error('Finish or reconcile the current price edit first');
      const current=await state();
      if(!lines(current).some(l=>/^\s*\d+ HTML content/.test(l)&&l.includes(`/studio/art/${lastVerifiedId}/overview`)))throw Error('Current task overview changed; do not navigate away from another workflow');
      item=next;
      if(!/^\d+$/.test(item.native_artwork_id)||!Number.isInteger(item.catalogue_target_usd)||item.catalogue_target_usd<=0||item.status!=='Published')throw Error('Invalid published-artwork price case');
      await sourceCurrent();
      await fs.mkdir(out+'/price-updates',{recursive:true});await fs.mkdir(out+'/evidence',{recursive:true});
      try{await fs.access(file());throw Error('An intent already exists; resume it');}catch(e){if(e.code!=='ENOENT')throw e;}
      intent={phase:'WAIT_OVERVIEW',item,started_utc:new Date().toISOString(),native_create_calls:0};await save();
      await navigate(`https://www.saatchiart.com/en-gb/studio/art/${item.native_artwork_id}/overview`);return phase();
    },
    async resume(id){item={native_artwork_id:id};intent=JSON.parse(await fs.readFile(file(),'utf8'));item=intent.item;return phase();},
    async reconcileNotSaved(evidencePath){
      if(intent.phase!=='SAVE_REQUIRES_RECONCILIATION'||intent.first_save_http_status!==401||intent.first_submission_delivery_quote_usd!==0||intent.explicit_captcha_failure||(intent.ready_retry_count||0)>0)throw Error('A ready retry is not authorized by the recorded failure evidence');
      const independent=await fs.readFile(evidencePath,'utf8');
      if(!exactRoute(independent,'overview'))throw Error('Independent saved-state evidence is for another route');
      const saved=overviewData(independent);
      if(saved.price!==intent.before.price||JSON.stringify(saved.keys)!==JSON.stringify(intent.before.keys))throw Error('The first save changed server state; do not retry');
      const s=await state();if(!exactRoute(s,'price-details'))throw Error('Return to the exact staged price form first');
      unchangedFields(intent.form_before,fields(s));
      if(Number(fields(s).numeric['Enter price'].replaceAll(',',''))!==item.catalogue_target_usd||!deliveryQuote(s).ready)throw Error('The corrected form is not ready');
      intent.ready_retry_count=1;intent.failed_save_reconciliation_evidence=evidencePath;intent.phase='STAGED_PRICE_ONLY';await save();return phase();
    },
    async step(){
      if(!intent)throw Error('No active price edit');
      if(['VERIFIED_PRICE_ONLY_SAVE_AND_RELOAD','VERIFIED_ALREADY_CURRENT'].includes(intent.phase))return phase();
      const s=await state();
      if(intent.phase==='WAIT_OVERVIEW'){
        if(!exactRoute(s,'overview'))return phase();
        const before=overviewData(s);intent.before=before;intent.before_evidence=await proof('price-before-overview',s);
        if(before.price===item.catalogue_target_usd){intent.phase='VERIFIED_ALREADY_CURRENT';intent.verified_utc=new Date().toISOString();lastVerifiedId=item.native_artwork_id;await save();return phase();}
        if(before.price!==item.observed_price_usd)throw Error('Native price changed since the audit; reconcile before overwriting');
        const section=lines(s).findIndex(l=>/heading .*Price & Details/.test(l));
        const edit=lines(s).slice(section+1).find(l=>/button Edit$/.test(l));
        if(section<0||!edit)throw Error('Price edit control absent');
        intent.phase='WAIT_PRICE_FORM';await save();await chrome.click(Number(edit.trim().match(/^\d+/)[0]));await state();return phase();
      }
      if(intent.phase==='WAIT_PRICE_FORM'){
        if(!exactRoute(s,'price-details')||!body(s).includes('Placeholder: Enter price'))return phase();
        index(s,/button SAVE & EXIT$/);
        if(/by (?:clicking|selecting)[^\n]*(?:agree|terms)/i.test(body(s)))throw Error('Explicit agreement needs owner confirmation');
        const before=fields(s);if(Number(before.numeric['Enter price'].replaceAll(',',''))!==intent.before.price)throw Error('Price form baseline mismatch');
        intent.form_before=before;intent.phase='STAGING_PRICE_ONLY';await save();
        await chrome.click(index(s,/stepper .*Placeholder: Enter price$/));await chrome.pressKey('super+a');await chrome.typeText(String(item.catalogue_target_usd));await chrome.pressKey('Tab');
        const staged=await state();unchangedFields(before,fields(staged));
        if(Number(fields(staged).numeric['Enter price'].replaceAll(',',''))!==item.catalogue_target_usd)throw Error('Price not staged');
        intent.phase='STAGED_PRICE_ONLY';intent.staged_evidence=await proof('price-staged',staged);await save();return phase();
      }
      if(intent.phase==='STAGED_PRICE_ONLY'){
        await sourceCurrent();
        if(!exactRoute(s,'price-details'))throw Error('Price page changed before save');
        const staged=fields(s);unchangedFields(intent.form_before,staged);
        if(Number(staged.numeric['Enter price'].replaceAll(',',''))!==item.catalogue_target_usd)throw Error('Staged price changed');
        const quote=deliveryQuote(s);if(!quote.ready)return {...phase(),waiting_for:'POSITIVE_COMPLETED_DELIVERY_QUOTE'};
        intent.delivery_quote_before_submit=quote;
        intent.phase='SAVE_SUBMITTED';intent.submitted_utc=new Date().toISOString();await save();
        await chrome.click(index(s,/button SAVE & EXIT$/));await state();return phase();
      }
      if(intent.phase==='STAGING_PRICE_ONLY'){
        if(!exactRoute(s,'price-details'))throw Error('Cannot reconcile the staged price on another page');
        const current=fields(s);unchangedFields(intent.form_before,current);
        const value=Number(current.numeric['Enter price'].replaceAll(',',''));
        if(value===item.catalogue_target_usd)intent.phase='STAGED_PRICE_ONLY';
        else if(value===intent.before.price)intent.phase='WAIT_PRICE_FORM';
        else throw Error('Unexpected partially staged price; manual reconciliation required');
        await save();return phase();
      }
      if(['SAVE_SUBMITTED','WAIT_RELOAD'].includes(intent.phase)){
        if(exactRoute(s,'overview')&&body(s).includes('Price Artwork Price $'))return verifySaved(s);
        if(Date.now()-Date.parse(intent.submitted_utc)>30000){intent.phase='SAVE_REQUIRES_RECONCILIATION';intent.evidence=await proof('save-unconfirmed',s);await save();}
        return phase();
      }
      throw Error('Reconcile the durable price intent before further actions: '+intent.phase);
    },
    status:()=>phase()
  };
}
