'use strict';
const imageSortStorage='boldstone.review.imageSort.v1';
const similarityJobs=new Map();
let sortDraft=[];
function initImageSort(route) {
  let saved=[];try{saved=JSON.parse(localStorage.getItem(imageSortStorage)||'[]');}catch{}
  state.imageSort=route!==undefined?ImageSort.parse(route):ImageSort.clean(saved);
  state.sortJobKey='';
  state.heldImageOrder=null;state.lastEditedImageId=null;
}
function holdImageOrder(aid){
  if(state.tab!=='images'||!$('#image-grid')||!currentImages().some(im=>im.id===aid))return;
  if(!state.heldImageOrder)state.heldImageOrder=filteredImages().map(im=>im.id);
  state.lastEditedImageId=aid;state.sortJobKey='';
}
function heldImageOrder(images){
  const rank=new Map(state.heldImageOrder.map((id,i)=>[id,i]));
  // Existing cards keep their place. Newly visible/imported files append until
  // an explicit sort or navigation starts a new review order.
  for(const image of defaultImageOrder(images))if(!rank.has(image.id)){
    rank.set(image.id,state.heldImageOrder.length);state.heldImageOrder.push(image.id);
  }
  return [...images].sort((a,b)=>rank.get(a.id)-rank.get(b.id));
}
function sortValue(image,key) {
  const choice=imageChoices(image.id),o=image.original||{};
  switch(key){
    case 'listing':return [activeImageUses(choice).includes('listing')?(choice.primary?0:1):2,Number(choice.order)||0];
    case 'folder':return image.folder_label||image.folder_url||null;
    case 'type':return imageTypes(image).map(t=>typeLabels()[t]||t).sort().join(', ');
    case 'purpose':return choice.decision==='exclude'?'Excluded':activeImageUses(choice).slice().sort().join(', ');
    case 'name':return image.name;
    case 'source':return image.source;
    case 'bytes':return Number.isFinite(o.bytes)&&o.bytes>0?o.bytes:null;
    case 'pixels':return o.dimensions?.length===2&&o.dimensions.every(x=>Number.isFinite(x)&&x>0)?o.dimensions[0]*o.dimensions[1]:null;
    default:return null;
  }
}
function sortControls() {
  sortDraft=ImageSort.clean(state.imageSort);
  return `<section class="image-sort" aria-label="Image sorting"><div class="sort-heading"><details id="image-sort-options"><summary>Sort: <span id="sort-summary">${esc(sortSummary())}</span></summary><div class="sort-panel"><p>Sort by the first rule, then each rule below it. These are viewing preferences; your listing order and selections stay as saved.</p><div id="sort-rows">${sortRows()}</div><div class="sort-actions"><button class="button" id="sort-add" ${sortDraft.length>=5?'disabled':''}>Add sort rule</button><button class="button dark" id="sort-apply">Apply sort</button><button class="text-button" id="sort-reset">Reset to default</button></div><p class="small muted">Similarity runs within groups made by earlier rules. Later rules choose the starting image and break equal-distance ties. Unknown original sizes sort last.</p></div></details><div class="sort-buttons"><button class="button" id="sort-reapply">Reapply sort</button><button class="button" id="sort-similar">Sort by similarity</button></div></div><p id="sort-status" class="small muted" role="status"></p></section>`;
}
function sortSummary(){return (state.imageSort||[]).map(r=>ImageSort.labels[r.key]+(r.key==='similarity'?(r.direction==='desc'?' (reverse)':''):(r.direction==='desc'?' ↓':' ↑'))).join(' · ')||'Default order';}
function sortRows(){
  return sortDraft.map((r,i)=>`<div class="sort-row" data-sort-row="${i}"><span>${i+1}.</span><label><span>${i?'Then by':'Sort by'}</span><select data-sort-key="${i}" aria-label="Sort rule ${i+1}">${Object.entries(ImageSort.labels).filter(([key])=>key===r.key||!sortDraft.some(x=>x.key===key)).map(([key,label])=>`<option value="${key}" ${key===r.key?'selected':''}>${label}</option>`).join('')}</select></label><label><span>Direction</span><select data-sort-direction="${i}" aria-label="Direction for sort rule ${i+1}">${(r.key==='similarity'?[['asc','Similar neighbours'],['desc','Reverse similar order']]:r.key==='listing'?[['asc','Primary / listing first'],['desc','Other images first']]:['pixels','bytes'].includes(r.key)?[['desc','Largest first'],['asc','Smallest first']]:[['asc','A to Z'],['desc','Z to A']]).map(([v,label])=>`<option value="${v}" ${v===r.direction?'selected':''}>${label}</option>`).join('')}</select></label><div class="sort-row-actions"><button class="button" data-sort-up="${i}" aria-label="Move sort rule ${i+1} up" ${i?'':'disabled'}>↑</button><button class="button" data-sort-down="${i}" aria-label="Move sort rule ${i+1} down" ${i<sortDraft.length-1?'':'disabled'}>↓</button><button class="button" data-sort-remove="${i}" aria-label="Remove sort rule ${i+1}">×</button></div></div>`).join('')||'<p class="small muted">Default order: listing choices first on sculptures; folders and file names in family galleries.</p>';
}
function renderSortDraft(){ $('#sort-rows').innerHTML=sortRows();$('#sort-add').disabled=sortDraft.length>=5; }
function applyImageSort(rows) {
  state.imageSort=ImageSort.clean(rows);state.limit=24;state.sortJobKey='';state.heldImageOrder=null;state.lastEditedImageId=null;
  try{localStorage.setItem(imageSortStorage,JSON.stringify(state.imageSort));}catch{}
  for(const [key,value] of similarityJobs)if(value.state==='error')similarityJobs.delete(key);
  const host=$('.image-sort');if(host)host.outerHTML=sortControls();
  renderGrid({preservePosition:false});
}
function sortImages(images) {
  if(state.heldImageOrder){state.sortJobKey='';return heldImageOrder(images);}
  if(!state.imageSort?.length){state.sortJobKey='';return defaultImageOrder(images);}
  // Cache choice-derived values once; library choices otherwise scan all reviews
  // for every comparator invocation.
  const values=new Map(images.map(im=>[im.id,Object.fromEntries(state.imageSort.filter(r=>r.key!=='similarity').map(r=>[r.key,sortValue(im,r.key)]))]));
  const plan=ImageSort.plan(images,state.imageSort,(im,key)=>values.get(im.id)[key]);
  if(!plan.groups||images.length<2){state.sortJobKey='';return plan.images;}
  const signature=JSON.stringify([plan.groups,plan.reverse,images.map(im=>[im.id,im.original?.dropbox_content_hash,im.original?.sha256,im.cached_file?.stamp,im.local_preview])]);
  state.sortJobKey=signature;
  if(!similarityJobs.has(signature)) {
    similarityJobs.set(signature,{state:'queued',total:images.length});
    setTimeout(()=>{
      if(state.sortJobKey===signature)requestSimilarity(signature,plan);
      else if(similarityJobs.get(signature)?.state==='queued')similarityJobs.delete(signature);
    },250);
  }
  const job=similarityJobs.get(signature);
  if(job.state==='ready') {
    const byId=new Map(images.map(im=>[im.id,im]));
    return job.order.map(id=>byId.get(id)).filter(Boolean);
  }
  return plan.images;
}
async function requestSimilarity(signature,plan) {
  try {
    let job=await api('/api/similarity',{groups:plan.groups,reverse:plan.reverse});
    similarityJobs.set(signature,job);updateSortStatus();
    while(job.state==='queued'||job.state==='running') {
      await new Promise(resolve=>setTimeout(resolve,1200));
      job=await api('/api/similarity/'+job.job_id);
      similarityJobs.set(signature,job);updateSortStatus();
    }
    if(job.state==='ready')applySimilarityWhenSafe(signature);
  } catch(error){similarityJobs.set(signature,{state:'error',error:error.message});updateSortStatus();}
}
function applySimilarityWhenSafe(signature) {
  if(state.sortJobKey!==signature||!$('#image-grid'))return;
  if(state.saving||state.dirty.size||$('dialog[open],.card-types[open],#image-sort-options[open]')){
    setTimeout(()=>applySimilarityWhenSafe(signature),1200);return;
  }
  renderGrid();
}
function updateSortStatus() {
  const el=$('#sort-status');if(!el)return;
  if(state.heldImageOrder){el.textContent='Image order is held while you review. Reapply sort to arrange the gallery using your latest choices.';return;}
  if(!state.imageSort?.some(r=>r.key==='similarity')){el.textContent='Your sort rules are remembered on this browser and included in the page link.';return;}
  const job=similarityJobs.get(state.sortJobKey);
  if(!job){el.textContent='Visual similarity needs at least two visible images.';return;}
  el.textContent=job.state==='ready'?`Similarity sorted ${job.analysed} of ${job.total} images across this entire filtered gallery, including images behind Show more. ${job.missing_ids.length?job.missing_ids.length+' without a usable local preview stay last in their group. ':''}Compared on this Mac using cached photos/previews. Similarity is approximate; it does not establish duplicates or sculpture identity.`:
    job.state==='error'?job.error+' Open Sort and apply again to retry.':
    job.phase==='ordering'?'Arranging similar neighbours…':`Analysing visual similarity on this Mac: ${job.completed||0} of ${job.total}. The first pass takes longer; results are cached. Current order stays visible until ready.`;
}
document.addEventListener('change',e=>{
  const el=e.target;
  if(el.hasAttribute('data-sort-key')){const row=sortDraft[Number(el.dataset.sortKey)];row.key=el.value;row.direction=['pixels','bytes'].includes(el.value)?'desc':'asc';renderSortDraft();}
  if(el.hasAttribute('data-sort-direction'))sortDraft[Number(el.dataset.sortDirection)].direction=el.value;
});
document.addEventListener('click',e=>{
  const el=e.target.closest('button');if(!el)return;
  if(el.id==='sort-similar')applyImageSort([{key:'similarity',direction:'asc'}]);
  if(el.id==='sort-apply')applyImageSort(sortDraft);
  if(el.id==='sort-reset')applyImageSort([]);
  if(el.id==='sort-reapply')applyImageSort(state.imageSort);
  if(el.id==='sort-add'){const key=Object.keys(ImageSort.labels).find(k=>!sortDraft.some(r=>r.key===k));if(key&&sortDraft.length<5)sortDraft.push({key,direction:'asc'});renderSortDraft();}
  for(const [attribute,offset] of [['sortUp',-1],['sortDown',1]])if(el.dataset[attribute]!==undefined){const i=Number(el.dataset[attribute]),j=i+offset;if(j>=0&&j<sortDraft.length)[sortDraft[i],sortDraft[j]]=[sortDraft[j],sortDraft[i]];renderSortDraft();}
  if(el.hasAttribute('data-sort-remove')){sortDraft.splice(Number(el.dataset.sortRemove),1);renderSortDraft();}
});
