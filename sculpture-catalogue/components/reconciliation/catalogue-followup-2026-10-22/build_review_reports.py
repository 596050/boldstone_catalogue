"""Refresh linked owner-review lists after the family size instruction."""
import collections,csv,hashlib,html,json,shutil
from pathlib import Path
from datetime import datetime,timezone
from html.parser import HTMLParser
H=Path(__file__).resolve().parent;BASE=H.parents[2];OUT=BASE/'outputs/catalogue-followup-2026-10-22';OUT.mkdir(exist_ok=True);(OUT/'images').mkdir(exist_ok=True)
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();esc=lambda x:html.escape(str(x),quote=True)
g=read(H/'canonical-master-register.json');a=read(H/'image-coverage-current.json');cov={x['option_id']:x for x in a['coverage']};assets=read(H/'current-assets.json');reviews=read(H/'photo-review-queue.json');reviewmap={x['task_id']:x for x in reviews};rows=[]
for i,r in enumerate(a['missing_pictures'],1):
 p=cov[r['option_id']]['individual'].get('reference')or r['reference'];ref=r['reference']
 review=reviewmap.get(r['option_id']+'::'+r['role'],{})
 rows.append({'sequence':i,'option_id':r['option_id'],'name':r['name'],'role':r['role'],'action_type':r['action_type'],'status':r['status'],'action':review.get('next_action',r['action']),'qualification':review.get('finding',r['qualification']),'review_state':review.get('review_state','Retained earlier decision'),'component_position':review.get('component_position',''),**{k:ref.get(k,'')for k in ['image_url','folder_url','file_id','folder_id']},**{'subject_'+k:p.get(k,'')for k in ['image_url','folder_url','file_id','folder_id']},'owner_response':''})
required=[r for r in rows if r['status']=='Open'];ind=[r for r in required if r['role']=='Individual'];ins=[r for r in required if r['role']=='In situ'and r['action_type']=='Find / capture'];series=[r for r in required if r['role']=='Series'and r['action_type']=='Find / capture'];checks=[r for r in required if r['action_type']=='Verify existing image'];resolved=[r for r in rows if r['status']=='Resolved'];optional=[r for r in rows if r['status']=='Optional']
assert[len(rows),len(required),len(ind),len(ins),len(series),len(checks),len(resolved),len(optional)]==[205,98,19,61,18,1,54,53]
def writecsv(name,data):
 p=OUT/name
 with p.open('w',encoding='utf-8-sig',newline='')as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(data)
 with p.open(encoding='utf-8-sig',newline='')as f:back=list(csv.DictReader(f))
 assert len(back)==len(data)and all(x['image_url']and x['folder_url']and x['file_id']and x['folder_id']for x in back)
 return{'path':str(p),'sha256':sha(p),'rows':len(data)}
csvs=[writecsv(n,rs)for n,rs in [('All_Current_Picture_Actions.csv',rows),('Missing_Pictures_Required_2026-10-22.csv',required),('Missing_Individual_Images_2026-10-22.csv',ind),('Missing_In_Situ_Images_2026-10-22.csv',ins),('Missing_Series_Images_2026-10-22.csv',series),('Existing_Images_to_Check_2026-10-22.csv',checks),('Resolved_Image_Associations_2026-10-22.csv',resolved),('Optional_Series_Images_2026-10-22.csv',optional)]]
thumbs={}
def thumb(fid):
 if fid in thumbs:return thumbs[fid]['relative_path']
 src=assets.get(fid,{}).get('thumb')
 if not src or not Path(src).is_file():return''
 p=OUT/'images'/(hashlib.sha256(fid.encode()).hexdigest()+Path(src).suffix.lower());shutil.copy2(src,p);thumbs[fid]={'path':str(p),'relative_path':str(p.relative_to(OUT)),'file_id':fid,'sha256':sha(p)};return thumbs[fid]['relative_path']
