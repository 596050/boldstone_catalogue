(() => {
  'use strict';
  const $=id=>document.getElementById(id), M=PhotoReview;
  const DATA=JSON.parse($('review-data').textContent), ROWS=new Map(DATA.records.map(r=>[r.id,r]));
  const PRODUCTS=Object.fromEntries(DATA.products.map(p=>[p.id,p])), PRODUCT_IDS=new Set(Object.keys(PRODUCTS));
  const STORAGE_KEY='boldstone.wall-photo-decisions.v1';
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const safeUrl=url=>{try{const u=new URL(url);return ['http:','https:'].includes(u.protocol)?u.href:'#';}catch{return '#';}};
  const link=(url,label)=>`<a href="${esc(safeUrl(url))}" target="_blank" rel="noopener noreferrer">${esc(label)} ↗</a>`;
  const MB=n=>n>=1048576?(n/1048576).toFixed(2)+' MB':(n/1024).toFixed(1)+' KB';
  const previewUrl=url=>{const u=new URL(url);if(u.hostname==='images.squarespace-cdn.com')u.searchParams.set('format','750w');return u.href;};
  let decisions={}, storageOK=true, page=1, visible=[], toastTimer, filterTimer, componentDraft=null, importDraft=null;
  let filters={group:'attention',product:'',review:'all',tag:'',search:''};
  function loadChoices(raw){
    if(!raw||typeof raw!=='object'||Array.isArray(raw))return;
    for(const [id,value] of Object.entries(raw)){if(!ROWS.has(id))continue;const d=M.clean(value,PRODUCT_IDS);if(!decisions[id]||Date.parse(d.updated_at||0)>=Date.parse(decisions[id].updated_at||0))decisions[id]=d;}
  }
  try{loadChoices(JSON.parse($('saved-decisions').textContent||'{}'));}catch{}
  try{const saved=localStorage.getItem(STORAGE_KEY);if(saved)loadChoices(JSON.parse(saved));}catch{storageFailure();}
  function storageFailure(){storageOK=false;$('storage-warning').hidden=false;$('storage-warning').textContent='Automatic browser saving is unavailable. Your choices still work in this open page. Use “Save reviewed page” or “Export decisions” before closing it.';$('save-status').textContent='Save a reviewed copy before closing';}
  function dFor(id){return M.clean(decisions[id],PRODUCT_IDS);}
  function persist(){
    try{localStorage.setItem(STORAGE_KEY,JSON.stringify(decisions));storageOK=true;$('storage-warning').hidden=true;$('save-status').textContent='● Saved in this browser · '+new Date().toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'});}catch{storageFailure();}
    updateProgress();
  }
  function toast(text){$('toast').textContent=text;$('toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').hidden=true,4500);}
  function updateProgress(){const complete=DATA.records.filter(r=>M.complete(r,dFor(r.id))).length;const edited=DATA.records.filter(r=>M.edited(dFor(r.id))).length;const pending=DATA.records.filter(r=>dFor(r.id).action==='check'||M.detailsNeeded(r,dFor(r.id)).length).length;$('decision-count').textContent=`${complete} / ${DATA.records.length}`;$('progress').value=complete;$('progress-caption').textContent=`${edited} with saved feedback · ${pending} need checking or details`;}
  function locationMarkup(row){
    if(!row.locations.length)return `<details class="locations"><summary>No current Dropbox location recorded</summary><p>${row.group==='missing'?'The recorded original was absent during the audit.':'No supported Dropbox match is recorded.'}</p>${row.historical_dropbox_ids.map(id=>`<small class="path">${esc(id)}</small>`).join('')}${row.local_backup_verified?'<p>Earlier local backup verified. Preview here uses the website URL.</p>':''}</details>`;
    return `<details class="locations"><summary>${row.locations.length} recorded Dropbox location${row.locations.length===1?'':'s'}</summary>${row.locations.map(m=>`<div class="location-entry"><b>${m.in_wall?'Wall Sculptures':'Elsewhere in BOLDSTONE MASTER'}</b><span class="path">${esc(m.path)}</span>${link(m.image_url,'Image')} · ${link(m.folder_url,'Folder')}<br><small>${MB(m.bytes)} · ${esc(m.id)}</small></div>`).join('')}</details>`;
  }
  function appMarkup(row){
    if(!row.app_associations.length)return '';
    return `<details class="recorded"><summary>Recorded app associations (${row.app_associations.length})</summary><p>Source evidence, not the choices made on this page.</p>${row.app_associations.map(a=>`<div class="app-entry">${link(PRODUCTS[a.id]?.app_url,a.title)}<br><small>${esc(a.scopes.join(', '))}${a.uses.length?' · '+esc(a.uses.join(' + ')):''}${a.primary?' · Primary selected':''}</small></div>`).join('')}</details>`;
  }
  function card(row){
    const d=dFor(row.id),inactive=['exclude','duplicate'].includes(d.action), needs=M.detailsNeeded(row,d),date=d.updated_at?new Date(d.updated_at).toLocaleString():'';
    return `<article class="photo-card ${d.action?'has-decision':''}" data-id="${row.id}">
      <div class="card-image"><button class="image-zoom" data-action="zoom" aria-label="Enlarge photograph ${row.number}"><img class="preview" src="${esc(previewUrl(row.url))}" alt="${esc(row.title+' - '+row.filename)}" loading="lazy" decoding="async" referrerpolicy="no-referrer"></button><div class="preview-failed" hidden>Preview could not load.<br>Open the Squarespace image link below to check it.</div><div class="image-topline"><span class="badge number">${String(row.number).padStart(3,'0')} / 444</span><span class="badge">SQUARESPACE</span></div></div>
      <div class="card-body"><span class="location-status ${row.group}">${M.groups[row.group]}</span><h3>${esc(row.title)}</h3><div class="filename">${esc(row.filename)}</div>
      ${row.dimensions?`<div class="dimensions">${row.dimensions.width} × ${row.dimensions.height} px · ${MB(row.dimensions.bytes)}<br><small>Website original checked in earlier audit</small></div>`:''}
      <div class="source-links">${link(row.url,'Website image')}${row.old_products.map(p=>link(p.url,'Old listing')).join(' ')}</div>
      ${locationMarkup(row)}${appMarkup(row)}
      <div class="decision-controls"><label class="field">What should happen?<select data-field="action" aria-label="Decision for photograph ${row.number}">${Object.entries(M.actions).map(([value,label])=>`<option value="${value}" ${value===d.action?'selected':''} ${!row.locations.length&&['keep_current','move_to_wall'].includes(value)?'disabled':''}>${esc(label)}</option>`).join('')}</select></label>
      <div><span class="label">Purpose · select more than one</span><div class="pills">${Object.entries(M.uses).map(([value,label])=>`<button class="pill" data-action="purpose" data-value="${value}" aria-pressed="${d.uses.includes(value)}" ${inactive?'disabled':''}>${label}</button>`).join('')}</div></div>
      <details class="types-menu"><summary>Image types <small>${d.types.length?d.types.length+' selected':'Choose types'}</small></summary><div class="type-options">${Object.entries(M.types).map(([value,label])=>`<label><input type="checkbox" data-type="${value}" ${d.types.includes(value)?'checked':''}>${label}</label>`).join('')}</div></details>
      <div><button class="component-button" data-action="components">Component sculptures · ${d.components.length?d.components.length+' chosen':'choose…'}</button><div class="component-chips">${d.components.map(id=>`<span>${esc(PRODUCTS[id].title)}${d.primary_for.includes(id)?' · Primary':''}</span>`).join('')}</div></div>
      ${['copy_to_wall','move_to_wall'].includes(d.action)?`<label class="field">Destination folder or correction (optional if components chosen)<input data-field="destination" value="${esc(d.destination)}" placeholder="Dropbox folder URL or exact folder name…"></label>`:''}
      ${d.action==='duplicate'?`<label class="field">Photograph to keep<input data-field="replacement" value="${esc(d.replacement)}" placeholder="Image URL, filename or photo number…"></label>`:''}
      <label class="field">Notes / corrections<textarea data-field="notes" rows="2" placeholder="Finish, identity, crop, folder or other feedback…">${esc(d.notes)}</textarea></label>
      <p class="incomplete-note">${needs.map(esc).join('<br>')}</p><div class="card-footer"><span>${d.action?(M.complete(row,d)?'✓ Review complete':d.action==='check'?'Further checking requested':'Decision needs details'):'Not decided'}${date?`<br>${esc(date)}`:''}</span><button data-action="clear">Clear choices</button></div></div></div></article>`;
  }
  function bindImages(scope){for(const img of scope.querySelectorAll('img.preview'))img.addEventListener('error',()=>{const parent=img.closest('.card-image');parent.querySelector('.image-zoom').hidden=true;parent.querySelector('.preview-failed').hidden=false;});}
  function refreshCard(id){const old=document.querySelector(`article[data-id="${id}"]`);if(!old)return;const open=Array.from(old.querySelectorAll('details')).map(e=>e.open);const top=old.getBoundingClientRect().top;old.outerHTML=card(ROWS.get(id));const fresh=document.querySelector(`article[data-id="${id}"]`);Array.from(fresh.querySelectorAll('details')).forEach((e,i)=>e.open=!!open[i]);bindImages(fresh);window.scrollBy(0,fresh.getBoundingClientRect().top-top);}
  function render(){
    visible=DATA.records.filter(r=>M.matches(r,dFor(r.id),filters,PRODUCTS));
    const size=$('page-size').value==='all'?Math.max(1,visible.length):Number($('page-size').value);const pages=Math.max(1,Math.ceil(visible.length/size));page=Math.min(page,pages);const start=(page-1)*size;
    $('gallery').innerHTML=visible.slice(start,start+size).map(card).join('');bindImages($('gallery'));
    $('result-count').textContent=visible.length?`${start+1}–${Math.min(start+size,visible.length)} of ${visible.length} photographs · ${DATA.records.length} in this review`:'0 photographs';
    $('empty').hidden=!!visible.length;
    $('pagination').innerHTML=visible.length?`<button data-page="${page-1}" ${page===1?'disabled':''}>← Previous</button><span>Page ${page} of ${pages}</span><button data-page="${page+1}" ${page===pages?'disabled':''}>Next →</button>`:'';
    for(const b of $('groups').querySelectorAll('button'))b.setAttribute('aria-pressed',String(b.dataset.group===filters.group));
  }
  function update(id,patch,refresh=true){let d=dFor(id);decisions[id]=M.clean({...d,...patch,updated_at:new Date().toISOString()},PRODUCT_IDS);persist();if(refresh)refreshCard(id);else{const el=document.querySelector(`article[data-id="${id}"] .incomplete-note`);if(el)el.textContent=M.detailsNeeded(ROWS.get(id),decisions[id]).join(' ');}}
  function resetFilters(){filters={group:'attention',product:'',review:'all',tag:'',search:''};$('search').value='';$('product-filter').value='';$('review-filter').value='all';$('tag-filter').value='';page=1;render();}
  const tabs=[['attention','Needs attention',171],['missing','Original missing',55],['unmatched','No match',35],['elsewhere','Other folders',81],['wall','Wall folders',273],['all','All photographs',444]];
  $('groups').innerHTML=tabs.map(([key,label,n])=>`<button data-group="${key}" aria-pressed="${key===filters.group}">${label}<span class="count">${n}</span></button>`).join('');
  const oldProducts=[...new Map(DATA.records.flatMap(r=>r.old_products).map(p=>[p.id,p])).values()].sort((a,b)=>a.title.localeCompare(b.title));
  $('product-filter').innerHTML='<option value="">All old wall products</option>';
  for(const p of oldProducts){const o=document.createElement('option');o.value=p.id;o.textContent=p.title;$('product-filter').append(o);}
  $('audit-date').textContent='Dropbox presence checked '+new Date(DATA.audit_utc).toLocaleString()+'. App associations reflect catalogue event '+DATA.source_event+'. This is an audit snapshot, not a live sync.';
  $('groups').addEventListener('click',e=>{const b=e.target.closest('[data-group]');if(!b)return;filters.group=b.dataset.group;page=1;render();});
  for(const [id,key] of [['product-filter','product'],['review-filter','review'],['tag-filter','tag']])$(id).addEventListener('change',()=>{filters[key]=$(id).value;page=1;render();});
  $('search').addEventListener('input',()=>{clearTimeout(filterTimer);filterTimer=setTimeout(()=>{filters.search=$('search').value;page=1;render();},180);});
  $('page-size').addEventListener('change',()=>{page=1;render();});$('reset-filters').addEventListener('click',resetFilters);$('empty-reset').addEventListener('click',resetFilters);
  $('pagination').addEventListener('click',e=>{const b=e.target.closest('[data-page]');if(!b||b.disabled)return;page=Number(b.dataset.page);render();document.querySelector('.results-bar').scrollIntoView({block:'start'});});
  $('gallery').addEventListener('click',e=>{
    const b=e.target.closest('[data-action]'),article=e.target.closest('article[data-id]');if(!b||!article)return;const id=article.dataset.id,d=dFor(id),row=ROWS.get(id);
    if(b.dataset.action==='zoom'){ $('large-image').src=row.url;$('large-image').alt=row.title+' - '+row.filename;$('large-title').textContent=`${row.number}. ${row.title}`;$('large-link').href=row.url;$('photo-dialog').showModal(); }
    if(b.dataset.action==='components')openComponents(id);
    if(b.dataset.action==='purpose'){const key=b.dataset.value,uses=d.uses.includes(key)?d.uses.filter(u=>u!==key):[...d.uses,key];update(id,{uses,primary_for:key==='listing'&&!uses.includes('listing')?[]:d.primary_for});}
    if(b.dataset.action==='clear'){decisions[id]=M.clean({updated_at:new Date().toISOString()},PRODUCT_IDS);persist();refreshCard(id);toast('Choices cleared for this photograph.');}
  });
  $('gallery').addEventListener('keydown',e=>{if(e.key==='Escape')e.target.blur();});
  $('gallery').addEventListener('change',e=>{const a=e.target.closest('article[data-id]');if(!a)return;const id=a.dataset.id;
    if(e.target.dataset.field==='action')update(id,{action:e.target.value});
    if(e.target.dataset.type){const types=Array.from(a.querySelectorAll('[data-type]:checked')).map(n=>n.dataset.type);update(id,{types});}
  });
  $('gallery').addEventListener('input',e=>{const a=e.target.closest('article[data-id]');if(!a)return;const field=e.target.dataset.field;if(['notes','destination','replacement'].includes(field))update(a.dataset.id,{[field]:e.target.value},false);});
  $('gallery').addEventListener('focusout',e=>{const a=e.target.closest('article[data-id]');if(!a)return;if(['notes','destination','replacement'].includes(e.target.dataset.field)){const footer=a.querySelector('.card-footer span'),d=dFor(a.dataset.id);footer.textContent=M.complete(ROWS.get(a.dataset.id),d)?'✓ Review complete':d.action?'Decision saved':'Feedback saved - action undecided';}});
  function openComponents(id){const d=dFor(id);componentDraft={id,components:new Set(d.components),primary:new Set(d.primary_for)};$('component-search').value='';renderComponents();$('component-dialog').showModal();}
  function renderComponents(){const term=$('component-search').value.trim().toLowerCase();const items=DATA.products.filter(p=>!term||(p.title+' '+p.family).toLowerCase().includes(term));$('component-selected').textContent=`${componentDraft.components.size} components chosen · ${componentDraft.primary.size} proposed primary selections`;
    $('component-options').innerHTML=items.map(p=>`<div class="component-row"><label><input type="checkbox" data-component="${p.id}" ${componentDraft.components.has(p.id)?'checked':''}><span>${esc(p.title)}<small>${esc(p.family)}${p.listing_decision==='exclude'?' · Currently excluded from catalogue':''}</small></span></label><label class="primary-option"><input type="checkbox" data-primary="${p.id}" ${componentDraft.primary.has(p.id)?'checked':''} ${!componentDraft.components.has(p.id)?'disabled':''}> Primary</label></div>`).join('');
  }
  $('component-search').addEventListener('input',renderComponents);
  $('component-options').addEventListener('change',e=>{const id=e.target.dataset.component||e.target.dataset.primary;if(!id)return;if(e.target.dataset.component){if(e.target.checked)componentDraft.components.add(id);else{componentDraft.components.delete(id);componentDraft.primary.delete(id);}}else{if(e.target.checked)componentDraft.primary.add(id);else componentDraft.primary.delete(id);}renderComponents();});
  $('component-cancel').addEventListener('click',()=>$('component-dialog').close());
  $('component-save').addEventListener('click',()=>{
    const draft=componentDraft;const d=dFor(draft.id);if(['exclude','duplicate'].includes(d.action)&&draft.primary.size){toast('Change the decision before assigning a primary image.');return;}
    let moved=0;for(const [id,value] of Object.entries(decisions)){if(id===draft.id)continue;const old=dFor(id);const remaining=old.primary_for.filter(p=>!draft.primary.has(p));if(remaining.length!==old.primary_for.length){decisions[id]={...old,primary_for:remaining,updated_at:new Date().toISOString()};moved++;}}
    update(draft.id,{components:[...draft.components],primary_for:[...draft.primary]});$('component-dialog').close();if(moved){render();toast(`Primary proposal moved from ${moved} other photograph${moved===1?'':'s'}.`);}
  });
  for(const dialog of document.querySelectorAll('dialog'))dialog.addEventListener('click',e=>{if(e.target===dialog){const r=dialog.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)dialog.close();}});
  $('photo-dialog').addEventListener('close',()=>{$('large-image').removeAttribute('src');});
  function download(name,content,type){const url=URL.createObjectURL(new Blob([content],{type}));const a=document.createElement('a');a.href=url;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),10000);}
  const stamp=()=>new Date().toISOString().replace(/[:.]/g,'-');
  $('export-json').addEventListener('click',()=>{download('wall-photo-decisions-'+stamp()+'.json',JSON.stringify(M.exportDocument(DATA,decisions),null,2),'application/json');toast('Decision export prepared. No images are included.');});
  $('export-csv').addEventListener('click',()=>{
    const rows=[['Photo','Old title','Image URL','Audit finding','Decision','Purposes','Image types','Components','Primary for','Destination','Keep other photo','Notes','Dropbox locations']];
    for(const r of DATA.records){const d=dFor(r.id);if(!M.edited(d))continue;rows.push([r.number,r.title,r.url,M.groups[r.group],M.actions[d.action],d.uses.join('; '),d.types.map(t=>M.types[t]).join('; '),d.components.map(id=>PRODUCTS[id].title).join('; '),d.primary_for.map(id=>PRODUCTS[id].title).join('; '),d.destination,d.replacement,d.notes,r.locations.map(m=>m.path).join('\n')]);}
    download('wall-photo-decisions-'+stamp()+'.csv','\ufeff'+rows.map(r=>r.map(M.csvCell).join(',')).join('\r\n'),'text/csv;charset=utf-8');toast('CSV decisions exported.');
  });
  $('save-page').addEventListener('click',()=>{
    const copy=document.documentElement.cloneNode(true);copy.querySelector('#saved-decisions').textContent=M.safeJson(decisions);copy.querySelectorAll('dialog[open]').forEach(d=>d.removeAttribute('open'));copy.querySelector('#toast').hidden=true;copy.querySelector('#gallery').innerHTML='';copy.querySelector('#large-image').removeAttribute('src');
    download('wall-sculpture-photo-decisions-reviewed-'+stamp()+'.htm','<!doctype html>\n'+copy.outerHTML,'text/html;charset=utf-8');toast('Portable review page prepared, including your decisions and image URLs.');
  });
  $('import-json').addEventListener('click',()=>$('import-file').click());
  $('import-file').addEventListener('change',async()=>{const file=$('import-file').files[0];if(!file)return;try{if(file.size>5*1024*1024)throw Error('This decision file is unexpectedly large.');importDraft=M.importDocument(JSON.parse(await file.text()),DATA);$('import-summary').textContent=`${Object.keys(importDraft).length} photo decisions are ready to import.`;$('import-dialog').showModal();}catch(e){toast(e.message);}finally{$('import-file').value='';}});
  $('import-cancel').addEventListener('click',()=>{importDraft=null;$('import-dialog').close();});
  $('import-confirm').addEventListener('click',()=>{const imported=Object.entries(importDraft||{});decisions=M.mergeImport(decisions,importDraft||{},PRODUCT_IDS,new Date().toISOString());persist();render();$('import-dialog').close();toast(`${imported.length} photo decisions imported.`);importDraft=null;});
  window.addEventListener('storage',e=>{if(e.key===STORAGE_KEY)toast('Choices changed in another tab. Export this tab’s decisions before reloading to compare them.');});
  $('search').value='';$('product-filter').value='';$('review-filter').value='all';$('tag-filter').value='';
  if(storageOK)$('save-status').textContent='● Choices save in this browser';
  updateProgress();render();
})();
