"""Freeze Google-only catch-up jobs from confirmed Meta publications."""
import concurrent.futures
import hashlib
import html
import json
import re
import sqlite3
import subprocess
import sys
import urllib.request
from pathlib import Path
from urllib.parse import urlencode,urlparse,urlunparse

ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'social-publisher'))
from common import atomic_json,digest,read_json,utc

BATCH='google-social-catchup-20261120'
if (OUT/'manifest.json').exists():
    raise SystemExit('The catch-up manifest is frozen. Resume its recorded jobs instead of rebuilding its coverage.')
MASTER=ROOT/'outputs/channel-completion-20261108/master-platform-values.json'
mapping=read_json(MASTER);master_hash=digest(MASTER.read_bytes())
proofs={};candidates={};google={}

def add_proof(pid,platform,url,source,verified=None):
    pattern=r'https://(?:www\.)?instagram\.com/(?:[^/]+/)?(?:p|reel)/' if platform=='instagram' else r'https://(?:www\.)?facebook\.com/'
    assert re.match(pattern,url),(pid,url)
    proofs.setdefault(pid,[]).append({'platform':platform,'url':url,'source':source,'verified_utc':verified})

def add_candidate(pid,p,source,preference=0):
    media=p.get('media_path') or p.get('media')
    if isinstance(media,str) and Path(media).is_file():
        candidates.setdefault(pid,[]).append((preference,source,p,Path(media).resolve()))

db=sqlite3.connect('file:'+str(ROOT/'social-publisher/state/outbox.sqlite3')+'?mode=ro',uri=True)
for job_id,raw,state,receipt in db.execute('SELECT id,payload,state,receipt FROM jobs'):
    p=json.loads(raw);r=json.loads(receipt) if receipt else None
    if state not in {'PUBLISHED','HISTORICAL_VERIFIED'}:continue
    if p['platform'] in {'facebook','instagram'}:
        add_proof(p['catalogue_id'],p['platform'],r['native_url'],'outbox:'+job_id,r.get('verified_utc'))
        add_candidate(p['catalogue_id'],{**p,'sha256':p['media_sha256']},'outbox:'+job_id,100 if p['platform']=='instagram' else 90)
    elif p['platform']=='google_business_profile':
        assert digest(Path(r['evidence_path']).read_bytes())==r['evidence_sha256']
        google[p['catalogue_id']]={'job_id':job_id,'payload':p,'receipt':r}
db.close()
for file in sorted((ROOT/'outputs').glob('*/*-publication-receipts.json')):
    platform=next((p for p in ['facebook','instagram'] if file.name==p+'-publication-receipts.json'),None)
    if platform is None:continue
    rows=read_json(file)
    if not isinstance(rows,list):continue
    for row in rows:
        if row.get('catalogue_id') and str(row.get('status','')).startswith('PUBLISHED') and (row.get('full_caption_readback') or row.get('full_product_text_readback')):
            add_proof(row['catalogue_id'],platform,row['url'],str(file.relative_to(ROOT)),row.get('verified_utc'))
for pid,p in mapping.items():
    for platform in ['instagram','facebook']:
        url=p.get(platform+'_post_url')
        if url:add_proof(pid,platform,url,str(MASTER.relative_to(ROOT)),p.get(platform+'_checked_utc'))

source_files=list((ROOT/'outputs').glob('social*/posts*.json'))
source_files += [ROOT/x for x in [
 'outputs/platform-completion-20261105/instagram-four-posts.json',
 'outputs/furnitures-faire-instagram-20261106/instagram-five-posts.json',
 'outputs/furnitures-faire-instagram-20261107-additional/instagram-five-posts.json',
 'outputs/instagram-marketplace-next-channels-20261107-1324/instagram-five-posts.json',
 'outputs/channel-completion-20261108/social-five-products.json',
 'outputs/product-social-approval-20261108/linkedin-ten-posts.json']]
