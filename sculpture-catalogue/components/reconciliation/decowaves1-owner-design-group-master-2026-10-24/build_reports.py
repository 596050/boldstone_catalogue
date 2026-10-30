"""Refresh current reports with the exact owner relationship and grouping scope."""
import csv,hashlib,html,json,re,shutil
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import unquote
H=Path(__file__).resolve().parent;B=H.parents[2];OUT=B/'outputs'/H.name
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();esc=lambda x:html.escape(str(x),quote=True)
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
m=read(H/'input-manifest.json');src=read(m['source_report_verification']['snapshot']);OLD=Path(src['output_directory']);g=read(H/'canonical-master-register.json');a=read(H/'image-coverage-current.json');edge=read(H/'owner-design-edge.json');projection=read(H/'working-design-group-projection.json');pair=[o for o in g['options']if o['product_id']in edge['owner_confirmed_option_ids']];pages={};csvs=[];images=[]
notice='<section><strong>Current position:</strong> 188 active individual finish/size/build options;112 retained identified component ID records;111 working design groups after the owner-confirmed Decowaves1 Verdigris/Frozen Decowaves1 White relationship. <a href="decowaves1-owner-design-equivalence.html">Confirmed pair and count scope</a>. Source-photo coverage remains unchanged. The prior scoped native check retains2 unresolved Wall Circle primary references;22 context cases,1 Series case and Frozen Fish legacy identity remain held or deferred.</section>'
for x in src['thumbnail_files']:
 p=Path(x['path']);assert sha(p)==x['sha256'];d=OUT/p.relative_to(OLD);d.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,d);images.append({**x,'path':str(d)})
for x in src['pages']:
 p=Path(x['path']);assert sha(p)==x['sha256'];text=p.read_text().replace(str(OLD),str(OUT));text=re.sub(r'<section><strong>Current (?:position|catalogue):</strong>.*?</section>','',text,flags=re.S);text=text.replace('</h1>','</h1>'+notice,1)
 if p.name=='physical-evidence-review.html':
  text=text.replace('Physical evidence for187 options','Physical evidence for188 options')
  text=text.replace('All748 physical field groups were audited against their retained working details, source assertions and owner instructions. Five distinct recorded local source references match their saved digests. The187-row measurement input is empty.','The current checklist contains188 options and752 physical field groups, including4 comparator-only water-build fields with no independent physical source assertions. Existing source assertions and owner instructions retain their qualifications. Five distinct recorded local source references match their saved digests. The188-row measurement input is empty.')
 d=OUT/p.name;d.write_text(text);pages[d.name]={'path':str(d),'sha256':sha(d),'cards':text.count('<article')}
css=re.search(r'<style>(.*?)</style>',(OUT/'index.html').read_text(),re.S).group(1);cards=[]
for o in pair:
 fields=''.join('<tr><th>'+esc(k)+'</th><td>'+esc(v['display'])+'</td></tr>'for k,v in o['master_fields'].items())
 cards.append('<article id="'+esc(o['product_id'])+'"><h2>'+esc(o['name'])+'</h2><p><a href="'+esc(o['image_url'])+'">Selected image</a> · <a href="'+esc(o['folder_url'])+'">Containing folder</a></p><p>Same relief design as the other numbered1 reference; retained individual finish option with its own working specifications.</p><table>'+fields+'</table><small>'+esc(o['product_id'])+' · '+esc(o['canonical_component_id'])+' · '+esc(o['file_id'])+' · '+esc(o['folder_id'])+'</small></article>')
