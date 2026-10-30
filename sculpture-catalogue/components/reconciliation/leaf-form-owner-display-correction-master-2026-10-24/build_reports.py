"""Show the current owner interpretation beside preserved historical source claims."""
import csv,hashlib,html,json,re,shutil
from pathlib import Path
from html.parser import HTMLParser
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;B=H.parents[2];OUT=B/'outputs'/H.name
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();esc=lambda v:html.escape(str(v),quote=True)
def write(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
m=read(H/'input-manifest.json');src=read(m['source_report_verification']['snapshot']);OLD=Path(src['output_directory']);g=read(H/'canonical-master-register.json');a=read(H/'image-coverage-current.json');old_a=read(m['audit']['snapshot']);oid='BSI-6581D83760F1';o=next(o for o in g['options']if o['product_id']==oid);row=next(x for x in a['coverage']if x['option_id']==oid);prior=next(x for x in old_a['coverage']if x['option_id']==oid)['series']['basis'];basis=row['series']['basis'];ref=row['series']['reference'];pages={};csvs=[];images=[]
notice='<section><strong>Current position:</strong> 188 active options and112 working component identities. Owner confirms the exact Leaf Form White photograph shows one existing design twice. No new sculpture, photo role or physical verification. Existing photograph holds remain. <a href="leaf-form-owner-display.html">Owner correction with image and folder links</a>.</section>'
for x in src['thumbnail_files']:
 p=Path(x['path']);assert sha(p)==x['sha256'];dest=OUT/p.relative_to(OLD);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest);images.append({**x,'path':str(dest)})
for x in src['pages']:
 p=Path(x['path']);assert sha(p)==x['sha256'];text=p.read_text().replace(str(OLD),str(OUT));text=re.sub(r'<section><strong>Current (?:position|catalogue):</strong>.*?</section>','',text,flags=re.S);text=text.replace(esc(prior),esc(basis));text=text.replace('</h1>','</h1>'+notice,1);dest=OUT/p.name;dest.write_text(text);pages[p.name]={'path':str(dest),'sha256':sha(dest),'cards':text.count('<article')}
css=re.search(r'<style>(.*?)</style>',(OUT/'index.html').read_text(),re.S).group(1)
body='<article id="'+oid+'"><h2>Leaf Form — White</h2><p><a href="'+esc(ref['image_url'])+'">Exact owner-reviewed repeated-display photograph</a> · <a href="'+esc(ref['folder_url'])+'">Containing folder</a></p><p><strong>One existing Leaf Form design shown twice on a wall.</strong> The owner rejected the two-part sculpture interpretation for this image. The catalogue already has one White option and one design identity, so no sculpture or option is added.</p><p>The image remains a qualified Series/display reference. It does not verify physical cast quantity, image-production method or native pack sale quantity.</p><p>The historical O028 title, description, two native parts, two proposed BOM positions, SKU LF-2P-35.70, native600.00 source price (currency unencoded in the retained export), set size and set weight are retained as source claims. They are not allocated to individual copies. O058 standalone association and all six working fields remain unchanged. The Gold option and separate garden image are outside this correction.</p><p><a href="'+esc(o['image_url'])+'">Existing individual reference</a> · <a href="'+esc(o['folder_url'])+'">Individual containing folder</a></p><small>'+esc(ref['file_id'])+' / '+esc(ref['folder_id'])+'</small></article>'
p=OUT/'leaf-form-owner-display.html';p.write_text('<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Leaf Form repeated display</title><style>'+css+'</style></head><body><main><h1>Leaf Form owner correction</h1>'+notice+body+'</main></body></html>');pages[p.name]={'path':str(p),'sha256':sha(p),'cards':1}
for x in src['csv_files']:
 p=Path(x['path']);assert sha(p)==x['sha256'];dest=OUT/p.name;shutil.copy2(p,dest);csvs.append({**x,'path':str(dest)})
p=OUT/'Owner_Leaf_Form_Depiction_1.csv'
with p.open('w',encoding='utf-8-sig',newline='')as f:
 headers=['option_id','component_id','name','file_id','folder_id','image_url','folder_url','unique_designs_depicted','depicted_placements','native_pack_quantity_verified','physical_cast_quantity_verified','current_interpretation'];w=csv.DictWriter(f,fieldnames=headers);w.writeheader();w.writerow({'option_id':oid,'component_id':o['canonical_component_id'],'name':o['name'],'file_id':ref['file_id'],'folder_id':ref['folder_id'],'image_url':ref['image_url'],'folder_url':ref['folder_url'],'unique_designs_depicted':1,'depicted_placements':2,'native_pack_quantity_verified':False,'physical_cast_quantity_verified':False,'current_interpretation':basis})
csvs.append({'path':str(p),'sha256':sha(p),'rows':1})
write(OUT/'remaining-photograph-requests.json',read(m['source_photo_requests']['snapshot']));count=read(m['source_count_summary']['snapshot']);count['current_option_list']={'path':str(OUT/'Current_Individual_Options_188.csv'),'sha256':sha(OUT/'Current_Individual_Options_188.csv'),'rows':188};count['latest_leaf_form_owner_depiction_import']=read(H/'import-summary.json');write(OUT/'current-count-summary.json',count)
class Parser(HTMLParser):
 def __init__(self):super().__init__();self.ids=set();self.links=[];self.images=[];self.cards=0
 def handle_starttag(self,t,attrs):
  d=dict(attrs)
  if t=='article':self.cards+=1
  if d.get('id'):self.ids.add(d['id'])
  if t=='a':self.links.append(d.get('href',''))
  if t=='img':self.images.append(d.get('src',''))
parsed={}
for x in pages.values():
 p=Path(x['path']).resolve();q=Parser();q.feed(p.read_text());assert q.cards==x['cards'];parsed[p]=q
for p,q in list(parsed.items()):
 for u in q.links:
  if u.startswith('https://'):continue
  d,_,anchor=u.partition('#');dest=(p.parent/d).resolve()if d and not Path(d).is_absolute()else(Path(d).resolve()if d else p);assert dest.is_file(),(p,u)
  if anchor and dest.suffix=='.html':
   if dest not in parsed:z=Parser();z.feed(dest.read_text());parsed[dest]=z
   assert anchor in parsed[dest].ids,(p,u)
 for u in q.images:assert(p.parent/u).is_file(),(p,u)
r={'status':'PASS_CURRENT_LINKED_REPORTS','recorded_utc':datetime.now(timezone.utc).isoformat(),'output_directory':str(OUT),'pages':list(pages.values()),'csv_files':csvs,'thumbnail_files':images,'counts':{**src['counts'],'current_file_paths_refreshed':0,'actual_parent_id_changes':0,'owner_depiction_corrections_this_refresh':1,'new_physical_verifications':0},'register_sha256':sha(H/'canonical-master-register.json'),'audit_sha256':sha(H/'image-coverage-current.json'),'pixels_edited':False,'native_or_platform_writes':0};write(H/'report-verification.json',r);print(json.dumps({'status':r['status'],'pages':len(pages),'current_owner_depiction_corrections':1,'new_physical_verifications':0}))
