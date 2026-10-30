from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
from html import escape
import json,hashlib
b=Path('/Users/tprice/Documents/boldstone/sculpture-catalogue');j=b/'components/parallel-reviews/remaining-photo-sources-and-bordered-import-20261023T200049Z';prior=b/'components/parallel-reviews/series-gap-review-20261023T190939Z';bj=b/'components/parallel-reviews/remaining-photo-source-followup-20261023T200107Z';now=datetime.now(timezone.utc).isoformat()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ref(p):return {'path':str(p),'sha256':sha(p)}
def save(n,d):
 p=j/n;p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');return ref(p)
def files(entries):return {x['file_id']:x for x in entries if x.get('object_type')=='file'}
old=json.loads((prior/'current-family-listings.json').read_text())['families'];old['Frozen Fish']=[json.loads((prior/'frozen-fish-listing-retry.json').read_text())]
current={};sources={}
for x in json.loads((j/'current-unique-family-listings.json').read_text())['records']:
 assert x.get('isError') is not True and x['result']['has_more'] is False
 current[x['family']]=x['result']['entries'];sources[x['family']]=ref(j/'current-unique-family-listings.json')
shared=json.loads((bj/'current-family-listings.json').read_text())
for family in ['Acanthus','Egyptian Palm','Moon Crater Phase']:
 top=next(x for x in shared['family_tops'] if x['family']==family);assert top['data']['has_more'] is False
 entries=list(top['data']['entries'])
 for x in shared['option_listings']:
  if x['family']==family:
   assert x['pages'] and x['pages'][-1]['has_more'] is False
   for page in x['pages']:
    entries.extend(page['entries'])
 assert not any(x.get('object_type')=='folder' for z in shared['option_listings'] if z['family']==family for p in z['pages'] for x in p['entries'])
 current[family]=entries;sources[family]=ref(bj/'current-family-listings.json')
current['Moonphases/Moonphase 4 Silver']=json.loads((j/'current-mp4-silver-folder.json').read_text())['entries'];sources['Moonphases/Moonphase 4 Silver']=ref(j/'current-mp4-silver-folder.json')
deltas=[]
for family,entries in current.items():
 oldfam=family.split('/')[0];oldentries=[x for p in old[oldfam] for x in p['entries']]
 if '/' in family:
  prefix='ns:202238505//BOLDSTONE MASTER/Products/01 Wall Sculptures/'+family+'/'
  oldentries=[x for x in oldentries if x.get('path','').casefold().startswith(prefix.casefold())]
 before=files(oldentries);after=files(entries);add=sorted(after.keys()-before.keys());absent=sorted(before.keys()-after.keys());changes=[]
 for fid in after.keys()&before.keys():
  fields={k:{'before':before[fid].get(k),'after':after[fid].get(k)} for k in ['name','path','modified_time','client_modified'] if before[fid].get(k)!=after[fid].get(k)}
  if before[fid].get('file',{}).get('size')!=after[fid].get('file',{}).get('size'):fields['size']={'before':before[fid].get('file',{}).get('size'),'after':after[fid].get('file',{}).get('size')}
  if fields:changes.append({'file_id':fid,'changes':fields})
 deltas.append({'scope':family,'current_file_count':len(after),'prior_file_count':len(before),'added_file_ids':add,'absent_file_ids':absent,'metadata_changes':changes,'source':sources[family],'all_original_bytes_rehashed':False})
# Shared listings and unique five-family recursive listings cover eight full relevant families;
# the only Moonphases residual target receives an exact 30-file direct-folder delta.
assert all(not x['added_file_ids'] and not x['absent_file_ids'] and not x['metadata_changes'] for x in deltas),deltas
pewter=files(current['Acanthus/Acanthus One Leaf Pewter']);assert set(pewter)=={'id:cnqzTNngPVsAAAAAAAufFw','id:cnqzTNngPVsAAAAAAA6VmA'}
delta={'schema':'boldstone.residual-photo-source-delta.v1','recorded_utc':now,'status':'NO_NEW_OR_CHANGED_SOURCE_METADATA_IN_SCOPED_CURRENT_FOLDERS','source_scope':'Eight relevant full families plus exact MP4 Silver and Pewter folders. Current metadata and file IDs compared with prior complete inventories and qualified visual reviews. No claim of global source absence or unchanged file bytes across every source.','prior_full_series_review':ref(prior/'review-findings.json'),'prior_full_series_verification':ref(prior/'verification.json'),'deltas':deltas,'series_options_reviewed':17,'new_series_bindings':0,'new_original_downloads':0,'new_physical_photographs_taken':0,'native_or_platform_writes':0,'pewter_current_individual_reference_already_available':True,'pewter_group_and_context_missing':True,'historical_pewter_lookup_errors_not_retried':True,'fresh_crossfolder_review':ref(bj/'metadata-delta-review.json')}
dref=save('residual-source-delta-review.json',delta)
ptr=json.loads((b/'current-master.json').read_text());reg=json.loads((b/ptr['register']).read_text());audit=json.loads(Path(reg['latest_image_coverage_audit']['path']).read_text());cov={x['option_id']:x for x in audit['coverage']};options={x['product_id']:x for x in reg['options']}
closed={'BSI-65A93033A200','BSI-4515726BBC18'};holds={'BSI-9299D69FEF08','BSI-AF88EAA8EBC0','BSI-04D6E8690F30','BSI-22DA74B2107E','BSI-C87B4CF945C7','BSI-1B20DCA291BB','BSI-67B24409A253','BSI-65520F070145'}
seriesprior={x['option_id']:x for x in json.loads((prior/'review-findings.json').read_text())['residual_tasks']}
requests=[]
for oid,c in cov.items():
 if oid in holds or oid in closed or oid not in reg['active_option_ids']:continue
 roles=[]
 if c['in_situ']['status']=='No verified image':roles.append('Display/context')
 if c['series']['status']=='No verified image':roles.append('Series')
 if not roles:continue
 o=options[oid];r=c['individual']['reference'];assert r and r['file_id']==o['file_id']
 required=[]
 if 'Display/context' in roles:required.append('One whole photograph showing the complete exact design/finish in a visible display setting. A staged display is acceptable when labelled; scene origin remains unverified without source evidence.')
 if 'Series' in roles:required.append('One whole group photograph showing this exact design/finish with at least one clearly identifiable companion. Give this panel’s position and the names of the other pieces; an isolated panel or finish/detail crop does not fill the group role.')
 if oid=='BSI-3635E3DC3434':
  required=['Find an existing current Master whole group/display photograph or take one showing the complete One Leaf Left Pewter panel beside identifiable companion sculptures with the display background visible. Identify the Pewter panel’s position. One suitable photograph can fill both roles; the existing individual PNG is already accepted.']
 request={'option_id':oid,'name':o['name'],'family':c['family'],'missing_roles':roles,'roles_count':len(roles),'existing_individual_reference':r,'requested_photograph':required,'current_status':'EXACT_CURRENT_SOURCE_REQUIRED','display_scene_origin':'UNVERIFIED_UNLESS_SOURCE_RECORDS_PROVIDED','native_source_creation_by_agent':False,'all_prior_hold_and_identity_cases_excluded':True,'qualification':'Searches were bounded. A source not found in the checked folders may exist elsewhere; do not mark the image Available without checking an exact current source.'}
 if oid in seriesprior:request['retained_series_review_finding']=seriesprior[oid]['next_required_input']
 requests.append(request)
