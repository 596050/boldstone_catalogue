"""Assemble reviewed image witnesses and open actions without changing approvals."""
import copy
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit, parse_qs

HERE=Path(__file__).resolve().parent
BASE=HERE.parents[2]
read=lambda p:json.loads(Path(p).read_text())
write=lambda p,d:Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
digest=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
inputs=read(HERE/'input-manifest.json')
g=read(inputs['master_register']['snapshot'])
original=copy.deepcopy(g)
model=read(inputs['source_model']['snapshot'])
manual=read(HERE/'manual-observations.json')
follow=read(HERE/'followup-observations.json')
extra=read(HERE/'group-extra-observations.json')
assets=read(HERE/'asset-index.json')
inventory=read(HERE/'live-inventory.json')
queues=[read(HERE/n) for n in ['visual-queue.json','followup-queue.json','moon-fishwave-extra-queue.json','group-extra-queue.json']]
labels={x['label']:x for q in queues for x in q}
entries={x['file_id']:x for x in inventory['entries']}
replacements={x['old_folder_id']:x['new_folder_id'] for x in inventory['completed_path_overlay']['retired_folder_replacements']}
display=lambda p:p.split('//',1)[-1] if p.startswith('ns:') else p
folder_url=lambda p:'https://www.dropbox.com/home'+quote(display(p),safe='/')

def ref(label='',file_id=''):
    file_id=file_id or labels.get(label,{}).get('file_id','')
    if not file_id:return None
    a=assets[file_id]
    return {k:a[k] for k in ['file_id','folder_id','name','path','image_url','folder_url']}|{'review_label':label}

def folder_ref(fid):
    fid=replacements.get(fid,fid)
    if fid not in entries:return None
    e=entries[fid]
    return {'folder_id':fid,'folder_url':folder_url(e['path']),'path':e['path']}

# Match old native references through previously sealed stable-ID/path histories.
path_ids={a['display_path'].casefold():fid for fid,a in assets.items()}
folder_ids={display(e['path']).casefold():fid for fid,e in entries.items() if e['object_type']=='folder'}
for a in model['assets']:
    if a['id'] in assets:path_ids[display(a['path']).casefold()]=a['id']
for filename,rowskey in [
    ('step-05-chelsea-moon-ripple-current-overlay.json','complete_old_to_current_ledger'),
    ('step-04-moon-fishwave-renames-current-overlay.json','objects')]:
    overlay=read(BASE.parent/'reports/dropbox-wall-structure-2026-10-20'/filename)
    for o in overlay[rowskey]:
        fid=o.get('current_id',o.get('file_id'))
        old=o.get('old_display_path')
        if old and fid in assets:path_ids[old.casefold()]=fid
        if old and fid in entries and entries[fid]['object_type']=='folder':folder_ids[old.casefold()]=fid

def from_url(url):
    if not url or not url.startswith('https://www.dropbox.com/'):return None
    u=urlsplit(url);p=unquote(u.path)
    for root in ['/home','/preview']:
        if p.startswith(root+'/'):p=p[len(root):];break
    name=parse_qs(u.query).get('preview',[''])[0]
    fid=path_ids.get((p+('/'+name if name else '')).casefold())
    return ref(file_id=fid) if fid else None

def current_url(url):
    if not url or not url.startswith('https://www.dropbox.com/'):return url
    r=from_url(url)
    if r:return r['image_url']
    u=urlsplit(url);p=unquote(u.path)
    for root in ['/home','/preview']:
        if p.startswith(root+'/'):p=p[len(root):];break
    f=folder_ref(folder_ids.get(p.casefold(),''))
    return f['folder_url'] if f else url

def project(r):
    if not isinstance(r,dict):return
    fid=r.get('file_id','')
    if fid in assets:
        a=ref(file_id=fid)
        for key in ['file_id','folder_id','image_url','folder_url']:
            if key in r:r[key]=a[key]
    else:
        for k in ['image_url','folder_url']:
            if k in r:r[k]=current_url(r[k])
        if r.get('folder_id') in replacements:r['folder_id']=replacements[r['folder_id']]

for key in ['components','aliases','source_review_reconciliation','original_specification_current_references']:
    for r in g[key]:project(r)
