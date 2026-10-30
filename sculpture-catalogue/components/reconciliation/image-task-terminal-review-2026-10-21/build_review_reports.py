"""Current linked review and precise remaining photograph/binding lists."""
import collections,csv,hashlib,html,json,re,shutil
from pathlib import Path
from datetime import datetime,timezone
from html.parser import HTMLParser
H=Path(__file__).resolve().parent;BASE=H.parents[2];OUT=BASE/'outputs/image-task-terminal-review-2026-10-21';OUT.mkdir(parents=True,exist_ok=True);(OUT/'images').mkdir(exist_ok=True)
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();esc=lambda x:html.escape(str(x),quote=True)
prior_manifest=H/'link-report-verification.json'
if prior_manifest.exists():
 for x in read(prior_manifest).get('thumbnail_files',[]):
  p=Path(x['path']);assert p.parent==OUT/'images'
  if p.is_file():p.unlink()
items=read(H/'terminal-review-items.json');audit=read(H/'image-coverage-current.json');assets=read(H/'current-assets.json');g=read(H/'canonical-master-register.json');actions={(x['option_id'],x['role']):x for x in audit['missing_pictures']}
state_names={'RESOLVED_VERIFIED_REFERENCE':'Image role mapped','REVIEWED_BINDING_REQUIRED':'Check existing candidate','REVIEWED_CAPTURE_REQUIRED':'Find or photograph','REVIEWED_SIZE_BINDING_REQUIRED':'Bind exact size / photograph'}
rows=[]
for x in items:
 d=x['findings'][-1];a=actions[(x['option_id'],x['requested_role'])];r=a['reference'];p=x['primary_reference'];subject=assets.get(p.get('file_id'))or x['prior_action']['reference']
 rows.append({'sequence':x['sequence'],'option_id':x['option_id'],'name':x['name'],'family':x['family'],'role':x['requested_role'],'review_state':x['review_state'],'review_status':state_names[x['review_state']],'action_type':a['action_type'],'action_status':a['status'],'finding':d['finding'],'next_action':d['next_action'],'position':d.get('position',''),'image_url':r['image_url'],'folder_url':r['folder_url'],'file_id':r['file_id'],'folder_id':r['folder_id'],'subject_image_url':subject['image_url'],'subject_folder_url':subject['folder_url'],'subject_file_id':subject['file_id'],'subject_folder_id':subject['folder_id'],'scene_and_physical_limit':'Visual reference only; scene origin, measured scale, exact physical cast and hardware remain separately unverified.','owner_response':''})
assert len(rows)==157 and all(all(x[k]for k in ['image_url','folder_url','file_id','folder_id','subject_image_url','subject_folder_url'])for x in rows)
required=[x for x in rows if x['action_status']!='Resolved'];ind=[x for x in required if x['role']=='Individual'];ins=[x for x in required if x['role']=='In situ'and x['review_state']=='REVIEWED_CAPTURE_REQUIRED'];series=[x for x in required if x['role']=='Series'and x['review_state']=='REVIEWED_CAPTURE_REQUIRED'];checks=[x for x in required if x['review_state']=='REVIEWED_BINDING_REQUIRED'];closed=[x for x in rows if x['action_status']=='Resolved']
assert[len(required),len(ind),len(ins),len(series),len(checks),len(closed)]==[142,26,65,20,31,15]
def writecsv(name,rs,fields=None):
 p=OUT/name;fields=fields or list(rows[0])
 with p.open('w',encoding='utf-8-sig',newline='')as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows({k:x.get(k,'')for k in fields}for x in rs)
 return{'path':str(p),'sha256':sha(p),'rows':len(rs)}
csvs=[]
for name,rs in [('All_157_Reviewed_Items.csv',rows),('Missing_Pictures_Required_2026-10-21.csv',required),('Missing_Individual_Images_2026-10-21.csv',ind),('Missing_In_Situ_Images_2026-10-21.csv',ins),('Missing_Series_Images_2026-10-21.csv',series),('Existing_Images_to_Check_2026-10-21.csv',checks),('Resolved_Image_Associations_2026-10-21.csv',closed)]:csvs.append(writecsv(name,rs))
optional=[]
for x in audit['missing_pictures']:
 if x['status']=='Optional':optional.append({**{k:x.get(k,'')for k in ['option_id','name','role','action_type','status','action','qualification']},**{k:x['reference'][k]for k in ['image_url','folder_url','file_id','folder_id']}})
csvs.append(writecsv('Optional_Series_Images_2026-10-21.csv',optional,list(optional[0])))
thumbnail_manifest={}
def thumb(fid):
 if fid in thumbnail_manifest:return thumbnail_manifest[fid]['relative_path']
 a=assets.get(fid,{})
 src=a.get('thumb','')
 if not src or not Path(src).is_file():return''
 p=OUT/'images'/(hashlib.sha256(fid.encode()).hexdigest()+Path(src).suffix.lower());shutil.copy2(src,p)
 thumbnail_manifest[fid]={'file_id':fid,'source_cache':src,'relative_path':str(p.relative_to(OUT)),'path':str(p),'sha256':sha(p),'purpose':'Existing source thumbnail for review, not a new product photograph'};return str(p.relative_to(OUT))