requests.sort(key=lambda x:(x['option_id']!='BSI-3635E3DC3434',x['family'].casefold(),x['name'].casefold()))
counts=Counter(role for x in requests for role in x['missing_roles']);assert counts=={'Display/context':16,'Series':17},counts
packet={'schema':'boldstone.residual-photo-capture-brief.v1','recorded_utc':now,'status':'READY_FOR_PHYSICAL_SOURCE_CAPTURE_OR_EXACT_EXISTING_SOURCE_LINK','expected_after_bordered_import':True,'counts':{'option_records':len(requests),'missing_roles':sum(counts.values()),'display_context':16,'series':17,'held_context_cases_excluded':8,'legacy_identity_case_excluded':1},'source_review':dref,'already_selected_bordered_displays':ref(j/'bordered-display-reference-decisions.json'),'requests':requests,'photograph_handoff':'Provide the whole original photo in BOLDSTONE MASTER and its exact filename or direct image link. A local computer agent cannot physically stage or photograph an absent sculpture. No generated image, crop or composite is offered as a source photograph.','platform_or_native_writes':0}
reqref=save('remaining-photograph-requests.json',packet)
parts=['<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Remaining sculpture photographs</title><style>body{max-width:1040px;margin:32px auto;padding:0 20px;font:17px/1.5 system-ui;color:#252525;background:#f8f6f1}article{background:white;padding:20px 24px;margin:18px 0;border:1px solid #ded8cc;border-radius:12px}a{color:#135d6d}.tag{display:inline-block;background:#e5eff0;padding:3px 9px;border-radius:6px;margin:0 6px 6px 0}.small{font-size:14px;color:#57524c}h1{font-size:30px}h2{font-size:21px}</style><h1>Remaining sculpture photographs</h1><p>After the two bordered Moonphase display associations: <strong>16 display/context roles and 17 series roles</strong> across '+str(len(requests))+' sculpture options still need exact photographs. Eight held context cases and one legacy identity case are excluded from this capture list.</p><p>Start with One Leaf Left — Pewter. One whole group/display photograph can fill both of its roles. The existing individual photograph is already accepted.</p><p class="small">Checked current Master source metadata and prior visual reviews; no global absence claim. Whole source images only. Staged displays may be labelled as such; photographs alone do not certify physical specifications or genuine client installation.</p>']
for x in requests:
 r=x['existing_individual_reference'];parts.append('<article id="'+escape(x['option_id'])+'"><h2>'+escape(x['name'])+'</h2><p>'+''.join('<span class="tag">'+escape(role)+'</span>' for role in x['missing_roles'])+'</p><p><a href="'+escape(r['image_url'],quote=True)+'">Existing individual image</a> · <a href="'+escape(r['folder_url'],quote=True)+'">Containing folder</a></p>'+''.join('<p>'+escape(t)+'</p>' for t in x['requested_photograph'])+'<p class="small">'+escape(x['option_id'])+' · Exact design and finish required. Supply a filename or direct image link when ready.</p></article>')
parts.append('<p>Save new whole originals in BOLDSTONE MASTER, then supply the filename or direct image link for review.</p></html>');html=j/'remaining-photograph-requests.html';html.write_text('\n'.join(parts)+'\n')
manifest=save('source-review-and-capture-manifest.json',{'recorded_utc':now,'status':'CURRENT_SOURCE_REVIEW_COMPLETE_SUPPORTED_TWO_ROLE_PACKET_SEALED_RESIDUAL_SOURCE_INPUT_REQUIRED','files':[dref,reqref,ref(html),ref(j/'bordered-display-packet-seal.json')],'counts':packet['counts'],'canonical_workbook_writes_by_this_lane':0,'native_or_platform_writes':0})
print(json.dumps({'delta':dref,'requests':reqref,'html':ref(html),'manifest':manifest,'counts':packet['counts']}))