for key in ['source_sets','source_offer_edges']:
    for r in g[key]:project(r.get('current_primary_reference',{}))
for r in g['arrangement_context_references']:
    project(r)
    for im in r.get('images',[]):project(im)
overview=extra['collection_overview']
gr=g['arrangement_context_references'][20]
gr['prior_folder_only_reference']={k:gr.get(k,'') for k in ['file_id','folder_id','image_url','folder_url']}
gr.update({k:ref(overview['label'])[k] for k in ['file_id','folder_id','image_url','folder_url']})
gr['current_overview_basis']=overview['finding']

options=g['options']; opt_by_id={o['product_id']:o for o in options}
config_by_id={x['configuration_id']:x for x in model['configurations']}
cross=defaultdict(list)
for c in g['source_media_configuration_coverage']:
    for pid in c['exact_supported_target_ids']:cross[pid].append(c)
negative={i:x['finding'] for x in follow['full_scope_negative_findings'] for i in x['products']}
insitu_extra={i:x for x in follow['additional_in_situ_witnesses'] for i in x['products']}
insitu_candidates={i:x for x in follow['additional_in_situ_candidates'] for i in x['products']}
series_extra={i:x for x in follow['additional_series_witnesses'] for i in x['products']}
uncertain_context=set(manual['context_identity_or_build_unconfirmed_labels'])
series_uncertain={6,7,71,154,155,162,163}
series_source_supported={136,137,138,154,155}
coverage=[]; missing=[]; identities=[]; primary_changes=[]; context_changes=[]
scene_guard='Room/garden presentation available. Scene origin and a real installed cast are not authenticated.'

def add_identity(case,name,position,proposal,state,need,image=None,compare=None,targets=None):
    identities.append({'case_id':case,'name':name,'position':position,'proposed_identity':proposal,
        'state':state,'check':need,'reference':image,'comparison':compare,'related_option_ids':targets or [],
        'owner_decision':'','canonical_option_count_increment':0})

