"""Build complete human-readable link lists from the current bounded audit."""
import collections,csv,hashlib,html,json
from pathlib import Path
from datetime import datetime,timezone
from html.parser import HTMLParser
HERE=Path(__file__).resolve().parent;BASE=HERE.parents[2];OUT=BASE/'outputs/image-review-links-2026-10-21'
read=lambda p:json.loads(Path(p).read_text());esc=lambda x:html.escape(str(x or ''),quote=True)
digest=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
audit=read(HERE/'image-coverage-current.json');g=read(HERE/'canonical-master-register.json')
overlay=read(read(HERE/'input-manifest.json')['overlay']['path']);byid={x['product_id']:x for x in g['options']};objects={x['file_id']:x for x in overlay['objects']}
bindings=overlay['component_finish_bindings'];binding_by_id={x['product_id']:x for x in bindings}
actions=[x for x in audit['missing_pictures']if x['status']not in ['Resolved','Optional']]
assert len(actions)==157
groups=[('individual','26 individual-image gaps','02-individual-images.html',[x for x in actions if x['role']=='Individual']),
 ('in-situ','66 missing in situ images','03-in-situ-images.html',[x for x in actions if x['role']=='In situ'and x['action_type']=='Find / capture']),
 ('series','27 missing series images','04-series-images.html',[x for x in actions if x['role']=='Series'and x['action_type']=='Find / capture']),
 ('checks','38 existing-image checks','05-existing-images-to-check.html',[x for x in actions if x['action_type']=='Verify existing image'])]
assert [len(x[3])for x in groups]==[26,66,27,38]
assert sum(len(x[3])for x in groups)==len(actions)
OUT.mkdir(parents=True,exist_ok=True)
def a(url,label):
 assert url.startswith('https://www.dropbox.com/'),url
 return f'<a href="{esc(url)}" target="_blank" rel="noopener">{esc(label)}</a>'
nav='<nav><a href="index.html">All links</a><a href="01-fingerprint-folders.html">Fingerprint folders</a>'+''.join(f'<a href="{file}">{esc(title)}</a>'for _,title,file,_ in groups)+'</nav>'
css='''*{box-sizing:border-box}body{margin:0;background:#f5f5f0;color:#26362d;font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}main{max-width:1600px;margin:auto;padding:28px}h1{font-size:30px;line-height:1.2;margin:0 0 12px}h2{font-size:23px;margin:32px 0 10px}p{max-width:1100px}nav{display:flex;flex-wrap:wrap;gap:8px;margin:20px 0}nav a,.download{background:#fff;border:1px solid #ccd5ca;border-radius:7px;padding:8px 12px;text-decoration:none}a{color:#235a43;text-underline-offset:3px}a:hover{color:#123c2a}section{scroll-margin-top:20px}.panel{background:#fff;border:1px solid #d7ded3;border-radius:9px;padding:16px}.table-wrap{overflow:auto;background:white;border:1px solid #d7ded3;border-radius:8px}table{border-collapse:collapse;width:100%;min-width:1020px}th,td{padding:13px 15px;vertical-align:top;text-align:left;border-bottom:1px solid #e4e8e0}th{background:#344e40;color:white;font-weight:600}tr:nth-child(even){background:#f7f8f4}td.name{width:22%;min-width:220px}td.action{width:40%;min-width:320px}td.links{min-width:150px}small,.muted{display:block;color:#667269;font-size:12px}code{font-size:11px;overflow-wrap:anywhere}details{margin-top:9px;font-size:13px}summary{cursor:pointer;color:#526953}.tag{display:inline-block;font-size:12px;background:#f2ead7;border-radius:4px;padding:2px 7px;margin-top:6px}.toolbar{display:flex;gap:12px;align-items:center;margin:16px 0;flex-wrap:wrap}input{font:inherit;padding:10px 12px;border:1px solid #aab8a9;border-radius:6px;min-width:320px;max-width:100%}.notice{border-left:4px solid #9b7333;padding:10px 15px;background:#fff7e8}.stats{display:flex;gap:10px;flex-wrap:wrap}.stats a{background:#fff;border:1px solid #cad5c8;padding:10px 14px;border-radius:8px;text-decoration:none}.links a{display:block;margin-bottom:6px}[hidden]{display:none!important}@media(max-width:700px){main{padding:18px}h1{font-size:25px}input{min-width:100%}}@media print{nav,.toolbar,.download{display:none}main{max-width:none;padding:0}table{min-width:0;font-size:10px}.table-wrap{overflow:visible}a{color:black}details{display:block}}'''
script='''const search=document.querySelector('#search');if(search){search.addEventListener('input',()=>{const q=search.value.toLocaleLowerCase().trim();let n=0;document.querySelectorAll('tr.task').forEach(r=>{r.hidden=!r.textContent.toLocaleLowerCase().includes(q);if(!r.hidden)n++});document.querySelector('#shown').textContent=n+' rows shown';});}'''
def page(title,body,count):
 return '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+esc(title)+' | Boldstone</title><style>'+css+'</style></head><body><main><h1>'+esc(title)+'</h1><p class="muted">21 October 2026 · Current stable-ID folder projection · Dropbox account access required</p>'+nav+'<div class="notice">For missing photographs, the linked image is an existing identification reference. Its containing folder is listed alongside it. Image roles, finish and exact-size limitations remain visible in the details.</div><div class="toolbar"><label for="search">Find a sculpture</label><input id="search" type="search" placeholder="Name, finish, option ID or image role"><span id="shown">'+str(count)+' rows shown</span></div>'+body+'<p class="muted">All157 required picture actions are listed across the four categories.53 optional series-image suggestions remain in the master. The Fingerprint reference documents do not close its four isolated-photo gaps. Stable IDs and native paths were verified within the saved audit scope; no full live HTTP/access audit is claimed.</p></main><script>'+script+'</script></body></html>'
