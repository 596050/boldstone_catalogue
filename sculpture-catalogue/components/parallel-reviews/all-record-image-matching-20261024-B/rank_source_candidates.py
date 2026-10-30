"""Rank cached current-family photographs for human comparison, never auto-match."""
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
from PIL import Image, ImageChops, ImageOps, ImageStat

H = Path(__file__).resolve().parent
B = H.parents[2]
def read(p): return json.loads(Path(p).read_text())
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,d): Path(p).write_text(json.dumps(d, ensure_ascii=False, indent=2)+'\n')
run = Path(read(H/'current-work.json')['run'])
rows = read(run/'source-evidence/source-rendition-review-register.json')
images = {x['file_id']:x for x in read(run/'images.json') if x['inventory_status']=='CURRENT_NATIVE_FILE_AND_ACTUAL_PARENT_VERIFIED'}
p = read(B/'current-master.json'); g = read(B/p['register'])
edge = {x['offer_ref']:x for x in g['source_offer_edges']}
offers = {x['ref']:x for x in read(B/'components/evidence/offer_review_index.json')}
extra = read(B/'evidence/image_review_cache_index.json')
fresh_source_path = B.parent/'reports/dropbox-wall-complete-role-review-20261024T214349Z/current-6360-visual-source-evidence.json'
fresh_sources = {x['file_id']:x for x in read(fresh_source_path)}
index = {}
errors = []
for fid,row in images.items():
    saved = row.get('saved_asset_metadata') or {}
    bound = fresh_sources.get(fid,{})
    possible = [bound.get('source_image_path'), saved.get('thumb'), saved.get('full'), extra.get(fid,{}).get('local_path')]
    for location in possible:
        if not location or not Path(location).is_file(): continue
        try:
            with Image.open(location) as im:
                im = ImageOps.exif_transpose(im).convert('RGB')
                digest = sha(location)
                if location == bound.get('source_image_path'):
                    assert digest == bound['actual_visual_source_sha256']
                index[fid] = {'path':location, 'sha256':digest, 'dimensions':list(im.size),
                              'family':row['family'], 'analysis':im.resize((32,32),Image.Resampling.BILINEAR)}
            break
        except Exception as e:
            errors.append({'file_id':fid,'path':location,'error':str(e)})
families = defaultdict(list)
for fid,im in index.items(): families[im['family']].append(fid)

def family_scope(ref):
    se = edge[ref]['source_offer']
    fid = se.get('image_file_id')
    if fid in images: return [images[fid]['family']]
    # Source titles are used only to narrow candidate ranking, never as identity.
    title=offers[ref]['title'].lower()
    candidates=[f for f in families if f.lower() in title]
    if 'moon crater' in title or 'spherical' in title or ref in ['O005','O006','O007','O011','O064']: return ['Moon Crater Phase']
    return candidates

ranked=[]
for n,row in enumerate(rows):
    rendition=row.get('selected_rendition')
    if not rendition: continue
    with Image.open(rendition['path']) as im:
        im=ImageOps.exif_transpose(im).convert('RGB')
        small=im.resize((32,32),Image.Resampling.BILINEAR)
    scope=family_scope(row['offer_ref'])
    candidates=[fid for f in scope for fid in families[f]]
    if not candidates: candidates=list(index)
    scores=[]
    for fid in candidates:
        diff=ImageStat.Stat(ImageChops.difference(small,index[fid]['analysis'])).rms
        scores.append((math.sqrt(sum(v*v for v in diff)/3),fid))
    scores.sort()
    result={**row, 'candidate_family_scope':scope, 'candidate_count_screened':len(candidates),
            'ranking_is_identity_proof':False, 'ranked_candidates':[]}
    for score,fid in scores[:4]:
        image=images[fid];cached=index[fid]
        result['ranked_candidates'].append({'file_id':fid,'name':image['name'],'family':image['family'],
            'folder_id':image['folder_id'],'path':image['path'],'image_url':image['image_url'],
            'folder_url':image['folder_url'],'cached_path':cached['path'],'cached_sha256':cached['sha256'],
            'cached_dimensions':cached['dimensions'],'whole_frame_RGB_RMSE_32px':score,
            'current_native_source_binding':fresh_sources.get(fid),
            'status':'NUMERICAL_CANDIDATE_REQUIRES_VISUAL_COMPARISON'})
    ranked.append(result)
write(run/'source-evidence/ranked-source-candidates.json',ranked)
write(run/'source-evidence/ranking-summary.json',{'source_entries':len(ranked),'current_cached_file_ids':len(index),
    'fresh_visual_source_evidence':{'path':str(fresh_source_path),'sha256':sha(fresh_source_path)},
    'families':dict(Counter(v['family'] for v in index.values())), 'cache_errors':errors,
    'method':'EXIF-oriented full-frame RGB RMSE at32pixels peraxis, scoped to current source family where known. Triage only; no automatic identity decisions.',
    'graph_writes':0})
print(json.dumps({'source_entries':len(ranked),'current_cached_file_ids':len(index),'cache_errors':len(errors)}))
