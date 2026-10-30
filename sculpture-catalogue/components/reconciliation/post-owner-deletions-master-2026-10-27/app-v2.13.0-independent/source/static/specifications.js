'use strict';
let specificationTimer,specificationRefreshBusy=false;
const specificationListingLabels={include:'Included in listing',exclude:'Excluded from listing',pending:'Listing not decided'};
function initSpecificationFilters(filters={}){
  state.specSearch=filters.specSearch||'';state.specFamily=filters.specFamily||'';
  state.specListing=['include','exclude','pending'].includes(filters.specListing)?filters.specListing:'';
  state.specDetails=['missing','omitted','unreviewed'].includes(filters.specDetails)?filters.specDetails:'';
}
function filteredSpecifications(){
  const terms=(state.specSearch||'').trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
  return (state.specifications?.products||[]).filter(p=>{
    const text=[p.name,p.original_name,p.id,p.component_id,p.family,...p.fields.map(f=>f.value||'')].join(' ').toLocaleLowerCase();
    return (!state.specFamily||p.family===state.specFamily)&&(!state.specListing||p.listing_decision===state.specListing)&&
      (!state.specDetails||(state.specDetails==='missing'?p.missing_count>0:state.specDetails==='omitted'?p.omitted_count>0:p.fields.some(f=>f.decision==='pending')))&&terms.every(term=>text.includes(term));
  });
}
function specificationRoute(){
  const params=new URLSearchParams();
  for(const [key,value] of [['q',state.specSearch],['family',state.specFamily],['listing',state.specListing],['details',state.specDetails]])if(value)params.set(key,value);
  state.routeHash='#specifications'+(params.size?'?'+params:'');history.replaceState(null,'',state.routeHash);
}
function specValue(field){return field.value===null?'Omitted from listing':field.value?.trim()?field.value:'Not provided';}
function componentPhotoPreviews(product){
  const photos=product.photos;if(!photos)return '';
  const section=(key,title,empty)=>{
    const group=photos[key],images=group.images;
    return `<section class="component-preview-section" aria-label="${esc(title)}"><div class="component-preview-heading"><h4>${esc(title)} <span>${group.count}</span></h4>${group.count?`<button class="text-button" data-component-overview="${esc(product.id)}" data-overview-section="${key}">View all ${group.count} →</button>`:''}</div>${images.length?`<div class="component-preview-strip">${images.map(image=>`<button class="component-preview-photo ${image.id===photos.primary_listing.image_id?'is-primary':''}" data-component-overview="${esc(product.id)}" data-overview-section="${key}" title="${esc(image.name)}${image.withheld_reasons?.length?' - needs review':''}" aria-label="View ${esc(title.toLowerCase())} for ${esc(product.name)}: ${esc(image.name)}">${picture(image)}${image.id===photos.primary_listing.image_id?'<span class="preview-photo-label">Primary</span>':image.withheld_reasons?.length?'<span class="preview-photo-label needs-attention">Needs review</span>':''}</button>`).join('')}</div>${group.count>images.length?`<p class="component-preview-note">Showing ${images.length} of ${group.count}</p>`:''}`:`<p class="component-preview-empty">${empty} <a href="#${encodeURIComponent(product.id)}${key==='in_situ'?'?type=in_situ':''}">Review images →</a></p>`}</section>`;
  };
  return `<div class="component-photo-previews">${section('listing','Listing photos','No photos selected for listing.')}${section('in_situ','In-situ photos','No qualifying in-situ photos assigned.')}</div>`;
}
function specificationCard(product){
  const evidenceID='spec-source-'+encodeURIComponent(product.id);
  const field=f=>`<div class="overview-field ${f.value===null?'omitted':!f.value?.trim()?'missing':''}"><dt>${esc(f.label)}</dt><dd>${esc(specValue(f))}</dd></div>`;
  return `<article class="component-specification" data-spec-product="${esc(product.id)}" aria-labelledby="spec-title-${esc(product.id)}">
    <header class="component-spec-heading"><div><span class="eyebrow">${product.number} · ${esc(product.id)}</span><h3 id="spec-title-${esc(product.id)}">${esc(product.name)}</h3><span class="chip ${product.listing_decision==='exclude'?'bad':product.listing_decision==='include'?'good':''}">${esc(specificationListingLabels[product.listing_decision]||specificationListingLabels.pending)}</span></div><div class="specification-links"><button class="button green" data-component-overview="${esc(product.id)}">Photos & specs</button><a class="button" href="#${encodeURIComponent(product.id)}?tab=specs">Review specifications →</a><a href="#${encodeURIComponent(product.id)}">Images</a>${product.folder_url?`<a href="${safeURL(product.folder_url)}" target="_blank" rel="noopener">Dropbox folder ↗</a>`:''}</div></header>
    ${product.photos?`<div class="component-photo-readiness">${coverageBadge({...product.photos,excluded:product.listing_decision==='exclude'})}</div>`:''}
    ${componentPhotoPreviews(product)}
    <dl class="overview-fields">${product.fields.map(field).join('')||'<div class="overview-field missing"><dt>Specifications</dt><dd>No specification fields recorded</dd></div>'}</dl>
    <details class="specification-evidence" id="${evidenceID}"><summary>Listing copy, source details & notes</summary><dl class="overview-fields">${product.listing_fields.map(field).join('')}</dl>${product.notes?`<p class="spec-private-note"><strong>Private review notes</strong><br>${esc(product.notes)}</p>`:''}<div class="spec-source-list">${[...product.fields,...product.listing_fields].map(f=>`<section><h4>${esc(f.label)}</h4><p><strong>Review choice:</strong> ${esc(({pending:'Not reviewed',keep:'Keep source value',edit:'Use edited value',exclude:'Omitted'})[f.decision]||f.decision)}${f.version?' · Saved revision '+f.version:''}</p><p><strong>Original source:</strong> ${esc(f.source_value||'Not provided')}</p>${f.qualification?`<p>${esc(f.qualification)}</p>`:''}${f.basis?`<p>${esc(f.basis)}</p>`:''}${f.notes?`<p><strong>Feedback:</strong> ${esc(f.notes)}</p>`:''}${f.evidence?`<p><strong>Evidence:</strong> ${esc(f.evidence)}</p>`:''}</section>`).join('')}</div></details>
  </article>`;
}
function specificationSummary(){
  const s=state.specifications;
  return `<div><strong>${s.totals.products}</strong><span>Components and finishes</span></div><div><strong>${s.families.length}</strong><span>Families with components</span></div>${s.family_inventory?.dropbox_folder_count!=null?`<div><strong>${s.family_inventory.dropbox_folder_count}</strong><span>Dropbox family folders</span></div>`:''}<div><strong>${s.totals.fields}</strong><span>Specification items</span></div><div><strong>${s.totals.missing}</strong><span>Missing values</span></div><div><strong>${s.totals.omitted}</strong><span>Omitted from listing</span></div>`;
}
function specificationFamilyInventory(){
  const inventory=state.specifications.family_inventory;
  if(inventory?.dropbox_folder_count==null)return '';
  return `<details class="family-inventory" id="spec-family-inventory"><summary>Dropbox folders & catalogue families - ${inventory.image_only_folders.length} folders without component records</summary><p>The family count above covers named component records. Dropbox folders can have a different catalogue name or contain group photographs without individual records. Every current top-level folder is listed here.</p><table><thead><tr><th>Dropbox folder</th><th>Catalogue family / status</th><th>Components</th><th>Images</th></tr></thead><tbody>${inventory.folders.map(f=>`<tr><th><a href="${safeURL(f.url)}" target="_blank" rel="noopener">${esc(f.name)} ↗</a></th><td>${f.registered_families.map(esc).join(', ')||'Images only - no component records'}</td><td>${f.product_ids.length}</td><td><a href="#library?family=${encodeURIComponent(f.name)}">Browse images →</a></td></tr>`).join('')}</tbody></table></details>`;
}
function renderAllSpecifications(){
  const s=state.specifications;
  $('#main').innerHTML=`<div class="breadcrumb"><span>Collection / Specifications</span><span>All components on one page</span></div><div class="hero"><div class="hero-copy"><span class="eyebrow">THE COMPLETE SPECIFICATION REGISTER</span><h1>All component specifications</h1><p>Every sculpture and finish, grouped by family. These are your current listing values, including saved edits. Open a component to review or change its details.</p></div><button class="button subtle" id="spec-refresh">Refresh details</button></div><div class="stats-strip spec-overview-stats" id="spec-overview-stats">${specificationSummary()}</div>${specificationFamilyInventory()}<div class="spec-overview-controls" role="search" aria-label="Find component specifications"><label>Search components or details<input type="search" id="spec-search" aria-label="Search component specifications" placeholder="Name, ID, material or size…"></label><label>Family<select id="spec-family" aria-label="Specification family"><option value="">All families</option>${s.families.map(f=>`<option>${esc(f)}</option>`).join('')}</select></label><label>Listing choice<select id="spec-listing" aria-label="Specification listing choice"><option value="">All listing choices</option><option value="include">Included in listing</option><option value="pending">Not decided</option><option value="exclude">Excluded from listing</option></select></label><label>Details<select id="spec-details" aria-label="Specification detail filter"><option value="">All details</option><option value="missing">Missing values</option><option value="omitted">Omitted fields</option><option value="unreviewed">Unreviewed fields</option></select></label><button class="text-button" id="spec-clear">Clear filters</button></div><div class="spec-overview-status"><span id="spec-result-count" role="status"></span><span id="spec-checked" role="status"></span></div><div id="specification-results"></div>`;
  for(const [id,value] of [['spec-search',state.specSearch],['spec-family',state.specFamily],['spec-listing',state.specListing],['spec-details',state.specDetails]])$('#'+id).value=value||'';
  renderSpecificationResults();renderSpecificationChecked();
}
function renderSpecificationResults(){
  const products=filteredSpecifications(),open=new Set($$('.specification-evidence[open]').map(el=>el.id));
  $('#spec-result-count').textContent=products.length+' of '+state.specifications.totals.products+' components shown';
  $('#specification-results').innerHTML=[...new Set(products.map(p=>p.family))].map(family=>`<section class="specification-family"><div class="specification-family-heading"><h2>${esc(family)}</h2><span>${products.filter(p=>p.family===family).length} ${products.filter(p=>p.family===family).length===1?'component':'components'}</span></div>${products.filter(p=>p.family===family).map(specificationCard).join('')}</section>`).join('')||'<div class="empty-state">No components match these filters. Try another name or clear the filters.</div>';
  for(const id of open){const el=document.getElementById(id);if(el)el.open=true;}
}
function renderSpecificationChecked(message=''){
  const el=$('#spec-checked');if(el)el.textContent=message||'Checked '+new Date(state.specifications.checked_at).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})+' · Auto-checks every 15 seconds';
}
async function refreshAllSpecifications(manual=false){
  if(state.pid!=='__specifications__'||specificationRefreshBusy||state.loading||(!manual&&(document.hidden||!syncCanRefresh())))return;
  const request=state.request,writeEpoch=state.writeEpoch,button=$('#spec-refresh');specificationRefreshBusy=true;if(button)button.disabled=true;
  try{
    const payload=await api('/api/specifications');
    if(state.pid!=='__specifications__'||request!==state.request||writeEpoch!==state.writeEpoch)return;
    const changed=payload.revision!==state.specifications.revision;state.specifications=payload;
    if(changed){
      const pageScroll=window.scrollY,mainScroll=$('#main').scrollTop;
      $('#spec-overview-stats').innerHTML=specificationSummary();renderSpecificationResults();
      const inventory=$('#spec-family-inventory');
      if(inventory){const open=inventory.open;inventory.outerHTML=specificationFamilyInventory();const replacement=$('#spec-family-inventory');if(replacement)replacement.open=open;}
      const select=$('#spec-family');select.innerHTML='<option value="">All families</option>'+payload.families.map(f=>`<option>${esc(f)}</option>`).join('');select.value=state.specFamily;
      $('#main').scrollTop=mainScroll;window.scrollTo(0,pageScroll);
    }
    renderSpecificationChecked();if(manual)toast('Specification details are up to date');
  }catch(error){if(state.pid==='__specifications__'&&request===state.request){renderSpecificationChecked('Could not refresh - showing the last loaded details');if(manual)toast(error.message,true);}}
  finally{specificationRefreshBusy=false;if(button)button.disabled=false;}
}
function startSpecificationRefresh(){clearInterval(specificationTimer);specificationTimer=setInterval(()=>refreshAllSpecifications(),15000);}
document.addEventListener('input',e=>{if(e.target.id==='spec-search'){state.specSearch=e.target.value;renderSpecificationResults();specificationRoute();}});
document.addEventListener('change',e=>{const field={'spec-family':'specFamily','spec-listing':'specListing','spec-details':'specDetails'}[e.target.id];if(field){state[field]=e.target.value;renderSpecificationResults();specificationRoute();}});
document.addEventListener('click',e=>{
  const button=e.target.closest('button');if(!button)return;
  if(button.id==='spec-refresh')refreshAllSpecifications(true);
  if(button.id==='spec-clear'){initSpecificationFilters();renderAllSpecifications();specificationRoute();}
});
