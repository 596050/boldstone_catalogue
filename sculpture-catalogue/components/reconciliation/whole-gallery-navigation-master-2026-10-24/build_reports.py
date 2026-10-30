"""Refresh existing support reports and expose all current options and galleries."""
import csv
from datetime import datetime, timezone
import hashlib
import html
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import shutil
from urllib.parse import parse_qs, quote, unquote, urlparse

H = Path(__file__).resolve().parent
B = H.parents[2]
ROOT = B.parent
OUT = B/'outputs'/H.name
OUT.mkdir(exist_ok=True)
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
write = lambda p,v: Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
esc = lambda x: html.escape(str(x),quote=True)
old_pointer = read(H/'inputs/pointer.before')
OLDH = (B/old_pointer['register']).parent
src = read(OLDH/'report-verification.json')
OLD = Path(src['output_directory'])
g = read(H/'canonical-master-register.json')
gallery = read(H/'complete-gallery-evidence-reference.json')
native = read(H/'current-native-reference-map.json')['current_objects']
assets = read(H/'current-assets.json')
oldassets = read(H/'inputs/asset_map.before')
oldnative = read(H/'inputs/native_map.before')['current_objects']
replacements = read(B/'components/parallel-reviews/held-identities-resumption-01a16dbc-20261024/deleted-reference-resolution/proposed-reference-replacements.json')['changes']
rid = {c['before']['file_id']:c['proposed']['file_id'] for c in replacements}
def norm(url):
    u=urlparse(url or '');p=unquote(u.path)
    for pre in ['/home','/preview']:
        if p.startswith(pre+'/'):p=p[len(pre):];break
    q=parse_qs(u.query)
    return p.rstrip('/')+('/'+q['preview'][0] if q.get('preview') else '')
file_targets={}
current_by_url={}
for fid,row in native.items():
    if row.get('object_type')=='file' and row.get('current_wall_snapshot_present'):
        current_by_url[norm(row['image_url'])]=fid
        if oldassets.get(fid,{}).get('image_url'):file_targets[norm(oldassets[fid]['image_url'])]=row['image_url']
for c in replacements:file_targets[norm(c['before']['image_url'])]=c['proposed']['image_url']
folder_targets={norm(v.get('folder_url') or 'https://www.dropbox.com/home'+quote(v['display_path'],safe='/')):native[fid]['folder_url'] for fid,v in oldnative.items() if (v.get('folder_url') or v.get('display_path')) and fid in native and native[fid].get('object_type')=='folder' and native[fid].get('folder_url')}
def refresh(url):
    if not url.startswith('https://www.dropbox.com/'):return url
    key=norm(url)
    if key in file_targets and norm(file_targets[key])!=key:return file_targets[key]
    if key in folder_targets and norm(folder_targets[key])!=key:return folder_targets[key]
    return url
notice='<section><strong>Current references:</strong> 188 active options. All6,360 current Wall images and562 platform-gallery entries have recorded visual roles. Current example links are refreshed; dated source narratives retain their original scope. <a href="index.html">Current option/specification index and complete image evidence</a>. Accepted estimates and owner holds remain qualified.</section>'
pages={};thumbnails=[];csv_files=[];csv_edits=[]
for x in src['thumbnail_files']:
    source=Path(x['path']);assert sha(source)==x['sha256'];dest=OUT/source.relative_to(OLD);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest);thumbnails.append({**x,'path':str(dest)})
for x in src['pages']:
    source=Path(x['path']);assert sha(source)==x['sha256'];text=source.read_text().replace(str(OLD),str(OUT));text=re.sub(r'<section><strong>Current (?:position|catalogue|references):</strong>.*?</section>','',text,flags=re.S)
    last=[None]
    def anchor(match):
        url=refresh(html.unescape(match.group(2)));key=norm(url)
        if key in current_by_url:last[0]=current_by_url[key]
        elif last[0] and url.startswith('https://www.dropbox.com/home'):
            url=native[last[0]]['folder_url'];last[0]=None
        return match.group(1)+esc(url)+match.group(3)
    text=re.sub(r'(<a\b[^>]*?\bhref=")([^"]*)(")',anchor,text);text=text.replace('</h1>','</h1>'+notice,1);dest=OUT/source.name;dest.write_text(text);pages[dest.name]={'path':str(dest),'sha256':sha(dest)}