for i,o in enumerate(options,1):
    pl=f'P{i:03d}';cl=f'C{i:03d}';oldref={k:o.get(k,'') for k in ['file_id','folder_id','image_url','folder_url']}
    project(o)
    primary=ref(file_id=o['file_id']) if o.get('file_id') else None
    if pl in follow['single_component_alternatives']:
        new=ref(follow['single_component_alternatives'][pl]['label'])
        primary_changes.append({'option_id':o['product_id'],'old':oldref,'new':new,'basis':follow['single_component_alternatives'][pl]['finding']})
        o.setdefault('historical_primary_image_references',[]).append(oldref)
        o.update({k:new[k] for k in ['file_id','folder_id','image_url','folder_url']});primary=new
        for comp in g['components']:
            if comp.get('file_id')==oldref['file_id'] and comp['component_id']==o.get('canonical_component_id'):
                comp.update({k:new[k] for k in ['file_id','folder_id','image_url','folder_url']})
    individual='Available'
    if pl in manual['primary_complete_group_labels']:individual='Group only'
    if pl in manual['primary_detail_labels'] and pl not in follow['single_component_alternatives']:individual='Detail only'
    if not primary:individual='Unbound size'
    evidence=primary or ref('F037')
    notes=[]
    if individual=='Unbound size':notes.append('The linked White solo panel is a related design reference only. No 100 × 22 cm Long image, measured size or geometry-parent binding is asserted.')
    if individual=='Group only':notes.append('Complete component appears within a group; no verified isolated full view is bound for this option.')
    if individual=='Detail only':notes.append('Selected image is cropped; the complete component outline is not established by this image.')
    ctx=ref(cl) if cl in labels and labels[cl].get('file_id') else from_url(o.get('context_image_url',''))
    room={'status':'No verified image','reference':None,'basis':'No exact wider room/garden view verified in the reviewed source references.'}
    if cl in manual['context_full_room_or_garden_labels'] and cl not in uncertain_context:
        room={'status':'Available','reference':ctx,'basis':scene_guard}
    elif cl in uncertain_context and ctx:
        room={'status':'Verify existing image','reference':ctx,'basis':manual['context_notes'].get(cl,'Exact member, finish or build must be checked in this source image.')}
    elif ctx:
        room['basis']='Existing reference is a product wall, workshop/display, group or detail view; no exact wider room/garden view verified.'
    if i in insitu_extra:
        w=insitu_extra[i];room={'status':'Available','reference':ref(w['label']),'basis':w['setting']+'. '+scene_guard}
    elif i in insitu_candidates:
        c=insitu_candidates[i];room={'status':'Verify existing image','reference':ref(c['label']),'basis':c['reason']}
    # Complete circular depictions, not rectangular native pattern swatches.
    if i==178:room={'status':'Available','reference':ref('W147'),'basis':'Pale Blue circle in a doorway room. '+scene_guard}
    if i==179:room={'status':'Available','reference':ref('W159'),'basis':'Terracotta circular room presentation. '+scene_guard}
    series={'status':'No verified image','reference':None,'basis':'No exact series/group image verified for this finish and build in the reviewed references.'}
    if cl in manual['context_series_labels'] and ctx:
        series={'status':'Verify existing image' if i in series_uncertain else 'Available','reference':ctx,
            'basis':manual['context_notes'].get(cl,'Existing source-linked arrangement with this component; repeated positions are not additional designs or physical stock.')}
    if i in series_extra:
        w=series_extra[i];series={'status':w.get('state','Available'),'reference':ref(w['label']),'basis':w['members']}
    if i in [29,30]:series={'status':'Available','reference':ref('U018'),'basis':'White pair: Spiral at left, Cup Ring at right. Pair dimensions and price are not individual component specifications.'}
    if i in [75,76,77,78,83,86,87,93,94,95,96,97,98]:
        series={'status':'Available','reference':primary,'basis':'Existing source-linked component within its matched pair, triptych or group. Component identity is retained; stock and current cast size are not certified.'}
    if i in [6,7]:series={'status':'Verify existing image','reference':ref('G20'),'basis':'Five colour-study panels are visible. Exact Pewter/Sandstone finish positions are unbound.'}
    cfgs=[config_by_id[c['configuration_id']] for c in cross[o['product_id']]]
    required=any(c['series']!='Optional: no fixed multi-part series established' for c in cfgs) or i in [17,18,29,30,75,76,77,78]
    if i in [6,7,9,82,141,142,161,175,176,177,178,179,180,181,182]:required=False
    if not required and series['status']=='No verified image':series['status']='Optional / no fixed set'
    scope=negative.get(i,'All linked primary/context references reviewed; source-crosswalk alternate folders sampled or fully reviewed where noted. A missing bound reference is not a claim that no image exists anywhere in Dropbox.')
    if i in range(175,182):scope='All 167 current Wall Circle family files reviewed. Rectangular swatches are separated from complete circular depictions.'
    if i in [83,84,85,86,87]:scope='All 96 current Frozen Fish family files reviewed. Fin count or perspective does not verify physical size.'
    if i in [29,30]:scope='All 29 current Cup Ring family files reviewed; brown paving studies are not assigned as the White standard wall option.'
    if i in [120,121]:scope='All 41 current Moon Fishwave display/room-folder files reviewed. Current folder name is In Situ; source provenance remains unverified.'
    if cl in manual['context_notes']:notes.append(manual['context_notes'][cl])
    row={'option_id':o['product_id'],'name':o['name'],'family':o['family'],'individual':{'status':individual,'reference':evidence,'exact_option':individual!='Unbound size'},'in_situ':room,
         'series':series,'series_required':required,'notes':notes,'scope':scope,'scene_origin':'Unverified; media presence does not authenticate an installed or manufactured object','owner_review':''}
    coverage.append(row)
    if individual!='Available':
        action='Find or photograph the complete sculpture alone, with all edges visible, in this exact finish and build.'
        if i==82:action='Identify the exact 100 × 22 cm Long file or photograph that size with a scale/reference. Confirm whether it shares the Short relief geometry.'
        if i==29:action='Find or photograph the complete White Ring alone. Use the right panel in the linked White pair to identify the design; the dedicated Ring image is cropped.'
        missing.append({'priority':1,'option_id':o['product_id'],'name':o['name'],'role':'Individual','action_type':'Find / capture','action':action,'reference':evidence,'scope':scope,'qualification':individual+'; '+(' '.join(notes)), 'owner_response':'','status':'Open'})
    if room['status']!='Available':
        missing.append({'priority':2,'option_id':o['product_id'],'name':o['name'],'role':'In situ','action_type':'Verify existing image' if room['status']=='Verify existing image' else 'Find / capture',
          'action':'Confirm the exact member, finish, size/build and scene role in the linked candidate.' if room['status']=='Verify existing image' else 'Find or create a wider room/garden view of this exact option; use the linked sculpture reference to identify it.',
          'reference':room['reference'] or evidence,'scope':scope,'qualification':room['basis'],'owner_response':'','status':'Open'})
    if series['status'] not in ['Available']:
        verify=series['status'] in ['Verify existing image','Source-supported']
        missing.append({'priority':2 if required else 3,'option_id':o['product_id'],'name':o['name'],'role':'Series','action_type':'Verify existing image' if verify else 'Find / capture' if required else 'Optional image',
          'action':'Check the exact component positions and finish/build in the linked group image.' if verify else 'Find or photograph this exact option with its identified family members.' if required else 'Optional family/series image: no fixed set is established. No compulsory new photograph is inferred.',
          'reference':series['reference'] or evidence,'scope':scope,'qualification':series['basis'],'owner_response':'','status':'Open' if required or verify else 'Optional'})
    selected=room['reference'] if room['reference'] else ctx
    if selected:
        before={k:o.get(k,'') for k in ['context_image_url','context_folder_url']}
        o['context_image_url']=selected['image_url'];o['context_folder_url']=selected['folder_url'];o['context_file_id']=selected['file_id'];o['context_folder_id']=selected['folder_id']
        if before!={k:o[k] for k in before}:context_changes.append({'option_id':o['product_id'],'before':before,'after':selected,'status':room['status']})
    o['photo_coverage']={'individual':individual,'in_situ':room['status'],'series':series['status'],'audit_option_id':o['product_id']}

