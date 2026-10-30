'use strict';
let costEditor=null,costOpening=0;
const costMoney=value=>'£'+Number(value).toLocaleString('en-GB',{minimumFractionDigits:2,maximumFractionDigits:2});
function costSummary(cost,pid){
  if(!cost)return '';
  if(cost.status!=='calculated')return `<section class="cost-summary"><h4>Manufacturing cost</h4><p>${esc(cost.message)}</p></section>`;
  return `<section class="cost-summary"><div class="section-title"><h4>Manufacturing cost <strong>${costMoney(cost.total_cost)}</strong></h4><button class="button" data-cost-product="${esc(pid)}">Costs &amp; alternatives</button></div><p class="small">${esc(cost.material_label)} · ${cost.finish_lines.map(f=>esc(f.label)+(f.coverage<1?' ('+Math.round(f.coverage*100)+'%)':'')).join(' + ')}</p><dl class="overview-fields">${[['Casting',cost.material_cost],['Surface effects',cost.finish_cost],['Fixings ('+cost.inputs.fixing_count+')',cost.fixing_cost],['Overheads',cost.overhead_cost],['Other parts',cost.other_cost],['Labour ('+cost.labour_hours.toFixed(2)+' h)',cost.labour_cost]].map(([k,v])=>`<div class="overview-field"><dt>${esc(k)}</dt><dd>${costMoney(v)}</dd></div>`).join('')}</dl><p class="small muted">Calculated production scenario. Selling price is separate. Rates, quantities and labour are editable.</p></section>`;
}
function costAlternatives(cost,config){return `<dl class="overview-fields">${Object.entries(cost.alternatives||{}).map(([k,total])=>`<div class="overview-field"><dt>${esc(config.materials[k].label)}</dt><dd>${costMoney(total)}</dd></div>`).join('')}</dl>`;}
function costNumber(label,name,value,min=0,step='any'){
  return `<label>${esc(label)}<input type="number" name="${name}" value="${value===null?'':esc(value)}" min="${min}" step="${step}"${value===null?'':' required'}></label>`;
}
function ensureCostDialog(){
  let dialog=$('#cost-dialog');if(dialog)return dialog;
  dialog=document.createElement('dialog');dialog.id='cost-dialog';dialog.className='cost-dialog';dialog.setAttribute('aria-label','Manufacturing costs');document.body.append(dialog);
  dialog.addEventListener('cancel',e=>{e.preventDefault();closeCosts();});return dialog;
}
function closeCosts(){
  if(costEditor?.saving)return;
  if(costEditor?.dirty&&!window.confirm('Discard unsaved cost changes?'))return;
  costOpening++;costEditor=null;state.dirty.delete('cost-editor');$('#cost-dialog').close();
}
async function openCosts(pid=''){
  if(costEditor?.dirty){toast('Save or close the current cost editor first.',true);return;}
  const request=++costOpening,dialog=ensureCostDialog();
  dialog.innerHTML='<button class="close" data-cost-close aria-label="Close costs">×</button><p>Loading current costs…</p>';
  if(!dialog.open)dialog.showModal();
  try{
    const [rates,product]=await Promise.all([api('/api/costs'),pid?api('/api/products/'+encodeURIComponent(pid)):Promise.resolve(null)]);
    if(request!==costOpening||!dialog.open)return;
    costEditor={pid,product,rates,dirty:false,saving:false};renderCostEditor();
  }catch(error){if(request===costOpening)dialog.innerHTML=`<button class="close" data-cost-close>×</button><p role="alert">${esc(error.message)}</p>`;}
}
function costRateRow(group,key,item){
  return `<tr data-rate-group="${group}" data-rate-key="${esc(key)}"><td><input aria-label="Rate name" name="label" value="${esc(item.label)}" required><small>${esc(key)}</small></td><td><input aria-label="Cost per reference sculpture" name="rate" type="number" min="0" step="0.01" value="${item.rate}" required></td><td><input aria-label="Additional labour minutes" name="minutes" type="number" min="0" step="any" value="${item.minutes}" required></td><td><textarea aria-label="Rate basis" name="basis">${esc(item.basis)}</textarea><input aria-label="Source URL" name="source" value="${esc(item.source)}">${item.source?`<a href="${safeURL(item.source)}" target="_blank" rel="noopener">Source ↗</a>`:''}</td></tr>`;
}
function renderCostEditor(){
  const e=costEditor,c=e.rates.settings,p=e.product,v=p?.costing,dialog=$('#cost-dialog');
  const rates=()=>`<h3>Shared cost rates</h3><p>Changing these rates recalculates every component. Costs are per reference sculpture (${c.reference_height_cm} x ${c.reference_width_cm} x ${c.reference_depth_cm} cm). Surface rates are per reference face, including the allowances in their basis.</p><div class="cost-inputs">${costNumber('Reference width (cm)','reference_width_cm',c.reference_width_cm,.01)}${costNumber('Reference height (cm)','reference_height_cm',c.reference_height_cm,.01)}${costNumber('Reference depth (cm)','reference_depth_cm',c.reference_depth_cm,.01)}${costNumber('Labour (£/hour)','labour_hourly',c.labour_hourly)}${costNumber('Casting labour (minutes at reference size)','casting_minutes',c.casting_minutes)}${costNumber('Labour per fixing (minutes)','fixing_minutes',c.fixing_minutes)}${costNumber('Cost per fixing (£)','fixing_unit',c.fixing_unit)}${costNumber('Overhead at reference size (£)','overhead_reference',c.overhead_reference)}</div>${['materials','finishes'].map(group=>`<h4>${group==='materials'?'Casting materials':'Surface effects'}</h4><div class="cost-table-wrap"><table class="cost-rates"><thead><tr><th>Name</th><th>£ / reference</th><th>Extra minutes</th><th>Calculation basis / source</th></tr></thead><tbody id="cost-${group}">${Object.entries(c[group]).map(([key,item])=>costRateRow(group,key,item)).join('')}</tbody></table></div><button class="button" type="button" data-add-cost-rate="${group}">Add ${group==='materials'?'material':'surface effect'}</button>`).join('')}<label>Model notes<textarea name="model_notes">${esc(c.notes)}</textarea></label>`;
  const product=()=>{const i=v.inputs;return `<div id="cost-result">${costSummary(v,e.pid)}</div><div class="cost-inputs">${costNumber('First face dimension (cm)','width_cm',i.width_cm,.01)}${costNumber('Second face dimension (cm)','height_cm',i.height_cm,.01)}${costNumber('Depth (cm)','depth_cm',i.depth_cm,.01)}${costNumber('Footprint factor (rectangle 1, circle 0.7854)','shape_factor',i.shape_factor,.000001)}${costNumber('Casting volume factor','casting_factor',i.casting_factor,.000001)}<label>Production material<select name="material">${Object.entries(c.materials).map(([k,m])=>`<option value="${k}"${i.material===k?' selected':''}>${esc(m.label)}</option>`).join('')}</select></label>${costNumber('Fixing quantity','fixing_count',i.fixing_count,0,1)}${costNumber('Labour hours override (blank = calculated)','labour_hours_override',i.labour_hours_override)}${costNumber('Other parts (£)','other_cost',i.other_cost)}</div><h4>Surface effects - choose all that apply</h4><p>Coverage 1 = the whole face; 0.5 = half. Overlapping layers can total more than 1. Verdigris includes its copper base, so a second copper charge is only needed for an additional treatment.</p><div class="cost-finishes">${Object.entries(c.finishes).map(([k,f])=>{const selected=i.finishes.find(x=>x.id===k);return `<label><input type="checkbox" name="finish" value="${k}"${selected?' checked':''}>${esc(f.label)}<input type="number" aria-label="${esc(f.label)} coverage" data-cost-coverage="${k}" min="0" max="5" step="any" value="${selected?.coverage??1}"></label>`;}).join('')}</div><label>Calculation notes<textarea name="notes">${esc(i.notes)}</textarea></label><p class="small">Casting scales with relative face area x depth x casting factor. Surface costs scale with face area and coverage. Overheads scale with the square root of face area, with a £${c.overhead_reference} minimum. Labour includes casting, surface work and fixings; the override replaces all calculated hours.</p><button class="button" type="button" data-cost-preview>Recalculate preview</button><details><summary>Material alternatives at the same size and finish</summary><div id="cost-alternatives">${costAlternatives(v,c)}</div><p>Moulding paste requires a rigid support and layered construction. These totals compare costs, not structural suitability. Changing production material does not rewrite the recorded sculpture specification.</p></details><button class="text-button" type="button" data-cost-settings>Open shared rates after saving or closing</button>`;};
  dialog.innerHTML=`<button class="close" data-cost-close aria-label="Close costs">×</button><span class="eyebrow">MANUFACTURING COSTS · GBP</span><h2>${esc(p?.name||'Materials, surface effects & labour')}</h2><p>${esc(c.notes)}</p><form id="cost-form">${p&&v.status==='calculated'?product():rates()}<div class="cost-save"><button class="button dark" type="submit">${p?'Save component costs':'Save rates for all sculptures'}</button><span id="cost-status" role="status"></span></div></form>`;
  e.formBaseline=formSnapshot($('#cost-form'));
}
function costFormData(){
  const e=costEditor,form=$('#cost-form'),f=new FormData(form);
  if(e.pid){return {width_cm:Number(f.get('width_cm')),height_cm:Number(f.get('height_cm')),depth_cm:Number(f.get('depth_cm')),shape_factor:Number(f.get('shape_factor')),casting_factor:Number(f.get('casting_factor')),material:f.get('material'),fixing_count:Number(f.get('fixing_count')),labour_hours_override:f.get('labour_hours_override')?.trim()?Number(f.get('labour_hours_override')):null,other_cost:Number(f.get('other_cost')),notes:f.get('notes'),finishes:f.getAll('finish').map(id=>({id,coverage:Number(form.querySelector('[data-cost-coverage="'+id+'"]').value)}))};}
  const data=JSON.parse(JSON.stringify(e.rates.settings));
  for(const key of ['reference_width_cm','reference_height_cm','reference_depth_cm','labour_hourly','casting_minutes','fixing_minutes','fixing_unit','overhead_reference'])data[key]=Number(f.get(key));
  for(const row of $$('[data-rate-group]',form)){
    const val=name=>row.querySelector('[name="'+name+'"]').value;
    data[row.dataset.rateGroup][row.dataset.rateKey]={label:val('label'),rate:Number(val('rate')),minutes:Number(val('minutes')),basis:val('basis'),source:val('source')};
  }
  data.notes=f.get('model_notes');return data;
}
async function previewCosts(){
  const e=costEditor;if(!e||e.saving)return;
  try{const submitted=costFormData(),result=await api('/api/costs/preview',{data:submitted,settings_version:e.rates.version});
    if(JSON.stringify(submitted)!==JSON.stringify(costFormData()))return;
    if(costEditor===e){$('#cost-result').innerHTML=costSummary(result,e.pid);$('#cost-alternatives').innerHTML=costAlternatives(result,e.rates.settings);$('#cost-status').textContent='Preview recalculated. Save to keep these inputs.';}
  }catch(error){if(costEditor===e)$('#cost-status').textContent=error.message;}
}
async function saveCosts(){
  const e=costEditor;if(!e||e.saving)return;
  e.saving=true;const form=$('#cost-form');form.querySelector('button[type=submit]').disabled=true;form.inert=true;
  state.writeEpoch++;
  const pending=api('/api/reviews',{kind:e.pid?'cost':'cost_settings',product_id:e.pid,item_id:'',version:e.pid?e.product.costing.version:e.rates.version,settings_version:e.rates.version,data:costFormData()});
  reviewRequests.add(pending);
  try{await pending;reviewRequests.delete(pending);e.dirty=false;state.dirty.delete('cost-editor');e.saving=false;
    await openCosts(e.pid);if(state.pid==='__specifications__')await refreshAllSpecifications(true);
    else if(state.pid===e.pid&&state.tab==='specs'&&!state.dirty.size)await load(state.pid,{tab:'specs'});
    toast('Manufacturing costs saved');
  }catch(error){e.saving=false;if(costEditor===e){$('#cost-status').textContent=error.message;form.querySelector('button[type=submit]').disabled=false;form.inert=false;}}
  finally{reviewRequests.delete(pending);state.writeEpoch++;}
}
document.addEventListener('click',e=>{const b=e.target.closest('button');if(!b)return;
  if(b.hasAttribute('data-cost-product'))openCosts(b.dataset.costProduct);
  if(b.hasAttribute('data-cost-settings'))openCosts();
  if(b.hasAttribute('data-cost-close'))closeCosts();
  if(b.hasAttribute('data-cost-preview'))previewCosts();
  if(b.dataset.addCostRate){const group=b.dataset.addCostRate;let n=1;while($('[data-rate-key="custom_'+n+'"]'))n++;
    $('#cost-'+group).insertAdjacentHTML('beforeend',costRateRow(group,'custom_'+n,{label:'New '+(group==='materials'?'material':'surface effect'),rate:0,minutes:0,basis:'Enter your cost and quantity basis.',source:''}));costEditor.dirty=true;state.dirty.add('cost-editor');}
});
function markCostDirty(e){if(e.target.closest('#cost-form')&&costEditor){costEditor.dirty=formSnapshot($('#cost-form'))!==costEditor.formBaseline;if(costEditor.dirty)state.dirty.add('cost-editor');else state.dirty.delete('cost-editor');$('#cost-status').textContent=costEditor.dirty?'Inputs changed - recalculate or save to update costs.':'';}}
document.addEventListener('input',markCostDirty);document.addEventListener('change',markCostDirty);
document.addEventListener('submit',e=>{if(e.target.id==='cost-form'){e.preventDefault();saveCosts();}});