def fingerprint_section():
 rows=[]
 for bind in bindings:
  opt=byid[bind['product_id']];im=objects[opt['file_id']];parent=objects[im['current_parent_id']]
  rows.append('<tr class="task fingerprint" data-option="'+esc(opt['product_id'])+'"><td class="name"><strong>'+esc(opt['name'])+'</strong><small>'+esc(opt['product_id'])+'</small><span class="tag">Isolated individual image still missing</span></td><td class="links">'+a(bind['component_folder_url'],'Component folder')+a(bind['finish_folder_url'],bind['finish']+' finish folder')+'</td><td class="links">'+a(im['current_native_url'],'Example pair image')+a(parent['current_native_url'],'Containing image folder')+'</td><td class="action">'+a(bind['reference_document_url'],'All pair/group references')+'<p>The folder split is complete. Keep the two components separate; retain this photograph as arrangement evidence. Source composition2 contains both accepted components.</p><details><summary>Stable IDs</summary><code>Component '+esc(bind['component_folder_id'])+'<br>Finish '+esc(bind['finish_folder_id'])+'<br>Reference document '+esc(bind['reference_document_id'])+'<br>Example image '+esc(im['file_id'])+'<br>Image folder '+esc(parent['file_id'])+'</code></details></td></tr>')
 return '<section id="fingerprint"><h2>Fingerprint — component folders</h2><p>Two accepted components, each with White and Verdigris finish folders. Pair images remain in '+a(next(x['current_native_url']for x in overlay['created_folders']if x['role']=='PAIR_GROUP_AND_CONTEXT_IMAGES'),'Arrangements')+'.</p><div class="table-wrap"><table><thead><tr><th>Component / finish</th><th>Component folders</th><th>Existing image and containing folder</th><th>References and outstanding work</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table></div></section>'
def action_section(key,title,items):
 rows=[]
 for x in items:
  r=x['reference'];bind=binding_by_id.get(x['option_id']);extra=a(bind['finish_folder_url'],'Separate component/finish folder')if bind else ''
  details='<details><summary>Qualification and stable IDs</summary><p>'+esc(x['qualification'])+'</p><p>'+esc(x['scope'])+'</p><code>Image '+esc(r['file_id'])+'<br>Containing folder '+esc(r['folder_id'])+'</code></details>'
  rows.append('<tr class="task action" data-option="'+esc(x['option_id'])+'" data-role="'+esc(x['role'])+'"><td class="name"><strong>'+esc(x['name'])+'</strong><small>'+esc(x['option_id'])+'</small><span class="tag">'+esc(x['role'])+' · '+esc(x['action_type'])+'</span></td><td class="links">'+a(r['image_url'],'Existing image to check'if x['action_type']=='Verify existing image'else'Example / reference image')+'</td><td class="links">'+a(r['folder_url'],'Containing folder')+extra+'</td><td class="action">'+esc(x['action'])+details+'</td></tr>')
 return '<section id="'+key+'"><h2>'+esc(title)+'</h2><div class="table-wrap"><table><thead><tr><th>Sculpture / option</th><th>Existing image</th><th>Containing folder</th><th>Required action</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table></div></section>'