def link(url,label):return'<a href="'+esc(url)+'" target="_blank" rel="noopener">'+esc(label)+'</a>'
def picture(fid,url,label):
 t=thumb(fid)
 return'<figure>'+('<a href="'+esc(url)+'" target="_blank" rel="noopener"><img src="'+esc(t)+'" alt="'+esc(label)+'" loading="lazy"></a>'if t else link(url,'Open image'))+'<figcaption>'+esc(label)+'</figcaption></figure>'
def card(r):
 pics=picture(r['subject_file_id'],r['subject_image_url'],'Kept sculpture / comparison')
 if r['file_id']!=r['subject_file_id']:pics+=picture(r['file_id'],r['image_url'],'Role image / candidate')
 return'<article data-search="'+esc(' '.join(map(str,r.values())).lower())+'"><h2>'+esc(r['name'])+'</h2><p>'+esc(r['role']+' · '+r['status']+' · '+r['review_state'])+'</p><div class="content"><div class="pictures">'+pics+'</div><div><p>'+esc(r['qualification'])+'</p><p>'+esc(r['component_position'])+'</p><p><strong>Next:</strong> '+esc(r['action'])+'</p><p>'+link(r['subject_image_url'],'Sculpture image')+' · '+link(r['subject_folder_url'],'Sculpture folder')+' · '+link(r['image_url'],'Role image / candidate')+' · '+link(r['folder_url'],'Containing folder')+'</p><details><summary>Stable Dropbox IDs</summary>'+esc('Option '+r['option_id'])+'<br>'+esc('File '+r['file_id'])+'<br>'+esc('Folder '+r['folder_id'])+'</details></div></div></article>'
