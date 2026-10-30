import hashlib,json
from pathlib import Path
project=Path(__file__).resolve().parents[1];ev=project/'evidence';base=Path('/Users/tprice/Library/Application Support/BoldstoneImageConsistency')
pointer=json.loads((base/'CURRENT-CANONICAL-ASSET-REGISTRY.json').read_text());ref=pointer['registry'];raw=Path(ref['path']).read_bytes();assert hashlib.sha256(raw).hexdigest()==ref['sha256'];registry=json.loads(raw)
live={x['file_id'] for x in json.loads((ev/'wall_inventory_2026-10-16.json').read_text())['entries']}
redirect=dict(registry['redirects']);evidence=[]
for r in registry['all_642_effective_source_bindings']:
    redirect[r['source_id']]=r['current_successor_id']
for r in registry['duplicate_asset_associations']:redirect[r['old_file_id']]=r['canonical_file_id']
def resolve(fid):
    seen=set()
    while fid not in live and fid in redirect and fid not in seen:seen.add(fid);fid=redirect[fid]
    return fid if fid in live else None
groups_path=base/'review-20261015T223009Z/native-duplicate-groups.json';group_bytes=groups_path.read_bytes();groups=json.loads(group_bytes)
for r in groups:
    present={fid for fid in r['file_ids'] if fid in live}
    if not present:present={resolve(fid) for fid in r['file_ids']} - {None}
    if len(present)==1:
        target=next(iter(present))
        for fid in r['file_ids']:
            if fid not in live and fid not in redirect:redirect[fid]=target
        evidence.append(dict(group_hash=r['content_hash'],historical_ids=r['file_ids'],current_candidate=target,scope='Historical duplicate/lineage candidate; current download hash must still be verified'))
aliases={old:resolve(old) for old in redirect if resolve(old) and old not in live}
payload=dict(registry_reference=ref,duplicate_groups_reference=dict(path=str(groups_path),sha256=hashlib.sha256(group_bytes).hexdigest()),aliases=aliases,evidence=evidence)
(ev/'source_id_lineage.json').write_text(json.dumps(payload,ensure_ascii=False))
cache=json.loads((ev/'image_review_cache_index.json').read_text());new=0
for old,r in list(cache.items()):
    target=aliases.get(old)
    if target and target not in cache and Path(r['local_path']).is_file():
        cache[target]={**r,'id':target,'lineage_source_id':old,'lineage_candidate':True,'current_download_verified':False};new+=1
(ev/'image_review_cache_index.json').write_text(json.dumps(cache,ensure_ascii=False))
feature=ev/'current_cache_image_features.pickle'
if feature.exists():feature.unlink()
print(json.dumps(dict(resolved_historical_ids=len(aliases),added_cached_candidates=new,all_candidates_require_current_binary_check=True)))