for x in src['csv_files']:
    source=Path(x['path']);assert sha(source)==x['sha256'];dest=OUT/source.name
    with source.open(encoding='utf-8-sig',newline='') as f:reader=csv.DictReader(f);headers=reader.fieldnames;rows=list(reader)
    for number,row in enumerate(rows,2):
        primary=None
        for key in ['file_id','individual_file_id','reference_file_id','primary_file_id','dropbox_file_id']:
            if row.get(key):primary=rid.get(row[key],row[key]);break
        for key,value in list(row.items()):
            if value is None:continue
            new=value
            if key in ['image_url','folder_url','individual_image','containing_folder','individual_folder','context_image_url','context_folder_url']:new=refresh(value)
            if key in ['file_id','individual_file_id','reference_file_id','primary_file_id','dropbox_file_id'] and value in rid:new=rid[value]
            if primary in native and native[primary].get('current_wall_snapshot_present') and native[primary].get('object_type')=='file':
                if key in ['folder_id','individual_folder_id','reference_folder_id','dropbox_folder_id']:new=native[primary]['folder_id']
                if key in ['folder_url','individual_folder','containing_folder']:new=native[primary]['folder_url']
            if new!=value:row[key]=new;csv_edits.append({'file':source.name,'row':number,'field':key,'before':value,'current':new})
        if source.name=='Current_Primary_Navigation_48.csv':
            proof=next((c for c in replacements if c['option_id']==row.get('option_id')),None)
            if proof:
                updates={'navigation_status':'CURRENT_EQUIVALENT_PHOTOGRAPH_REFERENCE_VERIFIED','file_verified':'True','folder_verified':'True',
                    'readback_utc':read(B/'components/parallel-reviews/held-identities-resumption-01a16dbc-20261024/deleted-reference-resolution/proposed-reference-replacements.json')['recorded_utc'],
                    'scope':'Equivalent current photograph reference verified against direct native file/parent metadata and content hashes. Original selected ID '+proof['before']['file_id']+' and deleted-file history remain in the current reference-resolution JSON. No new pattern, physical specimen, or fitted-specification confirmation.'}
                for key,value in updates.items():
                    if row.get(key)!=value:csv_edits.append({'file':source.name,'row':number,'field':key,'before':row.get(key),'current':value});row[key]=value
    if any(r['file']==source.name for r in csv_edits):
        with dest.open('w',encoding='utf-8-sig',newline='') as f:writer=csv.DictWriter(f,fieldnames=headers);writer.writeheader();writer.writerows(rows)
    else:shutil.copy2(source,dest)
    csv_files.append({**x,'path':str(dest),'sha256':sha(dest)})
css='body{font:17px/1.5 system-ui;max-width:1200px;margin:2rem auto;padding:0 1rem;color:#222}nav{padding:1rem;background:#eef2f5}article{border-top:1px solid #aaa;padding:1rem 0;overflow-wrap:anywhere}table{border-collapse:collapse;width:100%}th,td{vertical-align:top;text-align:left;border-bottom:1px solid #ddd;padding:.6rem}th{width:24%}small{font-size:13px}details{margin:1rem 0}.retired{background:#f2f2f2}'
def local(path):return quote(os.path.relpath(path,OUT),safe='/')
def link(path,title):return '<a href="'+esc(local(path))+'">'+esc(title)+'</a>'
parts=['<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Current Boldstone sculpture catalogue</title><style>'+css+'</style></head><body><h1>Boldstone sculpture catalogue</h1>',
    '<p>188 active individual finish, size or build options.112 retained component IDs project to110 working design groups. These are catalogue counts; physical stock and a final whole-library unique sculpture count remain unverified.</p>',
    '<nav>'+link(gallery['readers']['products'],'Full image evidence for every option')+' · '+link(gallery['readers']['platform_galleries'],'All Squarespace and local Shopify galleries')+' · '+link(gallery['native_complete_reader'],'All6,360 current images and containing folders')+' · '+link(ROOT/'reports/local-platform-crosswalk-corrected-20261024-root/index.html','Matched and unmatched local platform records')+'</nav>',
    '<p>All6,360 current Wall images in60 families and445 Squarespace/117 Shopify gallery entries have been reviewed.29 Squarespace and3 Shopify entries retain uncertain exact-photo correspondences.65 catalogue options have no existing platform-source association;625 current files retain family scope. Group/context photographs do not create new sculptures or confirm specifications.</p>',
    '<p>Two Wall Circle selected references now use verified current equivalents, with original deleted-file history retained. Two context links are refreshed by unchanged IDs.22 installation and one series requirement remain deferred. All current Frozen Fish dimensions remain70 H ×15 W cm; the legacy identity question remains deferred.</p>',
    '<p>'+link(OUT/'specifications-to-verify.html','Specification checklist')+' · '+link(OUT/'remaining-photograph-requests.html','Retained photograph requirements')+' · '+link(OUT/'current-primary-navigation-health.html','Two equivalent reference resolutions')+'</p>']
