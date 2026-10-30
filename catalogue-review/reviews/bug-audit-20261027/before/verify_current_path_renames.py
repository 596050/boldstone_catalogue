#!/usr/bin/env python3
"""Independent, full native readback of names, membership, content and links."""
import argparse
from collections import defaultdict
import csv
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sqlite3
import sys
import unicodedata
from urllib.parse import quote, urlsplit, urlunsplit

from renumber_current_paths import PROJECT, save, sha, now
from finish_current_path_batches import inventory, ReadAPI


def expected_prefix(path):
    parent=PurePosixPath(path).parent
    def normal(text):
        text=unicodedata.normalize('NFKD',text).encode('ascii','ignore').decode('ascii').lower()
        return re.sub(r'[^a-z0-9]+','-',text.replace('&',' and ')).strip('-')
    return normal(parent.parent.name)+'__'+normal(parent.name)+'__'


def verify(root):
    sys.path.insert(0,str(PROJECT/'catalogue-review'))
    from delete_dropbox import connection
    from rename_from_paths import get_owned_urls
    manifest=json.loads((root/'manifest.json').read_text())
    original_links=json.loads((root/'links-before.json').read_text())['links']
    link_proofs={}
    with connection(PROJECT) as (client,_):
        snapshot=inventory(client,manifest)
        owned=get_owned_urls(ReadAPI(client))
        links={'recorded_utc':now(),'pagination_exhausted':True,'links':[x['record'] for x in owned]}
        ids={r['id'] for r in snapshot['wall']['entries']+snapshot['workshop']['entries']}
        for old in original_links:
            if old['id'] not in ids:continue
            for item in owned:
                current=item['record']
                if current['id']!=old['id']:continue
                same=current['url_sha256']==old['url_sha256']
                if not same:
                    u=urlsplit(item['url'])
                    candidate=urlunsplit((u.scheme,u.netloc,u.path.rsplit('/',1)[0]+'/'+quote(old['name'],safe='-._~'),u.query,u.fragment))
                    if hashlib.sha256(candidate.encode()).hexdigest()!=old['url_sha256']:continue
                    checked=client.sharing_get_shared_link_metadata(url=candidate)
                    if checked.id!=old['id']:continue
                link_proofs[(old['id'],old['url_sha256'])]={'current':current,'original_url_unchanged':same,
                    'original_url_reconstructed_hash_verified':not same,'original_link_resolves_to_same_id':True}
                break
        save(root/'shared-link-survival.json',{'at':now(),'checks':[{'id':key[0],'original_url_sha256':key[1],**value}
             for key,value in link_proofs.items()]},immutable=True)
    save(root/'native-final-independent.json',snapshot,immutable=True)
    save(root/'links-final-independent.json',links,immutable=True)
    original={e['id']:e for name in ['native-before.json','workshop-before.json']
              for e in json.loads((root/name).read_text())['entries']}
    final={e['id']:e for e in snapshot['wall']['entries']+snapshot['workshop']['entries']}
    before_files={i:r for i,r in original.items() if r['kind']=='file'}
    files={i:r for i,r in final.items() if r['kind']=='file'}
    missing=sorted(set(before_files)-set(files));new=sorted(set(files)-set(before_files))
    errors=[];numbered=defaultdict(list);changes=[]
    for fid,row in files.items():
        prefix=expected_prefix(row['path'])
        suffix=PurePosixPath(row['name']).suffix
        match=re.fullmatch(re.escape(prefix)+r'(\d{3,})'+re.escape(suffix),row['name'])
        if not match:errors.append({'id':fid,'check':'filename_pattern','path':row['path']})
        else:numbered[row['parent_id']].append(int(match.group(1)))
        old=before_files.get(fid)
        if old:
            for key in ['id','size','content_hash','client_modified','parent_id','has_explicit_shared_members',
                        'sharing_info_present','read_only','parent_shared_folder_id','file_lock_present']:
                if old.get(key)!=row.get(key):errors.append({'id':fid,'check':'preserved_'+key})
            if suffix!=PurePosixPath(old['name']).suffix:errors.append({'id':fid,'check':'preserved_extension'})
        parent=str(PurePosixPath(row['path']).parent)
        changes.append({**row,'source_path_before':old['path'] if old else '',
                        'source_name_before':old['name'] if old else '',
                        'renamed':bool(old and old['name']!=row['name']),
                        'image_url':'https://www.dropbox.com/preview'+quote(row['path'],safe='/'),
                        'folder_url':'https://www.dropbox.com/home'+quote(parent,safe='/')})
    for fid,seq in numbered.items():
        if sorted(seq)!=list(range(1,len(seq)+1)):errors.append({'id':fid,'check':'contiguous_sequence'})
    for fid,row in original.items():
        if row['kind']!='folder':continue
        after=final.get(fid)
        if not after or any(row.get(k)!=after.get(k) for k in ['name','path','parent_id','sharing_info_present']):
            errors.append({'id':fid,'check':'folder_unchanged'})
    removed_receipts={}
    db=Path.home()/'Library/Application Support/BoldstoneReview/reviews.sqlite3'
    with sqlite3.connect('file:'+str(db)+'?mode=ro',uri=True) as connection:
        for file_id,state,created,result in connection.execute('SELECT file_id,state,created_at,result FROM deletion_jobs'):
            if file_id in missing and state in ('deleted','already_absent'):
                proof=json.loads(result or '{}')
                if proof.get('verified_absent'):
                    removed_receipts[file_id]={'created_at':created,'state':state,'checked_utc':proof.get('checked_utc')}
    for fid in missing:
        if fid not in removed_receipts:errors.append({'id':fid,'check':'external_absence_receipt_missing'})
    preserved_links=0
    for old in original_links:
        if old['id'] not in final:continue
        proof=link_proofs.get((old['id'],old['url_sha256']))
        current=proof['current'] if proof else None
        if current is None:errors.append({'id':old['id'],'check':'original_shared_link_retained','url_sha256':old['url_sha256']})
        else:
            preserved_links+=1
            for key in ['resolved_visibility','effective_audience','link_access_level','expires']:
                if old.get(key)!=current.get(key):errors.append({'id':old['id'],'check':'sharing_'+key})
    summary={'at':now(),'status':'PASS' if not errors else 'FAIL','initial_files':len(before_files),
             'current_files':len(files),'wall_images':sum(x['kind']=='file' for x in snapshot['wall']['entries']),
             'workshop_images':sum(x['kind']=='file' for x in snapshot['workshop']['entries']),
             'renamed_files':sum(r['renamed'] for r in changes),'already_correct_files':sum(not r['renamed'] for r in changes),
             'external_user_deletions':len(missing),'external_deletion_receipts':removed_receipts,'new_files':new,
             'folders_with_images':len(numbered),'all_scoped_folders':sum(r['kind']=='folder' for r in final.values()),
             'preserved_scoped_shared_links':preserved_links,'errors':errors,
             'native_final':str(root/'native-final-independent.json'),'native_final_sha256':sha(root/'native-final-independent.json'),
             'manifest':str(root/'manifest.json'),'manifest_sha256':sha(root/'manifest.json')}
    save(root/'verification.json',summary,immutable=True)
    if errors:
        print(json.dumps(summary,indent=2));raise SystemExit('Full verification needs reconciliation')
    save(root/'current-filename-paths.json',{'at':now(),'namespace_id':'202238505','verification':str(root/'verification.json'),
         'verification_sha256':sha(root/'verification.json'),'files':sorted(changes,key=lambda r:r['path'].casefold()),
         'externally_deleted_ids':missing},immutable=True)
    with (root/'verified-renames.csv').open('x',newline='') as stream:
        fields=['id','source_path_before','path','name','renamed','parent_id','size','content_hash','image_url','folder_url']
        writer=csv.DictWriter(stream,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(sorted(changes,key=lambda r:r['path'].casefold()))
    print(json.dumps({k:v for k,v in summary.items() if k!='external_deletion_receipts'},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True)
    verify(parser.parse_args().root)
