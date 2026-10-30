'use strict';
let nativeJobStatus={jobs:[],active_count:0,deletion_activity:{}},nativeJobsRequest=null,nativeJobsTimer;
let nativeJobsLoaded=false,nativeJobsError='';
let nativeViewNeedsRefresh=false;
let nativeJobDialogSignature='';
const finishedNativeJobs=new Map();
function nativeJobLabel(value){return ({keeper_reserved:'Retained as keeper for an active job',executing:'Deletion in progress',deleted:'Already deleted',already_absent:'Already removed',present:'File present - ready for a new review',queued:'Queued',running:'Running',completed:'Completed',needs_review:'Needs review',uncertain:'Check result',superseded:'Replaced by newer choices',cancelled:'Cancelled before starting'})[value]||value;}
function renderNativeJobButton(){
  const filename=nativeJobStatus.filename_job;
  const running=nativeJobStatus.jobs.filter(j=>j.state==='running').length+(filename?.state==='running'?1:0);
  const queued=nativeJobStatus.jobs.filter(j=>j.state==='queued').length,count=running+queued;
  const awaiting=nativeJobStatus.jobs.filter(j=>j.kind==='delete_review'&&j.state==='review_ready').length;
  const problems=nativeJobStatus.jobs.filter(j=>['needs_review','uncertain','review_attention'].includes(j.state)).length+
    (filename&&(['needs_review','unavailable'].includes(filename.state)||filename.heartbeat_stale)?1:0);
  $('#jobs-count').textContent=(count||!problems?String(count):'')+(awaiting?' · '+awaiting+' ready':'')+(problems?' ! '+problems:nativeJobsError?' !':'');
  $('#jobs-open').classList.toggle('jobs-active',count>0);
  $('#jobs-open').classList.toggle('jobs-attention',Boolean(problems||nativeJobsError));
  $('#jobs-open').title=running+' running · '+queued+' queued'+(problems?' · '+problems+' need attention':'')+(nativeJobsError?' · '+nativeJobsError:'');
}
function nativeJobsSignature(){return JSON.stringify([nativeJobStatus.jobs,nativeJobStatus.reservation,nativeJobsLoaded,nativeJobsError]);}
function nativeJobsStatusText(){return nativeJobsError?nativeJobsError+' Showing the last received status.':!nativeJobsLoaded?'Loading current jobs…':'';}
function jobDuration(seconds){
  if(seconds===null||seconds===undefined)return 'Not yet available';
  seconds=Math.max(0,Math.floor(seconds));
  return seconds>=3600?Math.floor(seconds/3600)+'h '+Math.floor(seconds%3600/60)+'m':seconds>=60?Math.floor(seconds/60)+'m '+seconds%60+'s':seconds+'s';
}
function filenameProgressHTML(job){
  if(!job)return '';
  if(job.state==='unavailable')return `<p role="status">${esc(job.stage)}</p><p class="small muted">${esc(job.message)}</p>`;
  const number=value=>Number(value||0).toLocaleString(),date=value=>value?new Date(value).toLocaleTimeString(): 'Not yet available';
  const pending=job.batch_number&&job.batch_files&&job.batch_state!=='verified';
  const checks=job.final_checks||'pending',failureCount=(job.verification_errors||[]).reduce((total,error)=>total+error.count,0);
  const checkLabel=({passed:'Passed',failed:'Needs review',pending:'Not yet complete'})[checks]||'Not yet complete';
  return `<div class="filename-progress"><p class="filename-progress-heading"><strong>${number(job.correct)} of ${number(job.total)} filenames verified</strong><span>${esc(job.percent)}%</span></p><progress aria-label="Filename verification progress" max="${Number(job.total)||1}" value="${Number(job.correct)||0}"></progress><p class="${job.state==='needs_review'?'filename-progress-warning':''}"><strong>${esc(job.stage)}</strong></p><dl><dt>Final checks</dt><dd class="${checks==='failed'?'filename-progress-warning':''}">${esc(checkLabel)}${failureCount?' - '+number(failureCount)+' failed':''}</dd><dt>Pass</dt><dd>${esc(job.pass_name)}</dd>${pending?`<dt>Current batch</dt><dd>${number(job.batch_number)} - ${number(job.batch_files)} files</dd><dt>Batch elapsed</dt><dd>${esc(jobDuration(job.batch_elapsed_seconds))}</dd>`:''}<dt>Last verified count</dt><dd>${esc(date(job.checked_at))}</dd>${job.state==='running'?`<dt>Worker update</dt><dd>${esc(date(job.heartbeat_at))} (${esc(jobDuration(job.heartbeat_age_seconds))} ago)</dd>`:''}</dl>${job.deferred_folders?`<p class="small">${number(job.deferred_folders)} folders changed during this pass and await follow-up.</p>`:''}<p class="small muted">${esc(job.message)}</p>${job.heartbeat_stale?'<p class="filename-progress-warning" role="status">No recent worker update. Showing the last verified count.</p>':''}</div>`;
}
function filenameJobSection(status){
  const reservation=status.reservation,job=status.filename_job;
  if(!reservation&&!job)return '';
  return `<aside class="job-wait"><strong>${esc(reservation?.label||'Dropbox filename renaming')}</strong>${reservation?`<p>${esc(reservation.reason)}</p>`:''}<div id="filename-job-progress">${filenameProgressHTML(job)}</div></aside>`;
}
function deletionResultHTML(job,r){
  const file=job.files.find(f=>f.id===r.file_id),rename=r.rename_reconciliation;
  const name=rename?.current_name||file?.name||r.file_id||r.operation_id;
  const reviewed=rename?.reviewed_name||file?.reviewed_name;
  const label=({deleted:'Deleted - absence verified',already_absent:'Already absent - app entry removed',not_started:'Not attempted',prepared:'Not attempted',executing:'Checking Dropbox',uncertain:'Result needs checking',present:'File present - ready for a new review',rejected:'Not deleted - needs another check'})[r.state]||r.state;
  const diagnostic=r.check_error||r.delete_error;
  const detail=diagnostic?'<br>'+esc((r.check_error?'Status check: ':'Original request: ')+diagnostic.error_code+(diagnostic.request_id?' · Dropbox request '+diagnostic.request_id:'')):'';
  return `<p class="small">${esc(name)}${reviewed&&reviewed!==name?'<br>Reviewed as: '+esc(reviewed):''}<br>${esc(label)}${r.message?' · '+esc(r.message):''}${r.resolved_by_operation_id?'<br>Completed by a later confirmed deletion; original attempt retained in Deletion history.':''}${detail}${rename?'<br>Verified filename change; original deletion confirmation retained.':''}</p>`;
}
function renderNativeJobs(){
  const dialog=$('#jobs-dialog'),s=nativeJobStatus;
  const scroll=dialog.scrollTop,expanded=new Set([...dialog.querySelectorAll('.native-job details[open]')].map(el=>el.closest('[data-job-id]').dataset.jobId));
  const focused=document.activeElement,focusJob=focused?.closest?.('[data-job-id]')?.dataset.jobId;
  const focusAction=focused?.closest?.('#jobs-dialog')&&[...focused.attributes].find(a=>a.name.startsWith('data-'));
  nativeJobDialogSignature=nativeJobsSignature();
  dialog.innerHTML=`<button class="close" data-close="jobs-dialog" aria-label="Close background jobs">×</button><span class="eyebrow">BACKGROUND WORK</span><h2>Dropbox jobs</h2><p>You can close this window and keep reviewing. Up to three file checks run together. Confirmed Dropbox changes run in order while the local app server is running.</p><p id="jobs-status" class="filename-progress-warning" role="status">${esc(nativeJobsStatusText())}</p><div id="filename-job-section">${filenameJobSection(s)}</div>${s.jobs.map(job=>{
    if(job.kind==='delete_review')return `<section class="operation-row native-job" data-job-id="${esc(job.id)}"><div><strong>${esc(job.label)}</strong><p>${['queued','running'].includes(job.state)?(job.retry_at?'Waiting before remaining checks':'Checking files'):job.state==='review_attention'?'Some checks need attention':job.state==='cancelled'?'Checks stopped - finished results are saved':'Ready for your confirmation'}</p>${deletionReviewProgress(job)}<small class="muted">${esc(new Date(job.updated_at).toLocaleString())}</small></div><div><button class="button" data-open-deletion-review="${esc(job.id)}">Open review</button>${job.counts.failed||job.state==='cancelled'?`<button class="button" data-retry-deletion-review="${esc(job.id)}">${job.state==='cancelled'?'Resume checks':'Retry failed checks'}</button>`:''}${['queued','running'].includes(job.state)?`<button class="button" data-cancel-deletion-review="${esc(job.id)}">Stop checks</button>`:''}</div></section>`;
    const progress=job.progress?.results||job.result?.results||[],done=progress.filter(r=>['deleted','already_absent'].includes(r.state)).length;
    const file=job.result?.file,path=file?.path;
    return `<section class="operation-row native-job" data-job-id="${esc(job.id)}"><div><strong>${esc(job.label)}</strong><p><span class="chip">${esc(nativeJobLabel(job.state))}</span>${progress.length?' '+done+' of '+progress.length+' verified':''}</p>${job.skipped?.length?`<p>${job.skipped.length} file(s) skipped because they already had a job or were retained as keepers.</p>`:''}${job.message?`<p>${esc(job.message)}</p>`:''}${job.state==='queued'&&s.reservation?'<p class="small muted">Waiting for the current Dropbox writer.</p>':''}${path?`<p><a href="https://www.dropbox.com/preview${encodeURI(path).replaceAll('#','%23').replaceAll('?','%3F')}" target="_blank" rel="noopener">Image ↗</a> · <a href="https://www.dropbox.com/home${encodeURI(path.slice(0,path.lastIndexOf('/'))).replaceAll('#','%23').replaceAll('?','%3F')}" target="_blank" rel="noopener">Folder ↗</a></p>`:''}${progress.length?`<details><summary>File results</summary>${progress.map(r=>deletionResultHTML(job,r)).join('')}</details>`:''}<small class="muted">${esc(new Date(job.updated_at).toLocaleString())}</small></div>${job.state==='uncertain'?`<button class="button" data-check-job="${esc(job.id)}">Check result</button>`:''}${job.can_review_remaining?`<button class="button" data-review-job-remaining="${esc(job.id)}">Review remaining files</button>`:''}${job.can_resume_rename?`<button class="button" data-resume-rename-job="${esc(job.id)}" title="Recheck the verified filename change and resume the deletion you already approved">Resume after verified rename</button>`:''}${job.state==='queued'?`<button class="button" data-cancel-job="${esc(job.id)}">Cancel queued job</button>`:''}${['needs_review','cancelled'].includes(job.state)&&job.asset_id?`<button class="button" data-replan-job="${esc(job.id)}">Plan again</button><button class="button" data-job-components="${esc(job.asset_id)}">Choose components</button>`:''}</section>`;
  }).join('')||(!nativeJobsLoaded?'':(s.reservation||s.filename_job)?'<p>No additional file jobs queued.</p>':'<p>No background jobs yet.</p>')}`;
  for(const el of dialog.querySelectorAll('.native-job details'))if(expanded.has(el.closest('[data-job-id]').dataset.jobId))el.open=true;
  if(focused?.tagName==='SUMMARY'&&focusJob){
    [...dialog.querySelectorAll('.native-job')].find(el=>el.dataset.jobId===focusJob)?.querySelector('summary')?.focus({preventScroll:true});
  }else if(focusAction){
    [...dialog.querySelectorAll('button')].find(el=>el.getAttribute(focusAction.name)===focusAction.value)?.focus({preventScroll:true});
  }
  dialog.scrollTop=scroll;
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
      if(typeof refreshBulkReview==='function')await refreshBulkReview();
      if($('#jobs-dialog').open&&nativeJobDialogSignature!==nativeJobsSignature()&&!$('#jobs-dialog').querySelector('button:disabled'))renderNativeJobs();
      else if($('#jobs-dialog').open&&$('#filename-job-section'))$('#filename-job-section').innerHTML=filenameJobSection(nativeJobStatus);
      for(const job of nativeJobStatus.jobs){
        if(job.kind==='delete_review')continue;
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
    }catch(error){nativeJobsError='Could not refresh jobs: '+error.message;renderNativeJobButton();if($('#jobs-dialog').open&&$('#jobs-status'))$('#jobs-status').textContent=nativeJobsStatusText();return null;}
    finally{nativeJobsRequest=null;}
  })();
  return nativeJobsRequest;
}
async function refreshNativeView(){
  if(!syncCanRefresh())return false;
  const pid=state.pid,request=state.request,writeEpoch=state.writeEpoch,pageScroll=window.scrollY,scroll=$('#main').scrollTop;
  const boot=await api('/api/bootstrap');
  const payload=['__family__','__specifications__'].includes(pid)?null:await api(pid==='__library__'?libraryAPI():'/api/products/'+encodeURIComponent(pid));
  if(pid!==state.pid||request!==state.request||writeEpoch!==state.writeEpoch||!syncCanRefresh())return false;
  state.boot=boot;absorb(boot.assignments||[]);
  for(const p of boot.products)if(p.review.version)state.reviews.set(key('product',p.id,''),p.review);
  if(payload){absorb(payload.reviews);if(pid==='__library__')state.library=payload;else state.current=payload;}
  renderList();if(pid==='__family__'||state.tab==='images'){renderMain();$('#main').scrollTop=scroll;window.scrollTo(0,pageScroll);}
  nativeViewNeedsRefresh=false;
  return true;
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
  for(const [key,route] of [['cancelJob','cancel'],['replanJob','replan'],['resumeRenameJob','resume-rename']])if(b.dataset[key]){b.disabled=true;try{await api('/api/jobs/'+route,{job_id:b.dataset[key]});await pollNativeJobs();renderNativeJobs();}catch(error){toast(error.message,true);}finally{b.disabled=false;}}
  if(b.dataset.jobComponents){$('#jobs-dialog').close();openComponents(b.dataset.jobComponents);}
  if(b.dataset.reviewJobRemaining){b.disabled=true;try{const review=await api('/api/jobs/review-remaining',{job_id:b.dataset.reviewJobRemaining});$('#jobs-dialog').close();await openSavedDeletionReview(review.id);await pollNativeJobs();}catch(error){toast(error.message,true);}finally{b.disabled=false;}}
  if(b.dataset.openDeletionReview){$('#jobs-dialog').close();await openSavedDeletionReview(b.dataset.openDeletionReview);}
  for(const [key,route] of [['retryDeletionReview','retry'],['cancelDeletionReview','cancel']])if(b.dataset[key]){b.disabled=true;try{await api('/api/deletion-reviews/'+route,{review_id:b.dataset[key]});await pollNativeJobs();renderNativeJobs();}catch(error){toast(error.message,true);}finally{b.disabled=false;}}
});
