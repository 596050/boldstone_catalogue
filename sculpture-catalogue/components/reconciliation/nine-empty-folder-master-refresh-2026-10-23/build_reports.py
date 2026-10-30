"""Retain current catalogue views and add the nine completed empty-folder histories."""
import csv,hashlib,html,json,re,shutil
from pathlib import Path
from html.parser import HTMLParser
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;B=H.parents[2];OUT=B/'outputs'/H.name;read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();esc=lambda x:html.escape(str(x),quote=True)
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
m=read(H/'input-manifest.json');source=read(m['source_report_verification']['snapshot']);oldout=Path(source['output_directory']);OUT.mkdir(exist_ok=True);history=read(H/'removed-empty-folder-history.json');pages=[];csvs=[];images=[]
notice='<section><strong>Current folder refresh:</strong> nine already-removed empty folders are recorded in '+ '<a href="completed-changes.html">the folder history</a>. No photograph, sculpture option, working specification or image-role decision changed. The four qualified display reviews below remain earlier evidence. Current photography gaps remain44 in situ and17 series.</section>'
for x in source['pages']+source['csv_files']+source['thumbnail_files']:assert sha(x['path'])==x['sha256']
for x in source['thumbnail_files']:
 src=Path(x['path']);dest=OUT/src.relative_to(oldout);dest.parent.mkdir(exist_ok=True,parents=True);shutil.copy2(src,dest);assert sha(dest)==x['sha256'];images.append({**x,'path':str(dest)})
for x in source['csv_files']:
 dest=OUT/Path(x['path']).name;shutil.copy2(x['path'],dest);assert sha(dest)==x['sha256'];csvs.append({**x,'path':str(dest)})
for x in source['pages']:
 src=Path(x['path']);dest=OUT/src.name;text=src.read_text().replace(str(oldout),str(OUT)).replace('</h1>','</h1>'+notice,1)
 if src.name=='imported-approvals.html':text=text.replace('Four reviewed display references and their qualifications','Retained qualified display references and their qualifications')
 dest.write_text(text);pages.append({**x,'path':str(dest),'sha256':sha(dest)})
template=(OUT/'index.html').read_text();css=re.search(r'<style>(.*?)</style>',template,re.S).group(1);cards=[];rows=[]
for x in history['folders']:
 parent=history['surviving_parent_metadata'][x['old_parent_id']];url='https://www.dropbox.com/home'+__import__('urllib.parse',fromlist=['quote']).quote(parent['path_display'],safe='/');cards.append('<article id="'+esc(x['file_id'])+'"><h2>'+esc(x['name'])+'</h2><p><strong>Removed while empty; retained as history.</strong></p><p>Family: '+esc(x['family'])+' · <a href="'+esc(url)+'">Surviving family folder</a></p><p>Historical folder path: '+esc(x['path_display'])+'</p><p>Folder ID: '+esc(x['file_id'])+'<br>Surviving family ID: '+esc(x['old_parent_id'])+'</p><p>No files were deleted. Existing sculpture records, image associations and photograph requests remain in force.</p></article>');rows.append({'family':x['family'],'historical_folder_name':x['name'],'removed_empty_folder_id':x['file_id'],'historical_path':x['path_display'],'surviving_family_folder_id':x['old_parent_id'],'surviving_family_folder_url':url,'status':'OWNER_REMOVED_WHILE_EMPTY_HISTORY_RETAINED','deleted_photographs':0,'image_roles_closed':0})
p=OUT/'completed-changes.html';p.write_text('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Nine completed empty-folder removals</title><style>'+css+'</style></head><body><main><h1>Nine completed empty-folder removals</h1><p>Two native removal packets are recorded in the current master. Nine historical folder IDs remain available; the six surviving family folders were checked against current metadata and87 direct children. <a href="index.html">Current photograph work</a></p>'+''.join(cards)+'</main></body></html>')
pages=[x for x in pages if Path(x['path']).name!='completed-changes.html']+[{'path':str(p),'sha256':sha(p),'cards':9}]
p=OUT/'Removed_Empty_Folders_9.csv'
with p.open('w',encoding='utf-8-sig',newline='')as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
csvs.append({'path':str(p),'sha256':sha(p),'rows':9});count=read(m['source_count_summary']['snapshot']);count['latest_empty_folder_history']={'completed_removals_recorded':9,'new_photograph_role_bindings':0,'history':'completed-changes.html'};write(OUT/'current-count-summary.json',count)
class Parser(HTMLParser):
 def __init__(self):super().__init__();self.cards=0;self.links=[];self.images=[]
 def handle_starttag(self,t,attrs):
  d=dict(attrs)
  if t=='article':self.cards+=1
  if t=='a':self.links.append(d.get('href',''))
  if t=='img':self.images.append(d.get('src',''))
for x in pages:
 z=Parser();z.feed(Path(x['path']).read_text());assert z.cards==x['cards'];assert all('BOLDSTONE_BACKUP'not in u.upper()for u in z.links);assert all('/BOLDSTONE%20MASTER/'in u.upper()for u in z.links if u.startswith('https://www.dropbox.com/'));assert all(u and(u.startswith('https://')or Path(u.split('#')[0]).is_file()or(OUT/u.split('#')[0]).is_file())for u in z.links);assert all((OUT/u).is_file()for u in z.images)
counts={**source['counts'],'new_individual_roles_closed':0,'new_owner_reference_exceptions':0,'new_finish_options':0,'in_situ_roles_closed':0,'owner_approval_packets_imported':0,'reopened_current_source_roles':0,'new_series_roles_closed':0,'reviewer_verified_display_bindings':0,'explicit_owner_image_role_approvals_added':0,'new_physical_verifications':0,'empty_folder_history_rows':9,'obsolete_folder_links_replaced':2}
result={'status':'PASS_CURRENT_LINKED_REPORTS','recorded_utc':datetime.now(timezone.utc).isoformat(),'output_directory':str(OUT),'pages':pages,'csv_files':csvs,'thumbnail_files':images,'counts':counts,'register_sha256':sha(H/'canonical-master-register.json'),'audit_sha256':sha(H/'image-coverage-current.json'),'pixels_edited':False,'native_file_revision_restores':0,'native_parent_folder_renames':0,'copied_image_bytes_verified':True,'source_report_sha256':m['source_report_verification']['sha256']};write(H/'report-verification.json',result);print(json.dumps({'status':result['status'],'empty_folder_history_rows':9,'in_situ_gaps':44,'series_gaps':17,'photograph_bindings_added':0}))