def link(url,label):return'<a href="'+esc(url)+'" target="_blank" rel="noopener">'+esc(label)+'</a>'
def figure(fid,url,caption):
 t=thumb(fid);img='<img src="'+esc(t)+'" alt="'+esc(caption)+'" loading="lazy">'if t else'<span>Open image in Dropbox</span>'
 return'<figure>'+link(url,'') .replace('></a>','>'+img+'</a>')+'<figcaption>'+esc(caption)+'</figcaption></figure>'
def card(x):
 media=figure(x['subject_file_id'],x['subject_image_url'],'Kept sculpture reference')
 if x['file_id']!=x['subject_file_id']:media+=figure(x['file_id'],x['image_url'],'Role image / candidate')
 links=link(x['subject_image_url'],'Sculpture image')+' · '+link(x['subject_folder_url'],'Sculpture folder')+' · '+link(x['image_url'],'Role image / candidate')+' · '+link(x['folder_url'],'Containing folder')
 return'<article class="task" data-state="'+esc(x['review_state'])+'" data-role="'+esc(x['role'])+'" data-search="'+esc(' '.join(str(v)for v in x.values()).lower())+'"><h3>'+str(x['sequence']).zfill(3)+' · '+esc(x['name'])+'</h3><p class="status">'+esc(x['role']+' — '+x['review_status'])+'</p><div class="evidence"><div class="pictures">'+media+'</div><div><p>'+esc(x['finding'])+'</p><p><strong>Next:</strong> '+esc(x['next_action'])+'</p><p class="links">'+links+'</p><p class="limit">'+esc(x['scene_and_physical_limit'])+'</p><details><summary>Stable Dropbox IDs</summary><p>Option '+esc(x['option_id'])+'<br>Role file '+esc(x['file_id'])+'<br>Role folder '+esc(x['folder_id'])+'<br>Subject file '+esc(x['subject_file_id'])+'<br>Subject folder '+esc(x['subject_folder_id'])+'</p></details></div></div></article>'
nav='<nav>'+ ' · '.join('<a href="'+file+'">'+label+'</a>'for file,label in [('index.html','All 157 reviews'),('individual-images.html','26 individual gaps'),('in-situ-images.html','65 in situ gaps'),('series-images.html','20 series gaps'),('existing-images-to-check.html','31 candidate checks'),('resolved-image-associations.html','15 mapped roles')])+'</nav>'
fp=g['latest_fingerprint_component_paths']['component_finish_bindings'];cup=g['current_cup_colour_reference_paths']
def organisation():
 text='<section><h2>Fingerprint folders</h2><p>The verified component split is retained. These four options still need complete individual photographs; pair images remain arrangement references.</p><ul>'
 for x in fp:text+='<li>'+esc(x['component_id']+' — '+x['finish'])+': '+link(x['finish_folder_url'],'Component finish folder')+' · '+link(x['reference_document_url'],'Pair/group reference document')+'<br><small>'+esc(x['finish_folder_id'])+'; '+esc(x['reference_document_id'])+'</small></li>'
 text+='</ul><h2>Cup Ring appearance references</h2><p>Owner-approved Pink and Brown image folders are recorded by stable IDs. These are processed reference images; physical finishes and manufacture remain unconfirmed. The White option and its historical primary remain unchanged.</p><ul>'
 for x in cup['objects']:text+='<li>'+esc(x['approved_appearance_label'])+': '+link(x['current_native_url'],'Image')+' · '+link(x['current_folder_url'],'Containing folder')+'<br><small>'+esc(x['file_id'])+'; '+esc(x['current_parent_id'])+'</small></li>'
 return text+'</ul></section>'
