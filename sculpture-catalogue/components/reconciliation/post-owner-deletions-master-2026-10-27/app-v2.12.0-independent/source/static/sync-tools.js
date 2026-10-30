'use strict';
let dropboxSyncTimer,dropboxSyncBusy=false,dropboxShownGeneration=0,dropboxLatestStatus=null;
function syncCanRefresh(){
  return !state.loading&&!state.saving&&!state.dirty.size&&!state.selected.size&&!document.querySelector('dialog[open],.card-types[open],#image-sort-options[open]')&&
    !document.activeElement?.matches('input,textarea,select');
}
function syncHasUpdate(status){
  return status.generation>dropboxShownGeneration||Boolean(status.catalogue_source&&Object.entries(status.catalogue_source).some(([k,v])=>v!==state.boot?.source?.[k]));
}
function renderDropboxSync(status){
  const label=$('#dropbox-sync-status'),button=$('#dropbox-sync-now');
  if(!label)return;
  const ready=syncHasUpdate(status);
  label.textContent=!status.enabled?'Dropbox refresh paused':status.state==='error'?'Dropbox: retrying':
    ready&&!syncCanRefresh()?'Catalogue updates ready - finish editing':status.state==='checking'?'Dropbox: checking for images':
    status.pending_previews?`Dropbox: ${status.pending_previews} previews pending`:
    status.last_checked?'Dropbox checked '+new Date(status.last_checked).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'}):'Dropbox: connecting';
  label.title=status.error||'New Wall Sculptures images are checked automatically every minute while the app is running. Your reviews are preserved.';
  label.classList.toggle('sync-error',status.state==='error');
  button.textContent=ready?'Show updates':'Check now';
  button.disabled=!status.enabled||dropboxSyncBusy||(status.state==='checking'&&!ready);
}
async function refreshDropboxView(status){
  if(!syncHasUpdate(status)||!syncCanRefresh())return;
  const pid=state.pid,request=state.request,writeEpoch=state.writeEpoch,mainScroll=$('#main').scrollTop,pageScroll=window.scrollY;
  const fresh=await api('/api/bootstrap');
  const payload=['__family__','__specifications__'].includes(pid)?null:await api(pid==='__library__'?libraryAPI():'/api/products/'+encodeURIComponent(pid));
  // A save, navigation or unsaved edit may begin while these reads are in flight.
  if(pid!==state.pid||request!==state.request||writeEpoch!==state.writeEpoch||!syncCanRefresh())return;
  state.boot=fresh;absorb(fresh.assignments||[]);
  const familyFilter=$('#family-filter');
  if(familyFilter){const selected=familyFilter.value;familyFilter.innerHTML='<option value="">All families</option>'+fresh.families.map(f=>`<option>${esc(f)}</option>`).join('');familyFilter.value=selected;}
  for(const p of fresh.products)if(p.review.version)state.reviews.set(key('product',p.id,''),p.review);
  if(payload){absorb(payload.reviews);if(pid==='__library__')state.library=payload;else state.current=payload;}
  renderList();
  if(pid==='__family__'||state.tab==='images'){
    renderMain();$('#main').scrollTop=mainScroll;window.scrollTo(0,pageScroll);
  }
  dropboxShownGeneration=fresh.dropbox_sync.generation;
}
async function pollDropboxSync(manual=false){
  if(dropboxSyncBusy||!state.boot||(!manual&&document.hidden))return;
  dropboxSyncBusy=true;
  try{
    const pending=dropboxLatestStatus&&syncHasUpdate(dropboxLatestStatus);
    const status=manual&&!pending?await api('/api/dropbox-sync',{}):await api('/api/dropbox-sync');
    dropboxLatestStatus=status;
    await refreshDropboxView(status);
  }catch(error){
    if(manual)toast(error.message,true);
  }finally{
    dropboxSyncBusy=false;
    if(dropboxLatestStatus)renderDropboxSync(dropboxLatestStatus);
  }
}
function startDropboxSync(){
  dropboxShownGeneration=state.boot.dropbox_sync?.generation||0;
  dropboxLatestStatus=state.boot.dropbox_sync;
  if(dropboxLatestStatus)renderDropboxSync(dropboxLatestStatus);
  $('#dropbox-sync-now').onclick=()=>pollDropboxSync(true);
  clearInterval(dropboxSyncTimer);dropboxSyncTimer=setInterval(()=>pollDropboxSync(),10000);
  pollDropboxSync();
}