for o in g['options']:
    active=o['counted_as_individual_option'];parts.append('<article id="'+esc(o['product_id'])+'"'+(' class="retired"' if not active else '')+'><h2>'+esc(o['name'])+(' (retired history)' if not active else '')+'</h2>')
    if o.get('image_url'):parts.append('<p><a href="'+esc(o['image_url'])+'">Current example image</a> · <a href="'+esc(o['folder_url'])+'">Actual containing folder</a></p>')
    parts.append('<small>'+esc(o['product_id'])+' · '+esc(o.get('file_id',''))+' · '+esc(o.get('folder_id',''))+'</small>')
    if o.get('current_context_navigation',{}).get('current_reference_verified') is False:parts.append('<p>The approved historical context image is currently unavailable in the checked Master scope. Its source-photo evidence and owner deferral remain retained.</p>')
    parts.append('<details><summary>All six working specifications and their evidence states</summary><table>')
    for field,v in o['master_fields'].items():parts.append('<tr><th>'+esc(field)+'</th><td>'+esc(v['display']).replace('\n','<br>')+'<br><small>'+esc(v['state']).replace('\n','<br>')+'</small></td></tr>')
    parts.append('</table></details></article>')
parts.append('</body></html>');(OUT/'index.html').write_text('\n'.join(parts)+'\n');pages['index.html']={'path':str(OUT/'index.html'),'sha256':sha(OUT/'index.html')}
health=read(H/'current-primary-navigation-health.json');cards=[]
for row in health['current_resolutions']:
    old=row['previous_navigation_observation'];cards.append('<article id="'+esc(row['product_id'])+'"><h2>'+esc(row['name'])+'</h2><p><a href="'+esc(row['image_url'])+'">Current equivalent image</a> · <a href="'+esc(row['verified_folder_url'])+'">Actual containing folder</a></p><p>'+esc(row['comparison']['visual_result'])+'</p><p>Current ID: '+esc(row['file_id'])+'<br>Original selected ID retained in history: '+esc(old['file_id'])+'</p><p>Pattern identity, physical specification and owner holds remain unchanged.</p></article>')
(OUT/'current-primary-navigation-health.html').write_text('<!doctype html><meta charset="utf-8"><title>Current selected references</title><style>'+css+'</style><h1>Current selected references</h1>'+''.join(cards));pages['current-primary-navigation-health.html']={'path':str(OUT/'current-primary-navigation-health.html'),'sha256':sha(OUT/'current-primary-navigation-health.html')}
count_path=OLD/'current-count-summary.json'
if count_path.is_file():
    count=read(count_path);count['current_option_list']={'path':str(OUT/'Current_Individual_Options_188.csv'),'sha256':sha(OUT/'Current_Individual_Options_188.csv'),'rows':188};count['complete_gallery_mapping']=gallery['counts'];write(OUT/'current-count-summary.json',count)
requests=OLD/'remaining-photograph-requests.json'
if requests.is_file():shutil.copy2(requests,OUT/requests.name)
write(H/'current-csv-navigation-changes.json',csv_edits)
class Parser(HTMLParser):
    def __init__(self):super().__init__();self.ids=set();self.links=[];self.images=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if a.get('id'):self.ids.add(a['id'])
        if tag=='a':self.links.append(a.get('href',''))
        if tag=='img':self.images.append(a.get('src',''))
parsed={};failures=[]
for item in pages.values():
    path=Path(item['path']).resolve();parser=Parser();parser.feed(path.read_text());parsed[path]=parser
for path,parser in list(parsed.items()):
    for url in parser.links:
        if url.startswith(('https://','http://','mailto:')):continue
        part,_,anchor=url.partition('#');dest=(path.parent/unquote(part)).resolve() if part and not Path(unquote(part)).is_absolute() else (Path(unquote(part)).resolve() if part else path)
        if not dest.is_file():failures.append({'page':str(path),'url':url,'reason':'missing local file'});continue
        if anchor and dest.suffix=='.html':
            if dest not in parsed:other=Parser();other.feed(dest.read_text());parsed[dest]=other
            if anchor not in parsed[dest].ids:failures.append({'page':str(path),'url':url,'reason':'missing anchor'})
    for url in parser.images:
        if not (path.parent/unquote(url)).is_file():failures.append({'page':str(path),'url':url,'reason':'missing local image'})
report={'status':'FAIL' if failures else 'PASS_CURRENT_REPORTS', 'recorded_utc':datetime.now(timezone.utc).isoformat(),
    'output_directory':str(OUT),'pages':list(pages.values()),'csv_files':csv_files,'thumbnail_files':thumbnails,
    'register_sha256':sha(H/'canonical-master-register.json'),'audit_sha256':sha(H/'image-coverage-current.json'),
    'counts':{**src['counts'],**gallery['counts']},'csv_navigation_field_edits':len(csv_edits),'failures':failures[:100],
    'source_report_manifest':{'path':str(OLDH/'report-verification.json'),'sha256':sha(OLDH/'report-verification.json')},
    'no_physical_or_commercial_field_changes':True,'native_or_platform_writes':0}
write(H/'report-verification.json',report)
print(json.dumps({'status':report['status'],'pages':len(pages),'csv_files':len(csv_files),'csv_navigation_field_edits':len(csv_edits),'failures':failures[:12]},indent=2))
if failures:raise SystemExit(1)