def csv_write(name,items):
 with(OUT/name).open('w',newline='',encoding='utf-8-sig')as f:
  keys=['priority','option_id','name','role','action_type','status','action','image_url','folder_url','file_id','folder_id','component_finish_folder_url','qualification','scope'];w=csv.DictWriter(f,fieldnames=keys);w.writeheader()
  for x in items:
   r={k:x.get(k,'')for k in ['priority','option_id','name','role','action_type','status','action','qualification','scope']};r.update({k:x['reference'][k]for k in ['image_url','folder_url','file_id','folder_id']});r['component_finish_folder_url']=binding_by_id.get(x['option_id'],{}).get('finish_folder_url','');w.writerow(r)
cards='<div class="stats">'+''.join(f'<a href="#{key}">{esc(title)}</a>'for key,title,_,_ in groups)+'</div>'
body=cards+fingerprint_section()+''.join(action_section(k,t,items)for k,t,_,items in groups)
(OUT/'index.html').write_text(page('Boldstone — all required image and folder links',body,161))
(OUT/'01-fingerprint-folders.html').write_text(page('Fingerprint — component and reference folders',fingerprint_section(),4))
for key,title,file,items in groups:
 csvname=file.removesuffix('.html')+'.csv';csv_write(csvname,items)
 (OUT/file).write_text(page(title,'<p><a class="download" href="'+csvname+'">Download this list as CSV</a></p>'+action_section(key,title,items),len(items)))
csv_write('all-required-picture-actions.csv',actions)
# Preserve the established three-list convenience exports with current paths.
csv_write('Missing_Pictures_Required_2026-10-21.csv',actions)
csv_write('Missing_Individual_Images_2026-10-21.csv',groups[0][3])
csv_write('Optional_Series_Images_2026-10-21.csv',[x for x in audit['missing_pictures']if x['status']=='Optional'])
class Check(HTMLParser):
 def __init__(self):super().__init__();self.rows=collections.Counter();self.hrefs=[]
 def handle_starttag(self,tag,attrs):
  d=dict(attrs)
  if tag=='tr'and'task'in d.get('class','').split():self.rows['fingerprint'if'fingerprint'in d['class'].split()else'action']+=1
  if tag=='a':self.hrefs.append(d.get('href',''))
receipts=[]
for p in sorted(OUT.glob('*.html')):
 c=Check();c.feed(p.read_text());expected=161 if p.name=='index.html'else 4 if p.name.startswith('01-')else next(len(x[3])for x in groups if x[2]==p.name)
 assert sum(c.rows.values())==expected,(p.name,c.rows)
 assert all(u.startswith('https://www.dropbox.com/')or u.startswith('#')or(OUT/u).is_file()for u in c.hrefs),(p.name,'bad href')
 if p.name=='index.html':
  assert c.rows=={'fingerprint':4,'action':157}
  for x in actions:assert x['reference']['image_url']in c.hrefs and x['reference']['folder_url']in c.hrefs
 receipts.append({'path':str(p),'sha256':digest(p),'task_rows':dict(c.rows),'link_count':len(c.hrefs)})
result={'status':'PASS_COMPLETE_LINK_REPORTS','recorded_utc':datetime.now(timezone.utc).isoformat(),'output_directory':str(OUT),'pages':receipts,
 'categories':{title:len(items)for _,title,_,items in groups},'individual_gap_types':audit['counts']['individual_statuses'],'all157_actions_have_image_and_folder_links_and_IDs':True,
 'four_separate_component_finish_bindings':True,'csv_files':[{'path':str(p),'sha256':digest(p)}for p in sorted(OUT.glob('*.csv'))],
 'input_audit_sha256':digest(HERE/'image-coverage-current.json'),'input_register_sha256':digest(HERE/'canonical-master-register.json'),'platform_or_Dropbox_writes':0}
(HERE/'link-report-verification.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'status':result['status'],'pages':len(receipts),'required_actions':157,'fingerprint_bindings':4}))