for file in sorted(set(source_files)):
    rows=read_json(file)
    if isinstance(rows,list):
        for p in rows:
            if p.get('catalogue_id'):add_candidate(p['catalogue_id'],p,str(file.relative_to(ROOT)),50 if p.get('captions',{}).get('instagram') else 40)

def normalized(value):return ' '.join(html.unescape(value).split()).casefold()

def google_caption(title,caption):
    caption=re.sub(r'https?://\S+','',caption)
    caption=re.sub(r'#\w+','',caption)
    caption=re.sub(r'(?i)\bTap (?:the )?(?:tagged product|product tag|tag)\b[^\n.!?]*(?:[.!?]|$)','',caption)
    caption=re.sub(r'(?i)\bBrowse the collection through the link in our bio\b[^\n.!?]*(?:[.!?]|$)','',caption)
    caption=re.sub(r'(?im)[^\n.!?]*\blink in (?:our |the )?bio\b[^\n.!?]*(?:[.!?]|$)','',caption)
    parts=[]
    for part in caption.split('\n\n'):
        part=part.strip()
        if not part:continue
        if re.match(r'(?i)^(?:Shop this sculpture|View this sculpture and order|For homes, gardens and design projects\. View|See the sculpture, current price|Explore this sculpture using the button)',part):continue
        parts.append(part)
    caption='\n\n'.join(parts)
    if not normalized(caption).startswith(normalized(title)):caption=title+'\n\n'+caption
    caption+='\n\nUse the Buy button to view this sculpture.'
    assert len(caption)<=1500,(title,len(caption))
    assert not re.search(r'(?i)product tag|tagged product|link in (?:our |the )?bio|https?://|#\w',caption),(title,caption)
    return caption

def dimensions(path):
    result=subprocess.run(['/usr/bin/sips','-g','pixelWidth','-g','pixelHeight',str(path)],capture_output=True,text=True,check=True,timeout=20)
    width=int(re.search(r'pixelWidth:\s*(\d+)',result.stdout).group(1));height=int(re.search(r'pixelHeight:\s*(\d+)',result.stdout).group(1))
    return width,height

records=[];coverage=[]
live_google=read_json(OUT/'boldstone_google_business_profile-initial.json')
for pid in sorted(proofs):
    if pid in google:
        previous=google[pid]
        assert normalized(previous['payload']['caption']) in normalized(live_google['text'])
        coverage.append({'catalogue_id':pid,'title':previous['payload']['title'],'meta_sources':proofs[pid],
                         'status':'ALREADY_GOOGLE_VERIFIED','google_receipt':previous['receipt']})
        continue
    assert candidates.get(pid),('Missing original source photograph',pid)
    options=sorted(candidates[pid],key=lambda item:item[0],reverse=True)
    preference,source,p,original=next(item for item in options if item[2].get('caption') or item[2].get('captions'))
    original_hash=digest(original.read_bytes());expected=p.get('sha256') or p.get('media_sha256')
    if expected:assert original_hash==expected,('Original source hash changed',pid,source)
    m=mapping[pid];title=p.get('title') or m.get('Retail / website name') or m['Sculpture']
    caption=p.get('captions',{}).get('instagram') or p.get('caption')
    website=p.get('website_url') or p.get('website') or m.get('pinterest_link')
    parsed=urlparse(website or '')
    assert parsed.scheme=='https' and parsed.hostname=='boldstonesculpture.com' and parsed.path.startswith('/buy/p/'),(pid,website)
    website=urlunparse(parsed._replace(query='',fragment=''))
    target=original;encoding='original unchanged'
    if original.stat().st_size>5_000_000:
        (OUT/'media').mkdir(exist_ok=True)
        target=OUT/'media'/(pid+'.png')
        if not target.exists():
            subprocess.run(['/usr/bin/sips','-Z','1600','-s','format','png',str(original),'--out',str(target)],capture_output=True,check=True,timeout=30)
            if target.stat().st_size>5_000_000:
                subprocess.run(['/usr/bin/sips','-Z','1400',str(target),'--out',str(target)],capture_output=True,check=True,timeout=30)
        encoding='Google size copy: proportional downsample, PNG; original retained'
    width,height=dimensions(target)
    assert target.stat().st_size<=5_000_000 and min(width,height)>=250,(pid,width,height,target.stat().st_size)
    target_hash=digest(target.read_bytes())
    purchase=website+'?'+urlencode({'utm_source':'google_business_profile','utm_medium':'social','utm_campaign':'sculpture_catchup_20261120','utm_content':p.get('sku') or m.get('SKU') or pid})
    record={'catalogue_id':pid,'sku':p.get('sku') or m.get('SKU'),'title':title,'media_path':str(target.resolve()),
            'sha256':target_hash,'width':width,'height':height,'bytes':target.stat().st_size,
            'original_media_path':str(original),'original_sha256':original_hash,'encoding':encoding,
            'source_record':source,'source_record_sha256':digest((ROOT/source).read_bytes()) if not source.startswith('outbox:') else None,
            'source_meta_caption':caption,'meta_sources':proofs[pid],'website_url':website,
            'alt_text':p.get('alt_text') or title+' sculpture, in the photograph used for its Meta post.',
            'captions':{'google_business_profile':google_caption(title,caption)},
            'tracked_urls':{'google_business_profile':purchase},'status':'PREPARED_NOT_PUBLISHED'}
    records.append(record);coverage.append({'catalogue_id':pid,'title':title,'meta_sources':proofs[pid],'status':'GOOGLE_MISSING'})

