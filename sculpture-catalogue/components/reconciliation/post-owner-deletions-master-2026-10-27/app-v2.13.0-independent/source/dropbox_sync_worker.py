#!/usr/bin/env python3
"""Read-only Dropbox inventory collector, using the existing Keychain grant.

The server launches this with the Dropbox SDK runtime. A complete, paginated
inventory and cursor are committed together; failures leave the prior state.
There are no Dropbox upload, move, share or delete calls in this module.
"""
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import argparse
import copy
import fcntl
import hashlib
import json
import os
import shutil
import sys
import time
import uuid

from media import MediaCache
from fetch_original import OriginalError, check_metadata

IMAGE_EXTENSIONS={'.jpg','.jpeg','.png','.gif','.webp','.bmp','.tif','.tiff','.heic','.heif','.avif'}

def stamp():
    return datetime.now(timezone.utc).isoformat()

def atomic_json(path, value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    temporary=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        with temporary.open('x') as stream:
            os.chmod(temporary,0o600)
            json.dump(value,stream,ensure_ascii=False)
            stream.flush();os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)

def encode_entry(entry):
    from dropbox.files import DeletedMetadata,FolderMetadata
    path=getattr(entry,'path_display',None)
    if not path:
        raise OriginalError('Dropbox returned an entry without its actual path.')
    if isinstance(entry,DeletedMetadata):
        return {'kind':'deleted','path':path}
    result={'id':entry.id,'path':path,'name':entry.name,
            'kind':'folder' if isinstance(entry,FolderMetadata) else 'file'}
    if result['kind']=='file':
        result.update(rev=entry.rev,bytes=entry.size,content_hash=entry.content_hash,
                      modified=entry.server_modified.isoformat(),downloadable=entry.is_downloadable)
    return result

def within(path, root):
    return path.casefold()==root.casefold() or path.casefold().startswith(root.casefold().rstrip('/')+'/')

def apply_entries(records, entries, root):
    """Dropbox deltas are ordered, including old-path deletion then new-path add."""
    for row in entries:
        path=row['path'].rstrip('/')
        if not within(path,root):
            raise OriginalError('Dropbox returned content outside Wall Sculptures.')
        if row['kind']=='deleted':
            for fid in [fid for fid,r in records.items() if within(r['path'],path)]:
                del records[fid]
            continue
        old=records.get(row['id'])
        if old and old['kind']=='folder' and old['path']!=path:
            for child in records.values():
                if child['id']!=old['id'] and within(child['path'],old['path']):
                    child['path']=path+child['path'][len(old['path']):]
        # A different file can replace a path, while reviews still retain its ID.
        for fid in [fid for fid,r in records.items() if fid!=row['id'] and r['path'].casefold()==path.casefold()]:
            del records[fid]
        records[row['id']]={**row,'path':path}

def collect(client, previous, root, root_id, encode=encode_entry):
    cursor=previous.get('cursor')
    records=copy.deepcopy(previous.get('records',{})) if cursor else {}
    reset=False
    try:
        page=client.files_list_folder_continue(cursor) if cursor else client.files_list_folder(
            root_id,recursive=True,include_deleted=False,include_media_info=False,limit=2000)
    except Exception as error:
        if not cursor or not getattr(getattr(error,'error',None),'is_reset',lambda:False)():
            raise
        records={};reset=True
        page=client.files_list_folder(root_id,recursive=True,include_deleted=False,include_media_info=False,limit=2000)
    pages=0;entries=0
    while True:
        rows=[encode(x) for x in page.entries]
        apply_entries(records,rows,root);pages+=1;entries+=len(rows)
        cursor=page.cursor
        if not cursor:
            raise OriginalError('Dropbox did not return a change cursor.')
        if not page.has_more:
            break
        page=client.files_list_folder_continue(cursor)
    records[root_id]={'id':root_id,'kind':'folder','path':root,'name':Path(root).name}
    return records,cursor,{'pages':pages,'entries':entries,'cursor_reset':reset,'has_more':False}

