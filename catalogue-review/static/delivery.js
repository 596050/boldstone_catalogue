'use strict';
let deliveryEditor=null,deliveryOpening=0;
const deliveryMoney=pence=>'£'+(pence/100).toLocaleString('en-GB',{minimumFractionDigits:2,maximumFractionDigits:2});
const deliveryDate=value=>new Date(value).toLocaleString('en-GB');
function ensureDeliveryDialog(){
  let dialog=$('#delivery-dialog');if(dialog)return dialog;
  dialog=document.createElement('dialog');dialog.id='delivery-dialog';dialog.className='delivery-dialog';dialog.setAttribute('aria-label','Delivery checker');document.body.append(dialog);
  dialog.addEventListener('cancel',event=>{event.preventDefault();closeDelivery();});return dialog;
}
function closeDelivery(){
  const e=deliveryEditor;if(e?.saving)return;
  if(e?.dirty&&!window.confirm('Discard unsaved package details?'))return;
  clearTimeout(e?.timer);clearTimeout(e?.refreshTimer);deliveryOpening++;deliveryEditor=null;state.dirty.delete('delivery-editor');$('#delivery-dialog').close();
}
async function openDelivery(pid=''){
  if(deliveryEditor?.saving)return;
  if(deliveryEditor?.dirty&&!window.confirm('Discard unsaved package details?'))return;
  clearTimeout(deliveryEditor?.timer);clearTimeout(deliveryEditor?.refreshTimer);deliveryEditor=null;state.dirty.delete('delivery-editor');
  const request=++deliveryOpening,dialog=ensureDeliveryDialog();
  dialog.innerHTML='<button class="close" data-delivery-close aria-label="Close delivery checker">×</button><p>Loading delivery checker…</p>';if(!dialog.open)dialog.showModal();
  try{
    const payload=await api('/api/delivery'+(pid?'?product_id='+encodeURIComponent(pid):''));
    if(request!==deliveryOpening||!dialog.open)return;
    deliveryEditor={pid,payload,quoteRequest:0,dirty:false,saving:false};renderDelivery();
    previewDelivery();refreshDelivery(false);
  }catch(error){if(request===deliveryOpening&&dialog.open)dialog.innerHTML=`<button class="close" data-delivery-close aria-label="Close delivery checker">×</button><p role="alert">${esc(error.message)}</p>`;}
}
function deliveryNumber(label,name,value,min){return `<label>${label}<input name="${name}" type="number" value="${value??''}" min="${min}" max="${name==='weight_kg'?1000:10000}" step="any" required></label>`;}
function renderDelivery(){
  const e=deliveryEditor,p=e.payload,d=p.package.data;
  $('#delivery-dialog').innerHTML=`<button class="close" data-delivery-close aria-label="Close delivery checker">×</button><span class="eyebrow">UK PARCEL DELIVERY · GBP</span><h2>${esc(p.name||'Delivery checker')}</h2><p>Quote one fully packed parcel using Royal Mail Tracked 48 online prices. Enter the outer box measurements and total weight, including packaging.</p><section id="delivery-rates" aria-live="polite"></section><form id="delivery-form"><div class="delivery-inputs">${deliveryNumber('Box length (cm)','length_cm',d.length_cm,.001)}${deliveryNumber('Box width (cm)','width_cm',d.width_cm,.001)}${deliveryNumber('Box depth (cm)','depth_cm',d.depth_cm,.001)}${deliveryNumber('Packed weight (kg)','weight_kg',d.weight_kg,.001)}${deliveryNumber('Packaging charge (£)','packaging_gbp',d.packaging_gbp??0,0)}<label>Destination<select name="destination"><option value="uk"${d.destination!=='international'?' selected':''}>United Kingdom</option><option value="international"${d.destination==='international'?' selected':''}>International - separate quote</option></select></label></div><label class="delivery-collection"><input type="checkbox" name="collection"${d.collection?' checked':''}> Add Royal Mail parcel collection</label><div id="delivery-result" aria-live="polite"></div><div class="delivery-save">${e.pid?'<button class="button dark" type="submit">Save package details</button>':'<span class="small muted">Open Delivery checker from a sculpture’s specification card to save its package details.</span>'}<span id="delivery-save-status" role="status">${p.package.version?'Package details saved '+esc(deliveryDate(p.package.updated_at)):''}</span></div></form><p class="small muted">Each box needs its own quote. Box orientation is checked automatically. Product dimensions and weight are kept separate from these packed measurements. The postage total is separate from the sculpture price.</p><a class="button" href="https://send.royalmail.com/" target="_blank" rel="noopener">Open Royal Mail postage ↗</a>`;
  e.baseline=formSnapshot($('#delivery-form'));renderDeliveryRates();
}
function renderDeliveryRates(){
  const e=deliveryEditor;if(!e)return;
  const r=e.payload,t=r.tariff,a=r.last_attempt;
  $('#delivery-rates').innerHTML=`<div class="delivery-rate-heading"><div><strong>Royal Mail Tracked 48</strong><p class="small">Rates verified ${esc(deliveryDate(t.verified_at))}${t.effective_date?' · effective '+esc(t.effective_date):''}</p></div><button type="button" class="button" data-delivery-refresh${e.checking||r.refreshing?' disabled':''}>${e.checking||r.refreshing?'Checking prices…':'Check prices now'}</button></div>${a?.status==='failed'?`<p class="delivery-warning" role="status">${esc(a.message)}</p>`:r.stale?'<p class="delivery-warning">These saved rates are more than 24 hours old. Check the latest Royal Mail prices before quoting.</p>':''}<p class="small muted">${a?'Last attempt '+esc(deliveryDate(a.at))+'. ':''}Automatic checks run when you open this checker, at most once a day. A failed check keeps the last verified tariff.</p><details><summary>Parcel tiers and source</summary><table class="delivery-table"><thead><tr><th>Parcel</th><th>Maximum box (cm)</th><th>Online postage</th></tr></thead><tbody>${t.tiers.map(row=>`<tr><td>${esc(row.label)}</td><td>${row.max_cm.map(esc).join(' x ')}</td><td>${deliveryMoney(row.pence)}</td></tr>`).join('')}</tbody></table><p>Collection: ${deliveryMoney(t.collection_pence)} per parcel. Royal Mail postage includes VAT. Compensation is up to £${esc(t.compensation_gbp)}, subject to Royal Mail’s terms. Delivery aims vary by postcode.</p><p><a href="${safeURL(t.source_url)}" target="_blank" rel="noopener">Published prices and service details ↗</a> · <a href="${safeURL(t.guide_url)}" target="_blank" rel="noopener">October 2026 online price guide ↗</a></p><p class="small muted">This checker reads published prices. It is not connected to a postage account and does not purchase labels.</p></details>`;
}
function deliveryFormData(){
  const form=$('#delivery-form'),f=new FormData(form);
  return {length_cm:Number(f.get('length_cm')),width_cm:Number(f.get('width_cm')),depth_cm:Number(f.get('depth_cm')),weight_kg:Number(f.get('weight_kg')),packaging_gbp:Number(f.get('packaging_gbp')),collection:f.has('collection'),destination:f.get('destination')};
}
async function previewDelivery(){
  const e=deliveryEditor;if(!e||e.saving)return;
  const request=++e.quoteRequest,form=$('#delivery-form');
  if(!form.checkValidity()){$('#delivery-result').innerHTML='<p>Enter all four packed measurements to calculate postage.</p>';return;}
  const data=deliveryFormData();$('#delivery-result').textContent='Calculating postage…';
  try{
    const result=await api('/api/delivery/quote',{data});
    if(deliveryEditor!==e||request!==e.quoteRequest||JSON.stringify(data)!==JSON.stringify(deliveryFormData()))return;
    if(result.status!=='calculated'){$('#delivery-result').innerHTML=`<strong>${esc(result.message)}</strong>`;return;}
    $('#delivery-result').innerHTML=`<span class="eyebrow">${result.rates.needs_confirmation?'SAVED TARIFF · CONFIRM CURRENT RATE':'PUBLISHED TARIFF QUOTE'}</span><h3>${esc(result.tier.label)}</h3><dl><div><dt>Postage</dt><dd>${deliveryMoney(result.postage_pence)}</dd></div><div><dt>Collection</dt><dd>${deliveryMoney(result.collection_pence)}</dd></div><div><dt>Packaging</dt><dd>${deliveryMoney(result.packaging_pence)}</dd></div><div class="delivery-total"><dt>Delivery total</dt><dd>${deliveryMoney(result.total_pence)}</dd></div></dl>`;
  }catch(error){if(deliveryEditor===e&&request===e.quoteRequest)$('#delivery-result').textContent=error.message;}
}
async function refreshDelivery(force){
  const e=deliveryEditor;if(!e||e.checking)return;
  e.checking=true;clearTimeout(e.refreshTimer);renderDeliveryRates();
  try{
    const r=await api('/api/delivery/refresh',{force});
    if(deliveryEditor!==e)return;
    e.payload={...e.payload,...r};
  }catch(error){if(deliveryEditor===e)e.payload={...e.payload,last_attempt:{at:new Date().toISOString(),status:'failed',message:'Price check could not finish: '+error.message}};}
  finally{if(deliveryEditor===e){e.checking=false;renderDeliveryRates();previewDelivery();
    // Reopen/poll a check already started in another tab without duplicating it.
    e.refreshTimer=setTimeout(()=>refreshDelivery(false),e.payload.refreshing?2000:60*60*1000);
  }}
}
async function saveDelivery(){
  const e=deliveryEditor;if(!e||!e.pid||e.saving||!$('#delivery-form').reportValidity())return;
  const data=deliveryFormData(),form=$('#delivery-form');e.saving=true;form.inert=true;$('#delivery-save-status').textContent='Saving package details…';
  try{
    const saved=await api('/api/reviews',{kind:'delivery',product_id:e.pid,item_id:'',version:e.payload.package.version,data});
    if(deliveryEditor!==e)return;
    e.payload.package=saved;e.baseline=formSnapshot(form);e.dirty=false;state.dirty.delete('delivery-editor');
    $('#delivery-save-status').textContent='Package details saved '+deliveryDate(saved.updated_at);toast('Package details saved');
  }catch(error){if(deliveryEditor===e)$('#delivery-save-status').textContent=error.message;}
  finally{e.saving=false;form.inert=false;if(deliveryEditor===e)previewDelivery();}
}
document.addEventListener('click',event=>{
  const b=event.target.closest('button');if(!b)return;
  if(b.id==='delivery-open')openDelivery(state.current?.id===state.pid&&!state.pid.startsWith('__')?state.pid:'');
  if(b.hasAttribute('data-delivery-product'))openDelivery(b.dataset.deliveryProduct);
  if(b.hasAttribute('data-delivery-close'))closeDelivery();
  if(b.hasAttribute('data-delivery-refresh'))refreshDelivery(true);
});
function deliveryInput(event){
  const e=deliveryEditor;if(!e||e.saving||!event.target.closest('#delivery-form'))return;
  e.quoteRequest++;clearTimeout(e.timer);e.dirty=!!e.pid&&formSnapshot($('#delivery-form'))!==e.baseline;
  if(e.dirty)state.dirty.add('delivery-editor');else state.dirty.delete('delivery-editor');
  $('#delivery-save-status').textContent=e.dirty?'Package details changed - save to keep them.':'';
  $('#delivery-result').textContent='Recalculating postage…';e.timer=setTimeout(previewDelivery,180);
}
document.addEventListener('input',deliveryInput);document.addEventListener('change',deliveryInput);
document.addEventListener('submit',event=>{if(event.target.id==='delivery-form'){event.preventDefault();saveDelivery();}});