def inspect_product(p):
    request=urllib.request.Request(p['website_url'],headers={'User-Agent':'Mozilla/5.0'})
    with urllib.request.urlopen(request,timeout=35) as response:
        raw=response.read(6_000_001);status=response.status;final=response.url
    assert status==200 and len(raw)<=6_000_000,(p['catalogue_id'],status)
    source=raw.decode();products=[]
    def visit(obj):
        if isinstance(obj,list):
            for child in obj:visit(child)
        elif isinstance(obj,dict):
            if obj.get('@type')=='Product':products.append(obj)
            for key in ['@graph','mainEntity']:visit(obj.get(key))
    for script in re.findall(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',source,re.S|re.I):
        try:visit(json.loads(script))
        except json.JSONDecodeError:pass
    assert products,(p['catalogue_id'],'No Product structured data')
    product=products[0]
    assert normalized(p['title']) in normalized(product.get('name','')),(p['catalogue_id'],p['title'],product.get('name'))
    return {'catalogue_id':p['catalogue_id'],'title':product['name'],'url':final,'http':status,'html_sha256':digest(raw),'checked_utc':utc()}

atomic_json(OUT/'prepared-posts.json',records)
atomic_json(OUT/'coverage-inventory.json',{'utc':utc(),'batch_id':BATCH,'distinct_meta_sculptures':len(proofs),
            'already_google':len(google),'missing_google':len(records),'master_source_sha256':master_hash,'sculptures':coverage})
results=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    futures={pool.submit(inspect_product,p):p for p in records}
    for future in concurrent.futures.as_completed(futures):
        p=futures[future]
        try:results.append(future.result())
        except Exception as error:results.append({'catalogue_id':p['catalogue_id'],'error':str(error)})
        atomic_json(OUT/'website-checks.json',results)
errors=[r for r in results if r.get('error')]
assert not errors,errors
print(json.dumps({'confirmed_meta_sculptures':len(proofs),'already_google':len(google),'google_deliveries_prepared':len(records),
                  'original_files_kept':len(records),'google_size_copies':sum(p['encoding']!='original unchanged' for p in records),
                  'product_pages_verified':len(results),'publish_clicks':0},ensure_ascii=False),flush=True)
