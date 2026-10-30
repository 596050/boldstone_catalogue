"""Independently check scoped identity, source, physical-field and native-link invariants."""
import copy, csv, hashlib, importlib.util, json, posixpath
from pathlib import Path
from datetime import datetime, timezone
from xml.etree import ElementTree as E
H=Path(__file__).resolve().parent;B=H.parents[2]
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
sp=importlib.util.spec_from_file_location('native_reader',B/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py');n=importlib.util.module_from_spec(sp);sp.loader.exec_module(n)
w=n.load(H/'master-workbook.pending');g=read(H/'canonical-master-register.json');old=read(H/'inputs/master_register.before');a=read(H/'image-coverage-current.json');old_a=read(H/'inputs/audit.before');native=read(H/'current-native-reference-map.json');plan=read(H/'workbook-edit-plan.json');report=read(H/'report-verification.json');out=Path(report['output_directory']);issues=[];checks=0
def check(ok,label):
 global checks
 checks+=1
 if not ok:issues.append(label)
links={}
for sn,z in w['sheets'].items():
 rp=posixpath.join(posixpath.dirname(z['part']),'_rels',posixpath.basename(z['part'])+'.rels');rs={x.get('Id'):x.get('Target')for x in E.fromstring(w['files'][rp])}
 for x in z['root'].findall('.//'+n.q('hyperlink')):links[(sn,x.get('ref'))]='#'+x.get('location')if x.get('location')else rs[x.get('{'+n.R+'}id')]
fid='id:cnqzTNngPVsAAAAAAAyluQ';parent='id:cnqzTNngPVsAAAAAAA6VrQ';scene_parent='id:cnqzTNngPVsAAAAAAAyh5w';scene_ids={'id:cnqzTNngPVsAAAAAAAyh6w','id:cnqzTNngPVsAAAAAAAyh6g'}
affected=set(read(H/'path-change-history.json')['affected_option_ids']);scene_options=set(g['latest_deco_scene_navigation_refresh']['existing_context_options_refreshed']);deferred={'BSI-9B2B466B38BE','BSI-449C4421ABD0'}
check(len(affected)==3 and scene_options=={'BSI-F61AE4921B6B'},'Exactly three004 paths and one pre-existing003 context path')
check(g['summary']==old['summary']and len(g['options'])==188 and len(g['active_option_ids'])==187,'Catalogue counts and definitions unchanged')
for key in ['components','original_review_specification_assertions','source_only_assertions_not_applied_to_options','source_sets','aliases','source_offer_edges','source_media_configuration_coverage','current_frozen_fish_size_policy','wall_sculpture_customisation_policy','source_platform_offer_coverage','retired_option_ids']:
 check(g[key]==old[key],'Immutable source/policy collection '+key)
for i,(o,b,c,bc)in enumerate(zip(g['options'],old['options'],a['coverage'],old_a['coverage']),10):
 oid=o['product_id'];check(oid==b['product_id']==c['option_id']==bc['option_id'],'Stable row identity '+oid)
 for key in ['name','canonical_key','canonical_component_id','specifications','master_fields','selling_details','image_url','folder_url','file_id','folder_id','physical_specifications_verified']:
  check(o.get(key)==b.get(key),'Accepted identity/specification/primary unchanged '+oid+' '+key)
 check(c['individual']==bc['individual']and c['series']==bc['series'],'Individual and series roles immutable '+oid)
 if oid in affected:
  check(o['context_file_id']==fid and o['context_folder_id']==parent,'004 exact current parent '+oid)
  ref=c['in_situ']['reference'];check(ref['file_id']==fid and ref['folder_id']==parent,'004 audit binding '+oid)
  check(c['in_situ']['status']==bc['in_situ']['status']and c['in_situ']['basis']==bc['in_situ']['basis'],'004 role qualification unchanged '+oid)
  for sn,col in [('Master Catalogue','U'),('Photo Coverage','H')]:check(links[(sn,col+str(i))]==ref['folder_url'],'004 paired folder native link '+oid)
  check(w['values']['Photo Coverage']['P'+str(i)]==parent,'004 workbook actual folder ID '+oid)
 elif oid in scene_options:
  check(o['context_file_id']==b['context_file_id']=='id:cnqzTNngPVsAAAAAAAyh6g'and o['context_folder_id']==b['context_folder_id']==scene_parent,'003 existing parent identity unchanged')
  ref=c['in_situ']['reference'];check('Spiral%202%20and%20Two%20Leaves%201%20and%20Acanthus%20Flower' in ref['folder_url'],'003 current folder pathname')
  check(c['in_situ']['status']==bc['in_situ']['status']and c['in_situ']['basis']==bc['in_situ']['basis'],'003 existing context qualification unchanged')
  check(links[('Master Catalogue','U'+str(i))]==ref['folder_url'],'003 workbook current containing folder')
 elif oid in deferred:
  z=copy.deepcopy(o);z.pop('current_context_owner_deferral');check(z==b,'Deferral only adds owner review metadata')
  z=copy.deepcopy(c);z['in_situ'].pop('owner_deferral');z['owner_review']=bc['owner_review'];check(z==bc,'Deferral leaves visual binding and gap intact')
 else:check(o==b and c==bc,'Entire unrelated option and coverage unchanged '+oid)
for ident in scene_ids:
 obj=native['current_objects'][ident];check(obj['parent_id']==scene_parent and obj['display_path'].rsplit('/',1)[0]==native['current_objects'][scene_parent]['display_path'],'002/003 actual same parent '+ident)
check(native['current_objects'][fid]['parent_id']==parent,'004 specific placement overrides old scene prefix')
check(native['old_path_to_id'][read(H/'path-change-history.json')['before']['display_path'].casefold()]==fid,'004 historical path alias still binds same file ID')
check(set(g['latest_deco004_path_refresh']['held_scene_file_ids'])==scene_ids and g['latest_deco_scene_navigation_refresh']['identity_state']=='ON_HOLD_PER_CURRENT_ROOT_INSTRUCTION','002/003 identity holds retained')
held={'BSI-9299D69FEF08','BSI-AF88EAA8EBC0','BSI-04D6E8690F30','BSI-22DA74B2107E','BSI-C87B4CF945C7','BSI-1B20DCA291BB','BSI-67B24409A253','BSI-65520F070145'}
for oid in held:
 check(next(z for z in a['coverage']if z['option_id']==oid)==next(z for z in old_a['coverage']if z['option_id']==oid),'Original held coverage byte-equivalent '+oid)
check(a['counts']==old_a['counts'],'All role/action totals unchanged by navigation and deferral')
check(a['counts']['required_picture_actions']==40 and a['counts']['in_situ_statuses']=={'Available':165,'No verified image':22},'40 actions;22 context gaps retained')
state=read(H/'guided-owner-review-state.json');check(len(state['queues']['in_situ'])==12 and len(state['queues']['series'])==17 and not deferred.intersection(state['queues']['in_situ']),'12 active context and17 series queue; scoped deferral excluded')
photo=read(H/'photo-source-review.json');check(len(photo['requests'])==29 and len(photo['held_requests'])==2 and photo['scope_files']==2293,'29 active of31 reviewed roles; bounded2293-file scope')
check(report['counts']['held_in_situ_cases']==10 and report['counts']['source_required_in_situ_cases']==12,'Ten held and12 active with no gap closure')
physical=read(H/'physical-source-audit.json');check(len(physical['options'])==187,'187 active options physically source-audited')
check(sum(len(z['physical_fields'])for z in physical['options'])==748,'748 physical field groups audited')
check(all(not z['physical_specifications_verified']for z in g['options']if z['product_id']in g['active_option_ids']),'No physical verification promoted')
with (out/'Physical_Verification_Input_187_Options.csv').open(encoding='utf-8-sig',newline='')as f:rows=list(csv.DictReader(f))
check(len(rows)==187,'Measurement input retains187 active options')
check(sha(out/'Physical_Verification_Input_187_Options.csv')==sha(Path(read(H/'inputs/source_report_verification.before')['output_directory'])/'Physical_Verification_Input_187_Options.csv'),'Uncompleted physical measurement input preserved exactly')
brief=read(out/'remaining-photograph-requests.json');check(brief['counts']['missing_roles']==29 and brief['counts']['option_records']==27 and not deferred.intersection({x['option_id']for x in brief['requests']}),'Capture brief contains29 active roles and27 options')
for item in report['pages']+report['csv_files']+report['thumbnail_files']:check(sha(item['path'])==item['sha256'],'Exact linked review artifact '+Path(item['path']).name)
for item in read(H/'original-verification.json')['files']:check(sha(item['local_original'])==item['sha256'],'Original bytes unchanged '+item['file_id'])
for item in read(H/'input-manifest.json').values():check(sha(item['path'])==sha(item['snapshot'])==item['sha256'],'Frozen input CAS '+Path(item['path']).name)
result={'status':'FAIL'if issues else'PASS','recorded_utc':datetime.now(timezone.utc).isoformat(),'checks':checks,'issues':issues,'workbook_sha256':sha(H/'master-workbook.pending'),'register_sha256':sha(H/'canonical-master-register.json'),'audit_sha256':sha(H/'image-coverage-current.json'),'current_options':187,'physical_field_groups':748,'new_physical_verifications':0,'active_context_requests':12,'held_context_requests':10,'series_requests':17,'unchanged_required_actions':40,'existing_context_path_refreshes':4,'identity_holds_retained':sorted(scene_ids),'native_or_platform_writes':0}
(H/'native-binding-verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:result[k]for k in ['status','checks','issues']}));raise SystemExit(bool(issues))