# Priority identity cases, followed by individually reviewable photographic positions.
add_identity('ID-FROZEN-FISH-LONG',options[81]['name'],'Unbound 100 × 22 cm option','Long size option; geometry parent unbound','Awaiting owner / exact file',
 'Does the Long use the same relief geometry as the linked White solo panel at a larger size? Which exact file depicts the 100 × 22 cm work?',ref('F037'),targets=[options[81]['product_id']])
add_identity('ID-CUP-RING',options[28]['name'],'Right member of White pair','Cup Ring (CRS2), White standard','Identity retained; isolated photo missing',
 'Find a complete isolated White Ring image; the dedicated Ring file is a crop.',ref('U018'),ref('U001'),[options[28]['product_id']])
wall_labels={175:'W001',176:'W141',177:'W002',178:'W155',179:'W160',180:'W144',181:'W166'}
for i,l in wall_labels.items():
    c=manual['wall_circle_visual_candidates'][l]
    add_identity('ID-WALL-CIRCLE-'+str(i),options[i-1]['name'],'Complete circular visual',c['candidate_native_pattern'] or 'Native pattern alias unresolved',
       'Strong visual candidate' if c['candidate_native_pattern'] else 'Unresolved',
       'Confirm the visual-name to native-pattern relationship. Pattern resemblance does not bind a diameter, lighting choice, exact SKU or physical mould.',ref(l),ref(c.get('source_swatch_label','')),[options[i-1]['product_id']])

