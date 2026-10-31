const PhotoReview = (() => {
  const schema = 'boldstone-wall-photo-decisions-v1';
  const actions = {
    '': 'Not decided', keep_current: 'Keep in its current Dropbox folder',
    copy_to_wall: 'Add a copy to a Wall Sculptures folder', move_to_wall: 'Move the Dropbox copy to a Wall Sculptures folder',
    keep_reference: 'Keep for advertising / reference', exclude: 'Exclude from the catalogue',
    duplicate: 'Duplicate - use another photograph', check: 'Needs further checking'
  };
  const types = {product:'Product / individual',in_situ:'In situ',group:'Group / series',detail:'Detail / close-up',rear:'Rear / fixing',workshop:'Workshop / process',design_reference:'Design / finish reference',mockup:'Mockup',packaging:'Packaging',other:'Other'};
  const uses = {listing:'Listing',advertising:'Advertising',reference:'Reference'};
  const groups = {missing:'Recorded original missing',unmatched:'No recorded Dropbox match',elsewhere:'Found in other Dropbox folders',wall:'Found in Wall Sculptures folders'};
  const text = (v,n=8000) => typeof v === 'string' ? v.slice(0,n) : '';
  const unique = (a,valid) => [...new Set(Array.isArray(a)?a:[])].filter(v=>typeof v==='string'&&valid.has(v));
  function clean(value,productIds){
    const v=value&&typeof value==='object'?value:{};
    const result={action:Object.hasOwn(actions,v.action)?v.action:'',uses:unique(v.uses,new Set(Object.keys(uses))),types:unique(v.types,new Set(Object.keys(types))),components:unique(v.components,productIds),primary_for:[],destination:text(v.destination,1500),replacement:text(v.replacement,1500),notes:text(v.notes),updated_at:!Number.isNaN(Date.parse(v.updated_at))?v.updated_at:''};
    result.primary_for=unique(v.primary_for,new Set(result.components));
    if(result.primary_for.length&&!result.uses.includes('listing'))result.uses.push('listing');
    if(['exclude','duplicate'].includes(result.action)){result.uses=[];result.primary_for=[];}
    return result;
  }
  function detailsNeeded(row,d){
    const issues=[];
    if(['copy_to_wall','move_to_wall'].includes(d.action)&&!d.components.length&&!d.destination.trim())issues.push('Choose a component folder or enter a destination.');
    if(d.uses.includes('listing')&&!d.components.length)issues.push('Choose the component(s) for listing use.');
    if(d.action==='duplicate'&&!d.replacement.trim())issues.push('Identify the photograph to keep.');
    if(['keep_current','move_to_wall'].includes(d.action)&&!row.locations.length)issues.push('No current Dropbox copy is recorded; choose another action or locate it first.');
    return issues;
  }
  const complete=(row,d)=>!!d.action&&d.action!=='check'&&!detailsNeeded(row,d).length;
  const edited=d=>!!(d.action||d.uses.length||d.types.length||d.components.length||d.destination||d.replacement||d.notes);
  function matches(row,d,filters,productById){
    if(filters.group==='attention'&&row.group==='wall')return false;
    if(!['all','attention'].includes(filters.group)&&row.group!==filters.group)return false;
    if(filters.product&&!row.old_products.some(p=>p.id===filters.product))return false;
    if(filters.review==='undecided'&&d.action)return false;
    if(filters.review==='recorded'&&!d.action)return false;
    if(filters.review==='check'&&d.action!=='check')return false;
    if(filters.review==='incomplete'&&!detailsNeeded(row,d).length)return false;
    if(filters.review==='edited'&&!edited(d))return false;
    if(filters.tag){const [kind,key]=filters.tag.split(':');if(!(kind==='use'?d.uses:d.types).includes(key))return false;}
    if(filters.search){
      const hay=[row.title,row.filename,row.url,...row.locations.map(m=>m.path),...row.app_associations.map(a=>a.title),...d.components.map(id=>productById[id]?.title||''),d.notes,d.destination,d.replacement,...d.uses,...d.types].join(' ').toLocaleLowerCase();
      if(!filters.search.toLocaleLowerCase().trim().split(/\s+/).every(s=>hay.includes(s)))return false;
    }
    return true;
  }
  function exportDocument(data,decisions){
    const ids=new Set(data.products.map(p=>p.id));
    return {schema,scope:data.scope,audit_utc:data.audit_utc,exported_utc:new Date().toISOString(),execution:'Review proposals only. No app, Dropbox or Squarespace change has been applied.',records:data.records.filter(r=>edited(clean(decisions[r.id],ids))||decisions[r.id]?.updated_at).map(r=>({id:r.id,url:r.url,title:r.title,source_group:r.group,recorded_dropbox_locations:r.locations,decision:clean(decisions[r.id],ids)}))};
  }
  function importDocument(payload,data){
    if(payload?.schema!==schema||!Array.isArray(payload.records))throw Error('This is not a Boldstone photo decision export.');
    const rows=new Map(data.records.map(r=>[r.id,r]));const ids=new Set(data.products.map(p=>p.id));const result={},primaries=new Map();
    for(const item of payload.records){
      if(!item||!rows.has(item.id)||rows.get(item.id).url!==item.url)throw Error('A photograph does not match this review. No choices were imported.');
      if(Object.hasOwn(result,item.id))throw Error('Duplicate decision entries were found. No choices were imported.');
      const d=item.decision;
      if(!d||typeof d!=='object'||!Object.hasOwn(actions,d.action))throw Error('A decision has an unsupported action.');
      for(const key of ['components','primary_for','uses','types'])if(d[key]!==undefined&&!Array.isArray(d[key]))throw Error('A decision has an invalid '+key+' list.');
      if((d.components||[]).some(id=>!ids.has(id)))throw Error('An imported component is not in this catalogue.');
      result[item.id]=clean(d,ids);
      for(const id of result[item.id].primary_for){if(primaries.has(id))throw Error('More than one photograph is proposed as primary for the same component. No choices were imported.');primaries.set(id,item.id);}
    }
    return result;
  }
  function mergeImport(existing,incoming,productIds,updatedAt){
    const result={},newPrimaries=new Set(Object.values(incoming).flatMap(d=>d.primary_for));
    for(const [id,value] of Object.entries(existing)){
      const d=clean(value,productIds),primary=d.primary_for.filter(p=>!newPrimaries.has(p));
      result[id]=primary.length===d.primary_for.length?d:{...d,primary_for:primary,updated_at:updatedAt};
    }
    for(const [id,value] of Object.entries(incoming))result[id]={...clean(value,productIds),updated_at:updatedAt};
    return result;
  }
  const safeJson=value=>JSON.stringify(value).replace(/</g,'\\u003c').replace(/\u2028/g,'\\u2028').replace(/\u2029/g,'\\u2029');
  const csvCell=value=>{let s=String(value??'');if(/^[=+@\-\t\r]/.test(s))s="'"+s;return '"'+s.replaceAll('"','""')+'"';};
  return {schema,actions,types,uses,groups,clean,detailsNeeded,complete,edited,matches,exportDocument,importDocument,mergeImport,safeJson,csvCell};
})();
