'use strict';
let nativeJobStatus={jobs:[],active_count:0,deletion_activity:{}},nativeJobsRequest=null,nativeJobsTimer;
let nativeJobsLoaded=false,nativeJobsError='';
let nativeViewNeedsRefresh=false;
let nativeJobDialogSignature='';
const finishedNativeJobs=new Map();
function nativeJobLabel(value){return ({keeper_reserved:'Retained as keeper for an active job',executing:'Deletion in progress',deleted:'Already deleted',already_absent:'Already removed',queued:'Queued',running:'Running',completed:'Completed',needs_review:'Needs review',uncertain:'Check result',superseded:'Replaced by newer choices',cancelled:'Cancelled before starting'})[value]||value;}
function renderNativeJobButton(){
  const count=nativeJobStatus.active_count+(nativeJobStatus.reservation?1:0);
  $('#jobs-count').textContent=String(count);
  $('#jobs-open').classList.toggle('jobs-active',count>0);
  const problems=nativeJobStatus.jobs.filter(j=>['needs_review','uncertain'].includes(j.state)).length;
  if(!count&&problems)$('#jobs-count').textContent='! '+problems;
  $('#jobs-open').title=count+' active job(s)'+(problems?' · '+problems+' need attention':'');
}
function renderNativeJobs(){
  const dialog=$('#jobs-dialog'),s=nativeJobStatus;
  nativeJobDialogSignature=JSON.stringify(s);
  dialog.innerHTML=`<button class="close" data-close="jobs-dialog" aria-label="Close background jobs">×</button><span class="eyebrow">BACKGROUND WORK</span><h2>Dropbox jobs</h2><p>You can close this window and keep reviewing. Jobs run in order while the local app server is running.</p>${s.reservation?`<aside class="job-wait"><strong>${esc(s.reservation.label)}</strong><p>${esc(s.reservation.reason)}</p></aside>`:''}${!nativeJobsLoaded?'<p role="status">'+esc(nativeJobsError||'Loading current jobs…')+'</p>':''}${s.jobs.map(job=>{
    const progress=job.progress?.results||job.result?.results||[],done=progress.filter(r=>['deleted','already_absent'].includes(r.state)).length;
    const file=job.result?.file,path=file?.path;
    return `<section class="operation-row native-job" data-job-id="${esc(job.id)}"><div><strong>${esc(job.label)}</strong><p><span class="chip">${esc(nativeJobLabel(job.state))}</span>${progress.length?' '+done+' of '+progress.length+' verified':''}</p>${job.skipped?.length?`<p>${job.skipped.length} file(s) skipped because they already had a job or were retained as keepers.</p>`:''}${job.message?`<p>${esc(job.message)}</p>`:''}${job.state==='queued'&&s.reservation?'<p class="small muted">Waiting for the current Dropbox writer.</p>':''}${path?`<p><a href="https://www.dropbox.com/preview${encodeURI(path).replaceAll('#','%23').replaceAll('?','%3F')}" target="_blank" rel="noopener">Image ↗</a> · <a href="https://www.dropbox.com/home${encodeURI(path.slice(0,path.lastIndexOf('/'))).replaceAll('#','%23').replaceAll('?','%3F')}" target="_blank" rel="noopener">Folder ↗</a></p>`:''}${progress.length?`<details><summary>File results</summary>${progress.map(r=>`<p class="small">${esc(job.files.find(f=>f.id===r.file_id)?.name||r.file_id||r.operation_id)}<br>${esc(({deleted:'Deleted - absence verified',already_absent:'Already absent - app entry removed',not_started:'Not attempted',prepared:'Not attempted',executing:'Checking Dropbox',uncertain:'Result needs checking',rejected:'Not deleted - review changed'})[r.state]||r.state)}${r.message?' · '+esc(r.message):''}</p>`).join('')}</details>`:''}<small class="muted">${esc(new Date(job.updated_at).toLocaleString())}</small></div>${job.state==='uncertain'?`<button class="button" data-check-job="${esc(job.id)}">Check result</button>`:''}${job.state==='queued'?`<button class="button" data-cancel-job="${esc(job.id)}">Cancel queued job</button>`:''}${['needs_review','cancelled'].includes(job.state)&&job.asset_id?`<button class="button" data-replan-job="${esc(job.id)}">Plan again</button><button class="button" data-job-components="${esc(job.asset_id)}">Choose components</button>`:''}</section>`;
  }).join('')||(!nativeJobsLoaded?'':s.reservation?'<p>No additional file jobs queued.</p>':'<p>No background jobs yet.</p>')}`;
}
function deletionActivity(image){
  return [image.id,...(image.duplicates||[]).map(a=>a.id)].map(id=>nativeJobStatus.deletion_activity?.[id]).find(Boolean);
}
function deletionBusyNotice(items){
  if(!items?.length)return '';
  return `<aside class="bulk-delete-skipped"><strong>${items.length} file(s) already handled or reserved</strong><ul>${items.map(item=>`<li>${esc(item.name)} - ${esc(nativeJobLabel(item.state))}</li>`).join('')}</ul><p>These files are skipped. Other selected files can continue.</p><button class="button" type="button" data-open-native-jobs>View existing jobs</button></aside>`;
}
async function refreshDeletionActivity(){
  const result=await pollNativeJobs();
  if(!result)throw Error('Could not check current deletion jobs. Try again before reviewing this selection.');
  return result.deletion_activity||{};
}
function pollNativeJobs(){
  if(nativeJobsRequest)return nativeJobsRequest;
  if(!state.boot)return Promise.resolve(null);
  nativeJobsRequest=(async()=>{
    try{
      nativeJobStatus=await api('/api/jobs');nativeJobsLoaded=true;nativeJobsError='';renderNativeJobButton();
      if($('#jobs-dialog').open&&nativeJobDialogSignature!==JSON.stringify(nativeJobStatus)&&!$('#jobs-dialog').querySelector('details[open],[data-check-job]:disabled'))renderNativeJobs();
      for(const job of nativeJobStatus.jobs){
        const signature=JSON.stringify([job.state,job.updated_at,job.progress,job.result]);
        if(!['completed','needs_review','uncertain'].includes(job.state)||finishedNativeJobs.get(job.id)===signature)continue;
        nativeViewNeedsRefresh=true;
        for(const item of job.progress?.results||job.result?.results||[])
          if(['deleted','already_absent'].includes(item.state))state.selected.delete(item.file_id);
        if(job.kind==='delete'&&job.state==='completed')for(const file of job.files)state.selected.delete(file.id);
        finishedNativeJobs.set(job.id,signature);
      }
      if(nativeViewNeedsRefresh&&syncCanRefresh())await refreshNativeView();
      return nativeJobStatus;
    }catch(error){nativeJobsError='Could not refresh jobs: '+error.message;$('#jobs-open').title=nativeJobsError;return null;}
    finally{nativeJobsRequest=null;}
  })();
  return nativeJobsRequest;
}
async function refreshNativeView(){
  const pid=state.pid,request=state.request,pageScroll=window.scrollY,scroll=$('#main').scrollTop;
  const boot=await api('/api/bootstrap');
  const payload=pid==='__family__'?null:await api(pid==='__library__'?libraryAPI():'/api/products/'+encodeURIComponent(pid));
  if(pid!==state.pid||request!==state.request||!syncCanRefresh())return;
  state.boot=boot;absorb(boot.assignments||[]);
  if(payload){absorb(payload.reviews);if(pid==='__library__')state.library=payload;else state.current=payload;}
  renderList();if(pid==='__family__'||state.tab==='images'){renderMain();$('#main').scrollTop=scroll;window.scrollTo(0,pageScroll);}
  nativeViewNeedsRefresh=false;
}
async function trackNativeJob(job){
  nativeJobStatus.jobs=[job,...nativeJobStatus.jobs.filter(j=>j.id!==job.id)];
  nativeJobStatus.active_count=nativeJobStatus.jobs.filter(j=>['queued','running'].includes(j.state)).length;
  renderNativeJobButton();await pollNativeJobs();
}
async function findNativeJob(id){
  await pollNativeJobs();
  // The shared poll may have started before the queue transaction committed.
  // One fresh read can discover it; this never resubmits a deletion.
  if(!nativeJobStatus.jobs.some(j=>j.id===id))await pollNativeJobs();
  return nativeJobStatus.jobs.find(j=>j.id===id);
}
function startNativeJobs(){
  clearInterval(nativeJobsTimer);nativeJobsTimer=setInterval(pollNativeJobs,2500);pollNativeJobs();
}
document.addEventListener('click',async e=>{
  const b=e.target.closest('button');if(!b)return;
  if(b.id==='jobs-open'||b.hasAttribute('data-open-native-jobs')){renderNativeJobs();if(!$('#jobs-dialog').open)$('#jobs-dialog').showModal();await pollNativeJobs();renderNativeJobs();}
  if(b.dataset.checkJob){b.disabled=true;try{await api('/api/jobs/check',{job_id:b.dataset.checkJob});await pollNativeJobs();renderNativeJobs();}catch(error){toast(error.message,true);}finally{b.disabled=false;}}
  for(const [key,route] of [['cancelJob','cancel'],['replanJob','replan']])if(b.dataset[key]){b.disabled=true;try{await api('/api/jobs/'+route,{job_id:b.dataset[key]});await pollNativeJobs();renderNativeJobs();}catch(error){toast(error.message,true);}finally{b.disabled=false;}}
  if(b.dataset.jobComponents){$('#jobs-dialog').close();openComponents(b.dataset.jobComponents);}
});