group_positions={1:['left','right'],2:['upper left','upper middle','upper right','lower left','lower middle','lower right'],3:['left oval panel','right oval panel'],
 4:['left wavy panel','right wavy panel'],5:['left double-curl panel','right double-curl panel'],6:['upper left quarter','upper right quarter','lower left quarter','lower right quarter'],
 7:['left diagonal panel','middle half-ring panel','right half-ring panel'],8:['far-left diagonal panel','left half-ring panel','right half-ring panel','far-right diagonal panel'],
 9:['left spiral panel','right spiral panel'],10:['left looped-ridge panel','right looped-ridge panel'],11:['left fine-ridge panel','right fine-ridge panel'],12:['left spiral panel','right spiral panel'],
 13:['left multiple-spiral panel','right multiple-spiral panel'],14:['left oval-ring panel','right oval-ring panel'],15:['left twin-spiral panel','right twin-spiral panel'],
 16:['left oval/curl panel','right oval/curl panel'],17:['left concentric panel','right concentric panel'],
 18:['first, Phase 4','second, Phase 1','third, Phase 2','fourth, Phase 3','fifth, Phase 4 repeated'],
 19:['upper-shelf candidate'],20:['far-left colour study','second colour study','centre colour study','fourth colour study','far-right colour study'],
 22:['left courtyard panel'],23:['right courtyard panel'],24:['upper-left workshop position'],25:['upper-right workshop position'],26:['lower workshop position'],
 27:['left member','right member']}
for gi,positions in group_positions.items():
    gr=g['arrangement_context_references'][gi-1];w=ref(f'G{gi:02d}')
    for j,pos in enumerate(positions,1):
        proposal=gr['name']+' — '+pos
        state='Candidate position; identity unverified';need='Confirm the exact relief, same/rotated/repeated design relationships, finish, size and individual sale unit before creating any new catalogue option.'
        target=[];comparison=None
        if gi in [9,12]:need+=' G09 and G12 repeat the same visible arrangement; do not double count.'
        if gi==2:need+=' Six visible sections are not a verified count of six unique moulds.'
        if gi==4 and j==2:comparison=ref('D167');need+=' A complete isolated wavy study is available for comparison, but orientation, ridge geometry and size equivalence are unconfirmed.'
        if gi==14:comparison=ref('A067');need+=' Related Echo Extended motifs do not establish a cross-family alias.'
        if gi==18:
            oi=[131,124,126,129,131][j-1];target=[options[oi-1]['product_id']];proposal=options[oi-1]['name'];state='Existing component reused';need='Existing arrangement membership retained. The repeated Phase 4 position adds no component or physical stock claim.'
        if gi==20:need+=' White/Pewter/Sandstone names stay accepted; exact finish positions are unbound.'
        if gi in [22,23]:need+=' Distant courtyard images do not establish close individual geometry or specifications.'
        if gi in [24,25,26]:need+=' Three groups share one cropped source photograph; no new alias is inferred from a moon or spiral motif.'
        if gi==27:target=gr['confirmed_member_option_ids'];state='Existing owner-confirmed membership';need='Pair membership was already owner confirmed. Record the exact position if needed; no new owner approval or additional product is recorded.'
        add_identity(f'GROUP-{gi:02d}-{j:02d}',gr['name'],pos,proposal,state,need,w,comparison,target)
for c in extra['collection_review_cases']:
    for j,pos in enumerate(c['positions'],1):
        add_identity(f'COLLECTION-{c["label"]}-{j:02d}','Collection of sculptures',pos,'Unbound collection member — '+pos,'Candidate position; identity unverified',c['note'],ref(c['label']))
add_identity('SHELLWAVE-WATER-LOWER',options[106]['name'],'Lower panel beneath the nozzle-bearing panel','Lower context panel; separate identity unbound','Component identification needed',
 'The upper adapted Shellwave is the existing option. Identify the lower panel separately; do not allocate the whole water feature dimensions or price to it.',ref('P107'),targets=[options[106]['product_id']])

native=read(BASE/'components/parallel-reviews/wall-circle-2026-10-17/family-keep/native-pattern-image-bindings.json')
if isinstance(native,dict):
    native=native.get('patterns',native.get('bindings',native.get('rows')))
assert isinstance(native,list) and len(native)==18
wall_sources=[]
for b in native:
    variants=[v for v in g['wall_circle_native_options'] if v['image_id']==b['image']['id']]
    assert len(variants)==8
    r=ref(file_id=variants[0]['dropbox_image_candidates'][0]['file_id'])
    v={'pattern':b['pattern'],'native_image_id':b['image']['id'],'native_url':b['image']['assetUrl'],'native_sha256':b['image_sha256'],
       'reference':r,'variant_ids':[x['variant_id'] for x in variants],'skus':[x['sku'] for x in variants],
       'state':'Same pattern-image design visually confirmed','scope':'Rectangular swatch image match. No exact-byte match, diameter, lighting, circular-object alias, current stock or manufacture certification.',
       'source_snapshot_date':'2026-10-17'}
    wall_sources.append(v)
    for variant in variants:
        variant['visual_swatch_binding']={'file_id':r['file_id'],'folder_id':r['folder_id'],'image_url':r['image_url'],'state':v['state'],'scope':v['scope']}