body='<p>Owner answered “Yes” on24 October2026 at03:55:40 UTC to the presented comparison of only Decowaves1 Verdigris and Frozen Decowaves1 White. Number2 remains unanswered. This does not verify the mould, physical cast count, stock, measurements, material recipe, fitted fixing or source SKU configuration.</p><p>The112 retained component IDs form111 working groups after linking BC-DECO-1 and BC-FDW-1. No IDs or rows were removed. Existing Decowaves1 Terracotta membership is retained; the owner did not newly review its photograph. The whole-library unique-design total remains unknown.</p><nav><a href="Current_Working_Design_Groups_111.csv">111 working groups</a> · <a href="Owner_Decowaves1_Design_Equivalence_2.csv">Confirmed two-option relationship</a> · <a href="'+esc(edge['source_evidence']['path'])+'">Sealed owner evidence</a> · <a href="index.html">Current catalogue</a></nav>'
p=OUT/'decowaves1-owner-design-equivalence.html';p.write_text('<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Decowaves1 owner design relationship</title><style>'+css+'</style></head><body><main><h1>Decowaves1 owner design relationship</h1>'+notice+body+''.join(cards)+'</main></body></html>');pages[p.name]={'path':str(p),'sha256':sha(p),'cards':2}
for x in src['csv_files']:
 p=Path(x['path']);assert sha(p)==x['sha256'];d=OUT/p.name
 if p.name=='Current_Individual_Options_188.csv':
  with p.open(encoding='utf-8-sig',newline='')as f:r=csv.DictReader(f);headers=r.fieldnames;data=list(r)
  headers=headers+['working_design_group_id','owner_confirmed_design_equivalence_edge']
  for row in data:row['working_design_group_id']=projection['component_id_to_working_group'].get(row['component_id'],'');row['owner_confirmed_design_equivalence_edge']=edge['edge_id']if row['option_id']in edge['owner_confirmed_option_ids']else''
  with d.open('w',encoding='utf-8-sig',newline='')as f:w=csv.DictWriter(f,fieldnames=headers);w.writeheader();w.writerows(data)
 else:shutil.copy2(p,d)
 csvs.append({**x,'path':str(d),'sha256':sha(d)})
def export(name,data):
 p=OUT/name
 with p.open('w',encoding='utf-8-sig',newline='')as f:w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
 csvs.append({'path':str(p),'sha256':sha(p),'rows':len(data)})
export('Current_Working_Design_Groups_111.csv',[{'working_design_group_id':x['working_design_group_id'],'retained_component_ids':' | '.join(x['retained_component_ids']),'active_option_ids':' | '.join(x['active_option_ids']),'owner_directly_confirmed_option_ids':' | '.join(x['owner_directly_confirmed_option_ids']),'basis':x['grouping_basis'],'scope':projection['scope']}for x in projection['groups']])
export('Owner_Decowaves1_Design_Equivalence_2.csv',[{'option_id':o['product_id'],'name':o['name'],'component_id_retained':o['canonical_component_id'],'working_design_group_id':'BC-DECO-1','edge_id':edge['edge_id'],'image_url':o['image_url'],'folder_url':o['folder_url'],'file_id':o['file_id'],'folder_id':o['folder_id'],'owner_answer_utc':edge['owner_answer_timestamp'],'specifications_transferred':False,'number2_confirmed':False}for o in pair])
shutil.copy2(m['source_photo_requests']['snapshot'],OUT/'remaining-photograph-requests.json');count=read(m['source_count_summary']['snapshot']);count['current_option_list']={'path':str(OUT/'Current_Individual_Options_188.csv'),'sha256':sha(OUT/'Current_Individual_Options_188.csv'),'rows':188};count['retained_component_identity_record_count']=112;count['grouped_working_design_identity_count']=111;count['current_owner_design_equivalence_scope']=edge['edge_id'];write(OUT/'current-count-summary.json',count)
class Parser(HTMLParser):
 def __init__(self):super().__init__();self.ids=set();self.links=[];self.cards=0
 def handle_starttag(self,t,attrs):
  d=dict(attrs)
  if t=='article':self.cards+=1
  if d.get('id'):self.ids.add(d['id'])
  if t in ['a','img']:self.links.append(d.get('href'if t=='a'else'src',''))
parsed={}
for x in pages.values():
 p=Path(x['path']).resolve();q=Parser();q.feed(p.read_text());assert q.cards==x['cards'];parsed[p]=q
for p,q in parsed.items():
 for u in q.links:
  assert 'BOLDSTONE_BACKUP'not in u.upper()
  if u.startswith(('https:','data:')):continue
  name,_,anchor=u.partition('#');target=(p.parent/unquote(name)).resolve()if name else p;assert target.is_file(),(p.name,u)
  if anchor and target in parsed:assert anchor in parsed[target].ids,(p.name,u)
result={**src,'status':'PASS','output_directory':str(OUT),'register_sha256':sha(H/'canonical-master-register.json'),'audit_sha256':sha(H/'image-coverage-current.json'),'pages':list(pages.values()),'csv_files':csvs,'thumbnail_files':images,'owner_design_equivalence_edge':edge['edge_id'],'retained_component_id_records':112,'grouped_working_design_identities':111}
write(H/'report-verification.json',result);print(json.dumps({'status':'PASS','pages':len(pages),'csvs':len(csvs),'retained_component_ids':112,'working_groups':111}))
