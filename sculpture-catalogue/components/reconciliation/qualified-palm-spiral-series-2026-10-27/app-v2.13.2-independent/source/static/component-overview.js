'use strict';
let overviewRequest=0;
function overviewImage(image){
  const labels=[...image.selected_uses,...image.effective_types.map(t=>typeLabels()[t]||t)];
  if(image.excluded)labels.unshift('Excluded from listing');
  if(image.primary_eligible)labels.unshift('Primary listing photo');
  else if(image.primary_selected&&!image.excluded)labels.unshift('Primary selection needs review');
  return `<figure class="overview-photo ${image.excluded?'overview-excluded':''}"><a href="${safeURL(image.url||imageURL(image,true))}" target="_blank" rel="noopener">${picture(image)}</a><figcaption><span>${labels.map(esc).join(' · ')||'Use not selected'}</span><small>${esc(image.name)}</small>${image.withheld_reasons.length?`<small class="error">${image.withheld_reasons.map(esc).join(' · ')}</small>`:''}<a href="${safeURL(image.folder_url)}" target="_blank" rel="noopener">Folder ↗</a></figcaption></figure>`;
}
function overviewSection(title,images,empty,id=''){
  return `<section class="component-photo-section"${id?` id="overview-${esc(id)}"`:''}><h3>${esc(title)}${images.length?' · '+images.length:''}</h3>${images.length?`<div class="overview-photo-grid">${images.map(overviewImage).join('')}</div>`:`<p class="overview-empty">${esc(empty)}</p>`}</section>`;
}
function renderComponentOverview(payload){
  const p=payload.product,images=payload.images;
  const primary=images.filter(a=>a.id===payload.primary_id),situ=images.filter(a=>payload.in_situ_ids.includes(a.id));
  const byId=new Map(images.map(image=>[image.id,image]));
  const listing=(payload.listing_ids||images.filter(a=>a.selected_uses.includes('listing')&&!a.excluded).map(a=>a.id)).map(id=>byId.get(id)).filter(Boolean);
  const reference=images.find(a=>a.id===payload.source_reference_id);
  const field=f=>`<div class="overview-field ${f.value===null?'omitted':!f.value?.trim()?'missing':''}"><dt>${esc(f.label)}</dt><dd>${esc(specValue(f))}</dd></div>`;
  const sources=[...p.fields,...p.listing_fields].map(f=>`<section><h4>${esc(f.label)}</h4><p>${esc(f.source_value||'Not provided')}</p>${f.qualification?`<p>${esc(f.qualification)}</p>`:''}${f.notes?`<p>${esc(f.notes)}</p>`:''}</section>`).join('');
  return `<div class="overview-title"><div><span class="eyebrow">${esc(p.family)} · ${esc(p.id)}</span><h2>${esc(p.name)}</h2><span class="chip">${esc(specificationListingLabels[p.listing_decision]||specificationListingLabels.pending)}</span></div><div class="specification-links"><a href="#${encodeURIComponent(p.id)}">Review images →</a><a href="#${encodeURIComponent(p.id)}?tab=specs">Edit specifications →</a>${p.folder_url?`<a href="${safeURL(p.folder_url)}" target="_blank" rel="noopener">Dropbox folder ↗</a>`:''}</div></div>
    <nav class="overview-section-links" aria-label="Photo sections"><button class="button" data-overview-section="listing">Listing photos · ${listing.length}</button><button class="button" data-overview-section="in_situ">In-situ photos · ${situ.length}</button><button class="button" data-overview-section="associated">Associated · ${images.length}</button></nav>
    <div class="component-overview-top"><div>${overviewSection('Primary listing photo',primary,payload.primary_conflict?'More than one primary selection needs resolving.':payload.primary_listing?.status==='needs_review'?'The selected primary photo needs review before it can be used.':'No primary listing photo selected.')}${!primary.length&&reference?`<details><summary>Existing catalogue reference (not selected as primary)</summary>${overviewImage(reference)}</details>`:''}</div><section class="overview-specs"><h3>All specifications</h3><dl class="overview-fields">${p.fields.map(field).join('')}</dl><details><summary>Listing copy & source details</summary><dl class="overview-fields">${p.listing_fields.map(field).join('')}</dl>${p.notes?`<p>${esc(p.notes)}</p>`:''}<div class="spec-source-list">${sources}</div></details></section></div>
    ${overviewSection('Listing photos',listing,'No photos are selected for listing for this component.','listing')}
    ${overviewSection('In-situ photos',situ,'No associated photo is currently tagged In situ.','in_situ')}
    ${overviewSection('All associated images',images,'No images are currently associated with this component.','associated')}
    <p class="small muted">Image uses are specific to this component. In situ is an image type; a photo can also be selected for listing and advertising. Excluded images remain visible here with their status.</p>
    <details class="overview-related"><summary>Related candidates · ${payload.related_images.length} (not assigned to this component)</summary>${overviewSection('Related candidates',payload.related_images,'No additional candidates.')}</details>`;
}
async function selectOverviewComponent(pid,section=''){
  const request=++overviewRequest,dialog=$('#component-overview-dialog'),root=$('#component-overview-content');
  root.innerHTML=pid?'<div class="loading">Loading photos and specifications…</div>':'<p>Choose a component to see its photos and specifications. This does not assign the image.</p>';
  if(!pid)return;
  try{
    const payload=await api('/api/component-overview/'+encodeURIComponent(pid));
    if(request!==overviewRequest||!dialog.open)return;
    root.innerHTML=renderComponentOverview(payload);
    if(section)$('#overview-'+section)?.scrollIntoView?.({block:'start'});
  }catch(error){if(request===overviewRequest&&dialog.open)root.innerHTML=`<p class="error" role="alert">${esc(error.message)}</p><button class="button" data-component-overview="${esc(pid)}">Retry</button>`;}
}
function openComponentOverview(pid,assetId,section=''){
  const image=currentImages().find(a=>a.id===assetId),ids=new Set(image?.component_ids||[]);
  if(state.boot.products.some(p=>p.id===state.pid))ids.add(state.pid);
  if(pid)ids.add(pid);
  const products=state.boot.products,choices=products.filter(p=>ids.has(p.id));
  pid=pid||choices[0]?.id||'';
  const options=items=>items.map(p=>`<option value="${esc(p.id)}"${p.id===pid?' selected':''}>${esc(p.name)}</option>`).join('');
  const dialog=$('#component-overview-dialog');
  dialog.innerHTML=`<button class="close" id="component-overview-close" aria-label="Close photos and specifications">×</button><span class="eyebrow">COMPONENT AT A GLANCE</span><label class="overview-component-picker">Component<select id="overview-component" aria-label="Component to preview">${pid?'':'<option value="">Choose a component…</option>'}<optgroup label="This image / current component">${options(choices)}</optgroup><optgroup label="All other components">${options(products.filter(p=>!ids.has(p.id)))}</optgroup></select></label><div id="component-overview-content" aria-live="polite"></div>`;
  if(!dialog.open)dialog.showModal();return selectOverviewComponent(pid,section);
}
function closeComponentOverview(){overviewRequest++;$('#component-overview-dialog').close();}
document.addEventListener('click',e=>{
  const button=e.target.closest('button');
  if(button?.dataset.componentOverview)openComponentOverview(button.dataset.componentOverview,'',button.dataset.overviewSection);
  else if(button?.dataset.overviewSection)$('#overview-'+button.dataset.overviewSection)?.scrollIntoView?.({block:'start'});
  if(button?.dataset.overviewImage)openComponentOverview('',button.dataset.overviewImage);
  if(button?.id==='component-overview-close')closeComponentOverview();
  if(e.target.closest('#component-overview-dialog a[href^="#"]'))closeComponentOverview();
});
document.addEventListener('change',e=>{if(e.target.id==='overview-component')selectOverviewComponent(e.target.value);});
document.addEventListener('cancel',e=>{if(e.target.id==='component-overview-dialog')overviewRequest++;},true);