target_order={options[81]['product_id']:-2,options[28]['product_id']:-1}
missing.sort(key=lambda r:(r['priority'],{'Individual':0,'In situ':1,'Series':2}[r['role']],target_order.get(r['option_id'],next(i for i,o in enumerate(options) if o['product_id']==r['option_id']))))
counts={'individual_options':len(coverage),'individual_statuses':dict(Counter(x['individual']['status'] for x in coverage)),
        'in_situ_statuses':dict(Counter(x['in_situ']['status'] for x in coverage)),'series_statuses':dict(Counter(x['series']['status'] for x in coverage)),
        'series_required_options':sum(x['series_required'] for x in coverage),'actions_by_role':dict(Counter(x['role'] for x in missing)),
        'actions_by_type':dict(Counter(x['action_type'] for x in missing)),'action_rows':len(missing),'identity_review_rows':len(identities),
        'native_pattern_image_bindings':18,'native_variants_covered':144,'better_complete_primary_images':len(primary_changes),
        'current_files_in_root_inventory':len(assets),'unique_dropbox_images_visually_reviewed':len({x['file_id'] for q in queues for x in q if x.get('file_id')}),
        'all_root_file_bytes_rehashed':False,'new_original_files_rehashed':14,'remote_writes':0}
audit={'schema':'boldstone.option-image-coverage.v1','recorded_utc':datetime.now(timezone.utc).isoformat(),'status':'COMPLETE_BOUNDED_EVIDENCE_AUDIT',
       'counts':counts,'coverage':coverage,'missing_pictures':missing,'identity_review':identities,'wall_circle_sources':wall_sources,
       'primary_reference_changes':primary_changes,'context_reference_changes':context_changes,
       'method':'All 184 options assessed. All selected primary and context references viewed; all Frozen Fish, Cup Ring, Wall Circle and the 227 files in group-reference folders reviewed. Other role-specific source-crosswalk folders sampled or fully reviewed as noted. Missing means no verified option-bound image within that scope.',
       'identity_guard':'No new owner approval, unique design count, measured specification, physical cast/mould, stock, availability or exact live platform SKU match is inferred from the photographs.',
       'inputs':{p.name:digest(p) for p in [HERE/'manual-observations.json',HERE/'followup-observations.json',HERE/'group-extra-observations.json',HERE/'asset-index.json']}}
assert counts['individual_statuses']=={'Available':157,'Detail only':5,'Group only':21,'Unbound size':1}
assert len({x['option_id'] for x in coverage})==184
assert len({x['case_id'] for x in identities})==len(identities)
assert g['summary']==original['summary']
assert g['original_review_specification_assertions']==original['original_review_specification_assertions']
assert all(a['master_fields']==b['master_fields'] and a['name']==b['name'] and a['product_id']==b['product_id'] for a,b in zip(original['options'],g['options']))
g['latest_image_coverage_audit']={'path':str(HERE/'image-coverage-audit.json'),'counts':counts,'scope':audit['method'],'identity_guard':audit['identity_guard']}
g['latest_chelsea_moon_ripple_current_paths']=inventory['completed_path_overlay']
g['latest_moon_fishwave_observed_folder_name']={'folder_id':'id:cnqzTNngPVsAAAAAAAyisg','current_name':'Moon Fishwave 1 and 2 White In Situ',
       'evidence':[str(HERE/'moon-fishwave-latest-metadata-0.json'),str(HERE/'moon-fishwave-latest-metadata-1.json')],'scene_provenance':'Unverified'}
write(HERE/'image-coverage-audit.json',audit)
write(HERE/'canonical-master-register.json',g)
write(HERE/'current-url-projection.json',{'file_paths':{k:v for k,v in path_ids.items()},'folder_paths':folder_ids})
print(json.dumps(counts))