css='body{font:16px/1.5 Arial,sans-serif;color:#28362d;background:#f5f6f3;margin:0}main{max-width:1160px;margin:auto;padding:30px 24px}h1,h2,h3{color:#344e40}h1{font-size:28px}h2{font-size:21px}h3{font-size:18px;margin:0}a{color:#245f7a}nav{padding:12px 0;border-bottom:1px solid #ced5cb}.task,section{background:white;margin:18px 0;padding:20px;border:1px solid #d8ded4}.status{margin:4px 0 16px;color:#53634f}.evidence{display:flex;gap:20px}.pictures{display:flex;gap:10px;flex-wrap:wrap;min-width:190px}figure{margin:0;max-width:180px}img{width:180px;height:165px;object-fit:contain;background:#eef1ec}figcaption,small,.limit{font-size:13px;color:#64705f}.links{font-size:14px}details{font-size:12px}input,select{font:inherit;padding:8px;margin:6px 8px 6px 0;max-width:100%}.toolbar{position:sticky;top:0;background:#f5f6f3;padding:12px 0;z-index:2}p{margin:8px 0 14px}.hide{display:none}@media(max-width:700px){.evidence{display:block}.pictures{margin-bottom:16px}main{padding:16px}nav{line-height:2}}'
js="const q=document.querySelector('#search'),s=document.querySelector('#state'),r=document.querySelector('#role');function filter(){let n=0;document.querySelectorAll('.task').forEach(x=>{let show=x.dataset.search.includes(q.value.toLowerCase())&&(s.value==='all'||x.dataset.state===s.value)&&(r.value==='all'||x.dataset.role===r.value);x.classList.toggle('hide',!show);if(show)n++});document.querySelector('#visible').textContent=n+' items shown'}[q,s,r].forEach(x=>x.addEventListener('input',filter));filter();"
pages=[]
for file,title,rs,org in [('index.html','Sculpture photograph review — 21 October 2026',rows,True),('individual-images.html','26 individual photograph / size gaps',ind,False),('in-situ-images.html','65 in situ photograph gaps',ins,False),('series-images.html','20 series photograph gaps',series,False),('existing-images-to-check.html','31 existing images needing exact binding',checks,False),('resolved-image-associations.html','15 image roles mapped in this review',closed,False)]:
 toolbar='<div class="toolbar"><input id="search" type="search" placeholder="Search sculpture, finish or finding" aria-label="Search"><select id="state" aria-label="Review status"><option value="all">All review states</option>'+''.join('<option value="'+k+'">'+esc(v)+'</option>'for k,v in state_names.items())+'</select><select id="role" aria-label="Picture role"><option value="all">All roles</option>'+''.join('<option>'+esc(x)+'</option>'for x in ['Individual','In situ','Series'])+'</select><p id="visible"></p></div>'
 body='<h1>'+esc(title)+'</h1><p>157 required items reviewed; 15 image associations resolved and 142 actions remain. The catalogue retains 184 individual options. Action counts are photograph roles, not a count of sculptures or new photos.</p><p>Available image roles include qualified presentations and staged settings. A visual match does not measure the sculpture or authenticate an installation. Dropbox links open in your account.</p>'+nav+('<p>'+link('Missing_Pictures_Required_2026-10-21.csv','Download all 142 outstanding actions (CSV)')+'</p>'if org else'')+toolbar+''.join(card(x)for x in rs)+(organisation()if org else'')
 p=OUT/file;p.write_text('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+esc(title)+'</title><style>'+css+'</style></head><body><main>'+body+'</main><script>'+js+'</script></body></html>');pages.append({'path':str(p),'sha256':sha(p),'review_rows':len(rs)})
class Parser(HTMLParser):
 def __init__(self):super().__init__();self.hrefs=[];self.images=[];self.tasks=0
 def handle_starttag(self,tag,attrs):
  d=dict(attrs)
  if tag=='a':self.hrefs.append(d.get('href',''))
  if tag=='img':self.images.append(d)
  if tag=='article'and d.get('class')=='task':self.tasks+=1
for p in pages:
 parser=Parser();parser.feed(Path(p['path']).read_text());assert parser.tasks==p['review_rows']
 assert all(url and(url.startswith('https://www.dropbox.com/')or(OUT/url).is_file())for url in parser.hrefs)
 assert all(im.get('alt')and(OUT/im['src']).is_file()for im in parser.images)
 p.update(hyperlinks=len(parser.hrefs),local_images=len(parser.images))
for x in csvs:
 with Path(x['path']).open(encoding='utf-8-sig',newline='')as f:back=list(csv.DictReader(f))
 assert len(back)==x['rows']and all(r['image_url']and r['folder_url']and r['file_id']and r['folder_id']for r in back)
for x in thumbnail_manifest.values():assert sha(x['path'])==x['sha256']
assert len({x['relative_path'].casefold()for x in thumbnail_manifest.values()})==len(thumbnail_manifest)
manifest={'status':'PASS_CURRENT_TERMINAL_REVIEW_REPORTS','recorded_utc':datetime.now(timezone.utc).isoformat(),'output_directory':str(OUT),'pages':pages,'csv_files':csvs,'thumbnail_files':list(thumbnail_manifest.values()),'counts':{'reviewed':157,'resolved_image_roles':15,'required_actions':142,'individual_gaps':26,'in_situ_gaps':65,'series_gaps':20,'existing_image_checks':31,'optional_series':53},'native_Dropbox_links_require_account':True,'created_shared_links':0,'live_HTTP_access_audit':False,'source_qualified_not_physical_certification':True,'legacy_report_directory_untouched':True}
(H/'link-report-verification.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:manifest[k]for k in ['status','output_directory','counts']}))