def download_original(client, row, data_root, root_path):
    directory=Path(data_root)/'originals';directory.mkdir(parents=True,exist_ok=True,mode=0o700)
    target=directory/(row['content_hash']+'.image')
    cache=MediaCache(data_root)
    if target.is_file():
        info=cache.inspect(target,hashes=True)
        if info['bytes']==row['bytes'] and info['dropbox_content_hash']==row['content_hash']:
            return {'path':str(target),'representation':'verified Dropbox original',**info}
    temporary=target.with_name(target.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        metadata,response=client.files_download(row['id'])
        with closing(response):
            check_metadata(metadata,row['id'],row['content_hash'],row['bytes'],root_path)
            length=0
            with temporary.open('xb') as output:
                os.chmod(temporary,0o600)
                for chunk in response.iter_content(chunk_size=1024*1024):
                    length+=len(chunk)
                    if length>row['bytes']:
                        raise OriginalError('Downloaded original exceeded its recorded size.')
                    output.write(chunk)
        info=cache.inspect(temporary,hashes=True)
        if info['bytes']!=row['bytes'] or info['dropbox_content_hash']!=row['content_hash']:
            raise OriginalError('The new image failed original-byte verification.')
        temporary.replace(target)
        return {'path':str(target),'representation':'verified Dropbox original',**info}
    finally:
        temporary.unlink(missing_ok=True)

def download_preview(client,row,data_root,root_path):
    from dropbox.files import PathOrLink,ThumbnailSize,ThumbnailMode
    result,response=client.files_get_thumbnail_v2(PathOrLink.path(row['id']),size=ThumbnailSize.w1024h768,
                                                mode=ThumbnailMode.bestfit)
    metadata=result.metadata
    target=Path(data_root)/'dropbox-sync/previews'/(row['content_hash']+'.jpg')
    target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    temporary=target.with_name(target.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        with closing(response):
            check_metadata(metadata,row['id'],row['content_hash'],row['bytes'],root_path)
            with temporary.open('xb') as stream:
                os.chmod(temporary,0o600);length=0
                for chunk in response.iter_content(chunk_size=128*1024):
                    length+=len(chunk)
                    if length>8_000_000:raise OriginalError('Preview exceeds the viewer size limit.')
                    stream.write(chunk)
        temporary.replace(target)
        return {'path':str(target),'representation':'Dropbox thumbnail / original dimensions not verified'}
    finally:
        temporary.unlink(missing_ok=True)

def sync(project,data_root):
    sys.path.insert(0,str(Path(project)/'image-processing'))
    import authorize
    from dropbox import Dropbox
    from dropbox.common import PathRoot
    from dropbox.exceptions import RateLimitError
    directory=Path(data_root)/'dropbox-sync';directory.mkdir(parents=True,exist_ok=True,mode=0o700)
    with (directory/'collector.lock').open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise OriginalError('Another image refresh is running.') from None
        state_path=directory/'inventory.json'
        previous=json.loads(state_path.read_text()) if state_path.exists() else {}
        baseline=json.loads((directory/'baseline.json').read_text())
        try:
            raw=authorize.keychain_backend().get_password(authorize.SERVICE,authorize.CREDENTIAL_ACCOUNT)
            grant=json.loads(raw) if raw else {}
        except Exception:raise OriginalError('The existing Dropbox connection could not be read from Keychain.') from None
        if grant.get('app_key')!=authorize.APP_KEY or not grant.get('refresh_token'):
            raise OriginalError('The existing Dropbox app is not authorized on this Mac.')
        scope={'namespace':authorize.NAMESPACE_ID,'root_id':authorize.ROOT_ID,'root_path':authorize.ROOT_PATH,
               'account_id':grant.get('account_id')}
        if previous and previous.get('scope')!=scope:
            raise OriginalError('The saved image refresh belongs to a different Dropbox source.')
        with Dropbox(app_key=authorize.APP_KEY,oauth2_refresh_token=grant['refresh_token'],timeout=25,
                     max_retries_on_error=0,max_retries_on_rate_limit=0) as client:
            account=client.users_get_current_account()
            rooted=client.with_path_root(PathRoot.namespace_id(authorize.NAMESPACE_ID))
            folder=rooted.files_get_metadata(authorize.ROOT_ID)
            authorize.verify_identity(account,folder,grant.get('account_id'))
            records,cursor,scan=collect(rooted,previous,authorize.ROOT_PATH,authorize.ROOT_ID)
            images={fid:r for fid,r in records.items() if r['kind']=='file' and Path(r['name']).suffix.lower() in IMAGE_EXTENSIONS}
            folders={r['path'].casefold():r['id'] for r in records.values() if r['kind']=='folder'}
            for row in images.values():
                row['folder_id']=folders.get(str(Path(row['path']).parent).casefold(),'')
                if not row['folder_id']:raise OriginalError('Dropbox returned an image without its containing folder.')
            retired={fid:r for fid,r in previous.get('retired',{}).items() if fid not in images}
            retired.update({fid:r for fid,r in previous.get('records',{}).items()
                            if r['kind']=='file' and Path(r['name']).suffix.lower() in IMAGE_EXTENSIONS and fid not in images})
            media={fid:m for fid,m in previous.get('media',{}).items() if fid in images and m.get('content_hash')==images[fid]['content_hash'] and Path(m['path']).is_file()}
            pending=[]
            for fid,r in images.items():
                old=baseline.get(fid)
                changed=old and old.get('hash') and old['hash']!=r['content_hash']
                if fid not in media and (old is None or changed):
                    pending.append(fid)
            failures=[]
            retry={fid:r for fid,r in previous.get('media_retry',{}).items()
                   if fid in images and r.get('content_hash')==images[fid]['content_hash']}
            eligible=[fid for fid in pending if retry.get(fid,{}).get('after',0)<=time.time()]
            for fid in sorted(eligible,key=lambda f:(f in baseline,images[f]['path'].casefold()))[:8]:
                row=images[fid]
                try:
                    if shutil.disk_usage(data_root).free<max(row['bytes'],8_000_000)+500_000_000:
                        raise OriginalError('Image preview cache is waiting for local disk space.')
                    info=download_original(rooted,row,data_root,authorize.ROOT_PATH) if 0<row['bytes']<=25_000_000 and Path(row['name']).suffix.lower() not in {'.heic','.heif','.avif'} else download_preview(rooted,row,data_root,authorize.ROOT_PATH)
                    media[fid]={**info,'content_hash':row['content_hash'],'revision':row['rev']}
                    retry.pop(fid,None)
                except RateLimitError:raise
                except Exception:
                    failures.append(fid);retry[fid]={'content_hash':row['content_hash'],'after':time.time()+300}
        signature=hashlib.sha256(json.dumps({'records':records,'media':media,'retired':retired},sort_keys=True).encode()).hexdigest()
        generation=previous.get('generation',0)+(signature!=previous.get('signature'))
        result={'schema':'boldstone-dropbox-images/v1','scope':scope,'cursor':cursor,'records':records,'media':media,'retired':retired,
                'signature':signature,'generation':generation,'checked_utc':stamp(),'scan':scan,
                'image_count':len(images),'new_image_count':sum(fid not in baseline for fid in images),
                'pending_previews':len(set(pending)-set(media)),'preview_failures':failures,'media_retry':retry,'native_writes':0}
        archive=directory/'generations'/(str(generation)+'-'+signature+'.json')
        if not archive.exists():atomic_json(archive,result)
        result.update(snapshot_path=str(archive),snapshot_sha256=hashlib.sha256(archive.read_bytes()).hexdigest())
        atomic_json(state_path,result)
        return {k:result[k] for k in ['generation','checked_utc','scan','image_count','new_image_count','pending_previews','native_writes']}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--project',required=True,type=Path);parser.add_argument('--data-dir',required=True,type=Path)
    args=parser.parse_args()
    try:print(json.dumps(sync(args.project,args.data_dir)))
    except OriginalError as error:
        print(json.dumps({'error':str(error),'retry_after':60}));return 1
    except Exception as error:
        # Never log SDK/keyring exception text, access tokens, or account responses.
        retry=max(60,int(getattr(error,'backoff',0) or 0))
        print(json.dumps({'error':'Dropbox refresh could not finish. The last complete image inventory is still available.','retry_after':retry}));return 1
    return 0

if __name__=='__main__':raise SystemExit(main())
