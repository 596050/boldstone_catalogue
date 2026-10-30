'use strict';
let coverageTimer,coverageRequest=0;
const familyCollapseKey='boldstone.review.collapsedFamilies.v1';
const collapsedFamilies=(()=>{try{const names=JSON.parse(localStorage.getItem(familyCollapseKey)||'[]');return new Set(Array.isArray(names)?names.filter(name=>typeof name==='string'):[]);}catch{return new Set();}})();
let familyFilterKey='',filteredCollapsedFamilies=new Set();
function visibleCollapsedFamilies(){
  const filter=[$('#search')?.value.trim()||'',$('#family-filter')?.value||'',$('#review-filter')?.value||''].join('\n');
  if(filter!==familyFilterKey){familyFilterKey=filter;filteredCollapsedFamilies.clear();}
  // Reveal matching results without changing the remembered unfiltered view.
  return filter.replaceAll('\n','')?filteredCollapsedFamilies:collapsedFamilies;
}
function setFamiliesCollapsed(names,collapsed,focusFamily){
  const visible=visibleCollapsedFamilies();
  for(const name of names){for(const set of [collapsedFamilies,visible]){if(collapsed)set.add(name);else set.delete(name);}}
  try{localStorage.setItem(familyCollapseKey,JSON.stringify([...collapsedFamilies]));}catch{}
  const list=$('#product-list'),scroll=list.scrollTop;
  renderList();list.scrollTop=scroll;
  if(focusFamily)$$('[data-family-toggle]',list).find(button=>button.dataset.familyToggle===focusFamily)?.focus();
}
const familyImagesHash=family=>'library?family='+encodeURIComponent(family);
const familyHash=family=>'family='+encodeURIComponent(family);
const coverageProduct=pid=>state.boot.coverage?.products[pid];
function navigateFamily(family){
  if(!dirtyOK())return;state.dirty.clear();
  const hash=familyHash(family);
  if(location.hash.slice(1)===hash)load('__family__',{family});else location.hash=hash;
}
function scheduleCoverageRefresh(){
  clearTimeout(coverageTimer);
  const request=++coverageRequest;
  coverageTimer=setTimeout(async()=>{
    try{
      const result=await api('/api/coverage');if(request!==coverageRequest)return;
      state.boot.coverage=result;renderList();
      if(state.pid==='__family__')renderFamily();else renderProductCoverage();
    }catch(error){if($('#product-coverage'))$('#product-coverage').textContent='Coverage could not refresh. Reload to check the latest image gaps.';}
  },200);
}
function coverageBadge(product){
  if(!product)return '';
  const primary=product.primary_listing?.status;
  const label=({set:'Primary set',missing:'Primary missing',needs_review:'Primary needs review'})[primary]||'Primary not checked';
  return `<span class="coverage-badges">${product.excluded?'<span class="coverage-badge">Listing excluded</span>':`<span class="coverage-badge ${product.in_situ.missing?'needs-attention':'complete'}">${product.in_situ.count}/${product.in_situ.target||2} in situ${product.in_situ.missing?' · need '+product.in_situ.missing:''}</span>`}<span class="coverage-badge primary-coverage ${primary==='set'?'complete':'needs-attention'}" title="Primary listing photo: ${esc(label.replace('Primary ','').toLowerCase())}">${label}</span></span>`;
}
function groupedProductList(products){
  const collapsed=visibleCollapsedFamilies();
  const search=($('#search')?.value||'').toLowerCase(),filter=$('#family-filter')?.value||'';
  const imageOnly=($('#review-filter')?.value?[]:state.boot.family_inventory?.image_only_folders||[]);
  const extras=[...imageOnly].filter(f=>(!filter||f.name===filter)&&(!search||f.name.toLowerCase().includes(search)));
  return [...new Set([...products.map(p=>p.family),...extras.map(f=>f.name)])].sort((a,b)=>a.localeCompare(b)).map(name=>{
    const family=state.boot.coverage?.families[name],members=products.filter(p=>p.family===name);
    const closed=collapsed.has(name),membersId='family-members-'+encodeURIComponent(name);
    const gaps=family?[family.in_situ_gaps?`${family.in_situ_gaps} in-situ gaps`:'In situ covered',family.white_entries_missing?`${family.white_entries_missing} White entries missing`:family.white_titles_missing?`${family.white_titles_missing} White titles to check`:''].filter(Boolean).join(' · '):'Images only - no component records';
    return `<section class="family-group"><div class="family-group-head"><button class="family-toggle" data-family-toggle="${esc(name)}" aria-expanded="${!closed}" aria-controls="${esc(membersId)}" aria-label="${closed?'Expand':'Collapse'} ${esc(name)}" title="${closed?'Expand':'Collapse'} ${esc(name)}"></button><button class="family-heading ${state.pid==='__family__'&&state.family===name?'active':''}" data-family="${esc(name)}" aria-label="Open ${esc(name)} family overview"><span>${esc(name)} <small>${members.length}${family&&members.length!==family.option_count?' / '+family.option_count:''}</small></span><small>${esc(gaps)}</small></button></div><div class="family-members" id="${esc(membersId)}"${closed?' hidden':''}><a class="family-images-link" href="#${familyImagesHash(name)}">All family images · pairs & groups →</a>${members.map(p=>{const r=data('product',p.id),coverage=coverageProduct(p.id);return `<button class="product-link ${p.id===state.pid?'active':''}" data-product="${p.id}"><span><strong>${esc(p.name)}</strong><small>${p.image_count} retained associations</small>${coverageBadge(coverage)}</span><i class="status-dot ${esc(r.decision==='exclude'?'exclude':r.status||'')}"></i></button>`;}).join('')}</div></section>`;
  }).join('')||'<p class="small muted">No sculptures match these filters.</p>';
}
function renderProductCoverage(){
  const root=$('#product-coverage'),p=coverageProduct(state.pid);if(!root||!p)return;
  const family=state.boot.coverage.families[p.family];
  const component=family.components.find(c=>c.product_ids.includes(p.id));
  root.innerHTML=`<div><strong>Image checklist</strong>${coverageBadge(p)}<span>${p.in_situ.listing_count} in situ selected for listing</span><a href="#${esc(p.id)}?type=in_situ">Review in-situ images →</a></div><div><span>${component?whiteStatus(component.status):'White component identity needs review'}${p.white_evidence&&p.individual.count===0?' · individual White photograph missing':''}</span><button class="text-button" data-family="${esc(p.family)}">${esc(p.family)} family overview →</button><a href="#${familyImagesHash(p.family)}">All ${esc(p.family)} family images →</a></div>`;
}
function whiteStatus(status){
  return ({white_entry_present:'Plain White entry present',white_title_missing:'White folder found · title omits “White”',white_entry_not_found:'Plain White entry not found',white_entry_excluded:'White entry excluded from listing'})[status]||'White finish needs review';
}
function familyProductLink(pid,label){return `<a href="#${esc(pid)}">${esc(label||coverageProduct(pid)?.name||pid)}</a>`;}
function renderFamily(){
  const family=state.boot.coverage?.families[state.family];
  const imageOnly=state.boot.family_inventory?.image_only_folders.find(f=>f.name===state.family);
  if(!family&&imageOnly){
    $('#main').innerHTML=`<div class="hero"><div class="hero-copy"><span class="eyebrow">DROPBOX IMAGE COLLECTION</span><h1>${esc(imageOnly.name)}</h1><p>This Dropbox folder is in the image library. No individual component records have been defined for it, so it is outside the families-with-components count.</p><a class="button green" href="#${familyImagesHash(imageOnly.name)}">Browse all images →</a> <a class="button" href="${safeURL(imageOnly.url)}" target="_blank" rel="noopener">Dropbox folder ↗</a></div></div>`;return;
  }
  if(!family){$('#main').innerHTML='<div class="empty-state">This family is not in the current catalogue.</div>';return;}
  const products=family.product_ids.map(coverageProduct).sort((a,b)=>Number(a.excluded)-Number(b.excluded)||b.in_situ.missing-a.in_situ.missing||a.name.localeCompare(b.name));
  $('#main').innerHTML=`<div class="breadcrumb"><span>Wall sculptures / Family overview</span><button class="button subtle" id="refresh-family">Refresh indicators</button></div><div class="hero"><div class="hero-copy"><span class="eyebrow">FAMILY OVERVIEW</span><h1>${esc(family.name)}</h1><p>Review each component and finish. The image target is at least two in-situ images per individual option.</p><a class="button green family-gallery-link" href="#${familyImagesHash(family.name)}">All family images - including pairs & groups →</a></div></div><div class="stats-strip family-stats"><div><strong>${family.option_count}</strong><span>Individual options</span></div><div><strong>${family.component_count}</strong><span>Component records</span></div><div><strong>${family.design_group_count}</strong><span>Working design groups</span></div><div><strong>${family.in_situ_gaps}</strong><span>Options below two in situ</span></div><div><strong>${family.white_entries_missing}</strong><span>White entries not available</span></div><div><strong>${family.white_titles_missing}</strong><span>White titles to check</span></div><div><strong>${family.unique_image_count}</strong><span>Unique retained images</span></div></div><section class="family-section"><h2>In-situ image coverage</h2><p>${family.in_situ_ready} options meet the two-image target; ${family.in_situ_images_missing} further images are needed across ${family.in_situ_gaps} options. Excluded listings are outside the target.</p><p class="small muted">Counts use non-excluded Dropbox images tagged In situ and assigned to that sculpture. Related candidates do not count until assigned or selected for listing. Group scenes can count; image tags do not certify a photographed installation.</p><div class="family-table-wrap"><table class="family-table"><thead><tr><th>Sculpture / finish</th><th>In situ</th><th>For listing</th><th>Action</th></tr></thead><tbody>${products.map(p=>`<tr class="${p.excluded?'muted':''}"><th>${familyProductLink(p.id)}${p.excluded?'<small>Excluded from listing</small>':''}</th><td>${coverageBadge(p)}</td><td>${p.in_situ.listing_count}</td><td><button class="text-button" data-component-overview="${esc(p.id)}">Photos & specs</button><br><a href="#${esc(p.id)}?type=in_situ">Review images →</a>${p.folder_url?`<br><a href="${safeURL(p.folder_url)}" target="_blank" rel="noopener">Folder ↗</a>`:''}</td></tr>`).join('')}</tbody></table></div></section><section class="family-section"><h2>Plain White components</h2><p>Checks follow existing component records and saved design-equivalence groups. Separate finishes and product records are retained. Mixed colours and marbling do not satisfy a plain White entry.</p><p class="small muted">A White folder with an unnamed finish is flagged for a title check. “Not found” means no supporting entry was found in these records; it does not establish that the sculpture cannot be made in White.</p><div class="family-table-wrap"><table class="family-table"><thead><tr><th>Component</th><th>White entry</th><th>Individual photograph</th><th>Review</th></tr></thead><tbody>${family.components.map(c=>`<tr><th>${esc(c.name)}${c.retained_component_ids.length>1?`<small>${c.retained_component_ids.length} linked component records · existing design equivalence</small>`:''}</th><td><span class="coverage-badge ${c.status==='white_entry_present'?'complete':'needs-attention'}">${whiteStatus(c.status)}</span></td><td>${c.white_product_ids.length?c.individual_image_count?`${c.individual_image_count} available`:'Missing — check product images':'White entry needed first'}</td><td>${(c.white_product_ids.length?c.white_product_ids:c.product_ids).map(pid=>familyProductLink(pid)).join('<br>')}</td></tr>`).join('')||'<tr><td colspan="4">Component identities are not defined for these options.</td></tr>'}</tbody></table></div>${family.unresolved_component_ids.length?`<p class="coverage-note">${family.unresolved_component_ids.length} option(s) lack a defined component identity, so White completeness is not inferred: ${family.unresolved_component_ids.map(pid=>familyProductLink(pid)).join(', ')}.</p>`:''}</section><p class="small muted coverage-basis">${esc(state.boot.coverage.basis)}</p>`;
}
function updateScopeSummary(){
  const root=$('#image-scope-summary');if(!root||state.pid==='__library__')return;
  const images=currentImages(),removed=images.filter(a=>a.association?.tier==='removed').length;
  const related=images.filter(a=>a.association?.tier==='related'&&!activeImageUses(data('image',state.pid,a.id)).includes('listing'));
  const assigned=images.length-related.length-removed;
  root.innerHTML=`<strong>${images.length-removed} retained associations</strong><span>${assigned} in This sculpture</span><button class="text-button" data-image-scope="related">${related.length} related candidates${related.length?' ('+[...new Set(related.map(a=>a.source))].map(esc).join(', ')+')':''} →</button>${removed?`<button class="text-button" data-image-scope="removed">${removed} removed from this title →</button>`:''}<button class="text-button" data-image-scope="all">Show all retained images →</button><small>Category counts and the gallery follow the filters below. Removed images stay in their own scope.</small>`;
}
document.addEventListener('click',event=>{
  const button=event.target.closest('button');if(!button)return;
  if(button.dataset.familyToggle){setFamiliesCollapsed([button.dataset.familyToggle],button.getAttribute('aria-expanded')==='true',button.dataset.familyToggle);return;}
  if(button.id==='collapse-families'||button.id==='expand-families'){if(state.boot)setFamiliesCollapsed(state.boot.families,button.id==='collapse-families');return;}
  if(button.dataset.family){navigateFamily(button.dataset.family);return;}
  if(button.id==='refresh-family'){load('__family__',{family:state.family});return;}
  if(button.dataset.imageScope){state.scope=button.dataset.imageScope;state.role='';state.use='';state.source='';state.imageSearch='';state.limit=24;state.selected.clear();renderImages();}
});
