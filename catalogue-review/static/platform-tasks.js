'use strict';
const platformStateLabels={action:'Tasks',waiting:'Waiting',verified:'Checked',unknown:'Check needed',not_targeted:'Not targeted'};
function platformTaskBadges(product){
  const status=product?.platform_tasks;
  if(!status)return '<span class="platform-status-unavailable">Platform checks not loaded</span>';
  return `<span class="platform-badges">${status.platforms.map(p=>`<span class="platform-badge platform-${esc(p.state)}" title="${esc(p.label+': '+(p.open_count?p.open_count+' outstanding task(s)':platformStateLabels[p.state]))}">${esc(p.label)} <b>${p.open_count||esc(platformStateLabels[p.state])}</b></span>`).join('')}</span>`;
}
function platformTaskSection(product,context='component'){
  const status=product?.platform_tasks;
  return `<details class="platform-checklist" id="platform-checklist-${esc(context)}-${esc(product.id)}" data-platform-product="${esc(product.id)}" data-platform-context="${esc(context)}"><summary><span class="platform-checklist-title">Platform tasks${status?' · '+status.open_count:''}</span>${platformTaskBadges(product)}</summary><div class="platform-task-content"></div></details>`;
}
function platformTaskContent(status){
  if(!status)return '<p>Platform checks have not loaded. Refresh this component to obtain its current tasks.</p>';
  return `<p class="platform-task-basis">These are dated platform observations. A saved product, a working feed and a public listing are separate checks. Changes to catalogue details or selected photos require another sync and readback.</p>${status.source_error?`<p class="platform-task-error" role="status">${esc(status.source_error)}</p>`:''}${status.platforms.map(p=>`<section class="platform-task-group"><h4>${esc(p.label)} <span class="platform-badge platform-${esc(p.state)}">${esc(platformStateLabels[p.state])}</span></h4>${p.checked_at?`<p class="platform-task-date">Checked ${esc(new Date(p.checked_at).toLocaleString())}</p>`:'<p class="platform-task-date">No dated check</p>'}${p.summary?`<p>${esc(p.summary)}</p>`:''}${p.tasks.length?`<ul>${p.tasks.map(t=>`<li><strong>${esc(t.title)}</strong> <span class="platform-task-state">${esc(platformStateLabels[t.state])}</span><p>${esc(t.detail)}</p>${t.url?`<a href="${safeURL(t.url)}" target="_blank" rel="noopener">Open ${esc(p.label)} action ↗</a>`:''}</li>`).join('')}</ul>`:p.state==='verified'?'<p>The recorded checks passed. Recheck after the next relevant catalogue update.</p>':'<p>No individual task details have been recorded. Verify this product before treating it as complete.</p>'}</section>`).join('')}`;
}
function productWithPlatformTasks(pid,context){
  if(context==='overview'&&typeof overviewPayload!=='undefined'&&overviewPayload?.product.id===pid)return overviewPayload.product;
  if(context==='specifications')return state.specifications?.products.find(p=>p.id===pid);
  return state.current?.id===pid?state.current:state.boot?.products.find(p=>p.id===pid);
}
function fillPlatformTaskDetails(details){
  if(!details?.open)return;
  const product=productWithPlatformTasks(details.dataset.platformProduct,details.dataset.platformContext);
  const root=$('.platform-task-content',details);if(root)root.innerHTML=platformTaskContent(product?.platform_tasks);
}
document.addEventListener('toggle',e=>{if(e.target.matches?.('.platform-checklist'))fillPlatformTaskDetails(e.target);},true);