nav='<nav>'+ ' · '.join('<a href="'+f+'">'+n+'</a>'for f,n in [('index.html','98 remaining actions'),('individual-images.html','19 individual entries'),('in-situ-images.html','61 in situ gaps'),('series-images.html','18 series gaps'),('existing-images-to-check.html','Deferred legacy binding'),('resolved-image-associations.html','54 current resolved actions')])+'</nav>'
css='body{font:16px/1.5 Arial,sans-serif;color:#28362d;background:#f5f6f3;margin:0}main{max-width:1160px;margin:auto;padding:26px}h1{font-size:27px}h2{font-size:19px;color:#344e40}a{color:#245f7a}article,section{background:#fff;border:1px solid #d8ded4;padding:20px;margin:18px 0}nav{padding:12px 0;border-bottom:1px solid #ced5cb}.content,.pictures{display:flex;gap:18px}.pictures{min-width:190px;flex-wrap:wrap}figure{margin:0;max-width:180px}img{width:180px;height:165px;object-fit:contain;background:#eef1ec}figcaption,details,.limit{font-size:13px;color:#64705f}input{font:inherit;padding:9px;width:80%;max-width:600px}.toolbar{position:sticky;top:0;background:#f5f6f3;padding:12px}.hide{display:none}@media(max-width:700px){.content{display:block}main{padding:15px}}'
pages=[]
for file,title,data in [('index.html','Current sculpture photograph and identity work',required),('individual-images.html','Individual photograph and identity gaps',ind),('in-situ-images.html','In situ images to find',ins),('series-images.html','Series images to find',series),('existing-images-to-check.html','Existing images and identities to confirm',checks),('resolved-image-associations.html','Resolved image actions retained for reference',resolved)]:
 body='<h1>'+esc(title)+'</h1><p>'+esc(g['wall_sculpture_customisation_policy']['customer_text'])+'</p><p>All current Frozen Fish: <strong>70 cm high × 15 cm wide</strong>. The historical FFL1/FFS2 binding remains deferred. No new 100 × 22 cm photograph is requested.</p><p>The catalogue contains 186 options across 112 working component identities. Links include 49 approved folder updates. Dune Ripple 1 is Waves and 2 is Spiral. Three complete images have been accepted for individual listings: Leaf Growth — White and Gold Leaf, Spiralfish 1 — Bronze and Spiralfish 2 — Bronze. Their original bytes are retained and photographic or generated origin remains unverified. These acceptances close individual-image roles only. The 19 remaining individual entries require 18 separate photographs and one deferred Frozen Fish identity. There are 61 in situ and 18 series gaps. The 13 earlier crop proposals remain declined, with separate photographs required. No crops have been created.</p><p>Working prices are estimates for 185 options. Made-to-order availability and a 1–2 week lead-time policy apply where earlier specific owner instructions do not take precedence. Moon Crater Phase 4 — Verdigris and Rust retains £175 per panel and its one-week policy. Physical stock and actual measurements remain qualified separately.</p>'+nav+'<p>'+link('Missing_Pictures_Required_2026-10-22.csv','Download remaining actions (CSV)')+' · '+link('All_Photo_Reviews_2026-10-22.csv','Download 105 current reviews (CSV)')+'</p><div class="toolbar"><input id="search" type="search" placeholder="Search sculpture, finish or action" aria-label="Search"><p id="shown"></p></div>'+''.join(card(r)for r in data)+'<p class="limit">Available image roles are qualified visual references. Actual cast measurements, scene origin and installed hardware retain their own evidence status. Native Dropbox links open in your account.</p>'
 js="const q=document.querySelector('#search');function filter(){let n=0;document.querySelectorAll('article').forEach(x=>{let s=x.dataset.search.includes(q.value.toLowerCase());x.classList.toggle('hide',!s);if(s)n++});document.querySelector('#shown').textContent=n+' items shown'}q.addEventListener('input',filter);filter();"
 p=OUT/file;p.write_text('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+esc(title)+'</title><style>'+css+'</style></head><body><main>'+body+'</main><script>'+js+'</script></body></html>');pages.append({'path':str(p),'sha256':sha(p),'review_rows':len(data)})
class Parser(HTMLParser):
 def __init__(self):super().__init__();self.hrefs=[];self.images=[];self.tasks=0
 def handle_starttag(self,tag,attrs):
  d=dict(attrs)
  if tag=='a':self.hrefs.append(d.get('href',''))
  if tag=='img':self.images.append(d)
  if tag=='article':self.tasks+=1
review_rows=[r for r in rows if r['option_id']+'::'+r['role']in reviewmap];assert len(review_rows)==105
csvs.append(writecsv('All_Photo_Reviews_2026-10-22.csv',review_rows))
for p in pages:
 x=Parser();x.feed(Path(p['path']).read_text());assert x.tasks==p['review_rows'];assert all(u and(u.startswith('https://www.dropbox.com/')or(OUT/u).is_file())for u in x.hrefs);assert all(t.get('alt')and(OUT/t['src']).is_file()for t in x.images)
assert len({x['relative_path'].casefold()for x in thumbs.values()})==len(thumbs)
manifest={'status':'PASS_OWNER_CORRECTION_REPORTS','recorded_utc':datetime.now(timezone.utc).isoformat(),'output_directory':str(OUT),'pages':pages,'csv_files':csvs,'thumbnail_files':list(thumbs.values()),'counts':{'required_actions':98,'find_capture':97,'existing_image_checks':1,'individual_gaps':19,'in_situ_gaps':61,'series_gaps':18,'current_resolved_actions':54,'historical_resolved_actions_in_prior_publication':53,'cumulative_resolved_including_two_archived':56,'superseded_Fingerprint_actions_archived':6,'optional':53,'exact_crop_candidates':0,'separate_individual_photos_required':18,'historical_crop_candidates_declined_by_owner':13,'legacy_binding_deferred':1,'reviewed_action_rows':105,'new_visual_roles_mapped':3,'previous_visual_roles_mapped':6},'old_report_directories_preserved':True,'native_links_require_account':True}
(H/'link-report-verification.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps({'status':manifest['status'],'counts':manifest['counts']}))
