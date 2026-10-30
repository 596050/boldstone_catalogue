'use strict';
let nativeJobStatus={jobs:[],active_count:0},nativeJobsBusy=false,nativeJobsTimer;
let nativeViewNeedsRefresh=false;
let nativeJobDialogSignature='';
const finishedNativeJobs=new Set();
function nativeJobLabel(value){return ({queued:'Queued',running:'Running',completed:'Completed',needs_review:'Needs review',uncertain:'Check result',superseded:'Replaced by newer choices',cancelled:'Cancelled before starting'})[value]||value;}
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
  dialog.innerHTML=`<button class="close" data-close="jobs-dialog" aria-label="Close background jobs">×</button><span class="eyebrow">BACKGROUND WORK</span><h2>Dropbox jobs</h2><p>You can close this window and keep reviewing. Jobs run in order while the local app server is running.</p>${s.reservation?`<aside class="job-wait"><strong>${esc(s.reservation.label)}</strong><p>${esc(s.reservation.reason)}</p></aside>`:''}${s.jobs.map(job=>{
    const progress=job.progress?.results||job.result?.results||[],done=progress.filter(r=>['deleted','already_absent'].includes(r.state)).length;
    const file=job.result?.file,path=file?.path;
    return `<section class="operation-row native-job" data-job-id="${esc(job.id)}"><div><strong>${esc(job.label)}</strong><p><span class="chip">${esc(nativeJobLabel(job.state))}</span>${progress.length?' '+done+' of '+progress.length+' verified':''}</p>${job.message?`<p>${esc(job.message)}</p>`:''}${job.state==='queued'&&s.reservation?'<p class="small muted">Waiting for the current Dropbox writer.</p>':''}${path?`<p><a href="https://www.dropbox.com/preview${encodeURI(path).replaceAll('#','%23').replaceAll('?','%3F')}" target="_blank" rel="noopener">Image ↗</a> · <a href="https://www.dropbox.com/home${encodeURI(path.slice(0,path.lastIndexOf('/'))).replaceAll('#','%23').replaceAll('?','%3F')}" target="_blank" rel="noopener">Folder ↗</a></p>`:''}${progress.length?`<details><summary>File results</summary>${progress.map(r=>`<p class="small">${esc(job.files.find(f=>f.id===r.file_id)?.name||r.file_id||r.operation_id)}<br>${esc(({deleted:'Deleted - absence verified',already_absent:'Already absent - app entry removed',not_started:'Not attempted',prepared:'Not attempted',executing:'Checking Dropbox',uncertain:'Result needs checking',rejected:'Not deleted - review changed'})[r.state]||r.state)}${r.message?' · '+esc(r.message):''}</p>`).join('')}</details>`:''}<small class="muted">${esc(new Date(job.updated_at).toLocaleString())}</small></div>${job.state==='uncertain'?`<button class="button" data-check-job="${esc(job.id)}">Check result</button>`:''}${job.state==='queued'?`<button class="button" data-cancel-job="${esc(job.id)}">Cancel queued job</button>`:''}${job.state==='needs_review'&&job.asset_id?`<button class="button" data-replan-job="${esc(job.id)}">Plan again</button><button class="button" data-job-components="${esc(job.asset_id)}">Choose components</button>`:''}</section>`;
  }).join('')||(s.reservation?'<p>No additional file jobs queued.</p>':'<p>No background jobs yet.</p>')}`;
}
async function pollNativeJobs(){
  if(nativeJobsBusy||!state.boot)return;
  nativeJobsBusy=true;
  try{
    nativeJobStatus=await api('/api/jobs');renderNativeJobButton();
    if($('#jobs-dialog').open&&nativeJobDialogSignature!==JSON.stringify(nativeJobStatus)&&!$('#jobs-dialog').querySelector('details[open],[data-check-job]:disabled'))renderNativeJobs();
    for(const job of nativeJobStatus.jobs){
      if(!['completed','needs_review','uncertain'].includes(job.state)||finishedNativeJobs.has(job.id))continue;
      nativeViewNeedsRefresh=true;
      for(const item of job.progress?.results||job.result?.results||[])
        if(['deleted','already_absent'].includes(item.state))state.selected.delete(item.file_id);
      if(job.kind==='delete'&&job.state==='completed')for(const file of job.files)state.selected.delete(file.id);
      finishedNativeJobs.add(job.id);
    }
    if(nativeViewNeedsRefresh&&syncCanRefresh())await refreshNativeView();
  }catch(error){$('#jobs-open').title='Could not refresh jobs: '+error.message;}
  finally{nativeJobsBusy=false;}
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
async function findNativeJob(id){await pollNativeJobs();return nativeJobStatus.jobs.find(j=>j.id===id);}
function startNativeJobs(){
  clearInterval(nativeJobsTimer);nativeJobsTimer=setInterval(pollNativeJobs,2500);pollNativeJobs();
}
document.addEventListener('click',async e=>{
  const b=e.target.closest('button');if(!b)return;
  if(b.id==='jobs-open'){await pollNativeJobs();renderNativeJobs();$('#jobs-dialog').showModal();}
  if(b.dataset.checkJob){b.disabled=true;try{await api('/api/jobs/check',{job_id:b.dataset.checkJob});await pollNativeJobs();renderNativeJobs();}catch(error){toast(error.message,true);}finally{b.disabled=false;}}
  for(const [key,route] of [['cancelJob','cancel'],['replanJob','replan']])if(b.dataset[key]){b.disabled=true;try{await api('/api/jobs/'+route,{job_id:b.dataset[key]});await pollNativeJobs();renderNativeJobs();}catch(error){toast(error.message,true);}finally{b.disabled=false;}}
  if(b.dataset.jobComponents){$('#jobs-dialog').close();openComponents(b.dataset.jobComponents);}
});
