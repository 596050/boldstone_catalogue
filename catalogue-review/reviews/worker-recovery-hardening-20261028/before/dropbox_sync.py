"""Persistent live image overlay, separate from source catalogue and reviews."""
from collections import defaultdict
from copy import copy,deepcopy
from pathlib import Path
from urllib.parse import quote,unquote,urlsplit
import hashlib
import json
import re
import subprocess
import threading
import time

from dropbox_sync_worker import IMAGE_EXTENSIONS,atomic_json,within
from media import enrich

ROOT_PATH='/BOLDSTONE MASTER/Products/01 Wall Sculptures'
ROOT_ID='id:cnqzTNngPVsAAAAAAArpsA'
NAMESPACE='202238505'

def link(path,kind='home'):
    return 'https://www.dropbox.com/'+kind+quote(path,safe='/')

def folder_path(url):
    path=unquote(urlsplit(url or '').path)
    for prefix in ['/home','/preview']:
        if path.startswith(prefix+ROOT_PATH+'/'):return path[len(prefix):].rstrip('/')
    return ''

def in_situ_folder(path):
    """Use an explicit folder label, including an In Situ ancestor, as a type."""
    folder=Path(path)
    while within(str(folder),ROOT_PATH) and str(folder).casefold()!=ROOT_PATH.casefold():
        match=re.search(r'(?:^|[\s_-])in[\s_-]+situ$',folder.name,re.I)
        if match:
            stem=folder.name[:match.start()].rstrip(' _-')
            return {'path':str(folder),'product_path':str(folder.parent/stem) if stem else str(folder.parent)}
        folder=folder.parent
    return None

def read_inventory(path):
    value=json.loads(Path(path).read_text())
    scope=value.get('scope',{})
    if scope.get('root_id')!=ROOT_ID or scope.get('namespace')!=NAMESPACE or scope.get('root_path')!=ROOT_PATH:
        raise ValueError('Image refresh source does not match Wall Sculptures.')
    signature=hashlib.sha256(json.dumps({k:value[k] for k in ['records','media','retired']},sort_keys=True).encode()).hexdigest()
    if signature!=value['signature'] or value['scan'].get('has_more') is not False:
        raise ValueError('The image refresh inventory is incomplete or damaged.')
    archive=Path(value['snapshot_path']).resolve()
    if not archive.is_relative_to(Path(path).resolve().parent/'generations') or hashlib.sha256(archive.read_bytes()).hexdigest()!=value['snapshot_sha256']:
        raise ValueError('The image refresh snapshot could not be verified.')
    return value

def apply_inventory(base,state,data_root):
    """Build an independent catalogue snapshot; never edit canonical files/reviews."""
    cat=copy(base)
    for name in ['assets','edges','paths','preview_paths','source','products']:
        setattr(cat,name,deepcopy(getattr(base,name)))
    records=state['records'];folders={r['path'].casefold():r['id'] for r in records.values() if r['kind']=='folder'}
    # Stable folder IDs keep the association through same-folder renames.
    anchors=defaultdict(set);path_anchors=defaultdict(set);family_paths=defaultdict(set);source_folders=defaultdict(set)
    for a in base.assets.values():
        path=folder_path(a.get('folder_url'))
        if a['source']=='Dropbox' and path and a.get('folder_id'):
            source_folders[path.casefold()].add(a['folder_id'])
    for pid,p in base.products.items():
        path=folder_path(p.get('folder_url'))
        ids=source_folders.get(path.casefold(),set())
        if len(ids)==1:
            fid=next(iter(ids));current=records.get(fid,{})
            if current.get('kind')=='folder':
                path=current['path'];cat.products[pid]['folder_url']=link(path);anchors[fid].add(pid)
        if path:
            path_anchors[path.casefold()].add(pid)
            # Family aliases must come from a product's own containing folder.
            # A broadly related gallery edge cannot rename another family.
            family_paths[path[len(ROOT_PATH)+1:].split('/')[0].casefold()].add(p['family'])
        for aid,edge in base.edges.get(pid,{}).items():
            a=base.assets[aid]
            if a['source']=='Dropbox' and (aid==p.get('primary_id') or any(u.startswith('selected_') for u in edge.get('uses',[]))):
                if a.get('folder_id'):anchors[a['folder_id']].add(pid)
    for path,pids in path_anchors.items():
        if path in folders:anchors[folders[path]].update(pids)
    # A role-labelled sibling has the same exact product-folder stem. Keep
    # ambiguous/group stems as candidates rather than matching on loose words.
    folder_roles={}
    for path,fid in folders.items():
        context=in_situ_folder(records[fid]['path'])
        if not context:continue
        context['folder_id']=folders[context['path'].casefold()]
        folder_roles[fid]=context
        related=path_anchors.get(context['product_path'].casefold(),set())
        if not related and context['product_path'].casefold() in folders:
            related=anchors.get(folders[context['product_path'].casefold()],set())
        if len(related)==1:anchors[fid].update(related)
    images={fid:r for fid,r in records.items() if r['kind']=='file' and Path(r['name']).suffix.lower() in IMAGE_EXTENSIONS}
    absent_hashes=set();active_hashes={r.get('content_hash') for r in images.values()}
    for fid,row in state.get('retired',{}).items():
        if fid in cat.assets:continue
        parent=str(Path(row['path']).parent)
        cat._asset(fid,row['name'],'Dropbox','',link(row['path'],'preview'),link(parent),row.get('folder_id',''),
                   'uncertain','Not present in the latest Wall Sculptures inventory',[],
                   {'native_file_id':fid,'path':row['path'],'revision':row['rev']})
        cat.assets[fid].update(source_unavailable=True,original={'bytes':row['bytes'],'dropbox_content_hash':row['content_hash']})
    for aid,a in cat.assets.items():
        if a['source']=='Dropbox' and aid not in images and a.get('inventory_status')=='CURRENT_NATIVE_FILE_AND_ACTUAL_PARENT_VERIFIED':
            a['source_unavailable']=True
            a['availability_note']='Not present in the latest complete Wall Sculptures inventory; source history retained.'
            if a.get('original',{}).get('dropbox_content_hash'):absent_hashes.add(a['original']['dropbox_content_hash'])
    for fid,row in images.items():
        parent=str(Path(row['path']).parent)
        folder_id=folders.get(parent.casefold())
        if not folder_id:raise ValueError('An image is missing its verified containing-folder identity.')
        old=base.assets.get(fid)
        family_name=row['path'][len(ROOT_PATH)+1:].split('/')[0]
        destination_families=family_paths.get(family_name.casefold(),set())
        family=next(iter(destination_families)) if len(destination_families)==1 else family_name
        if old:
            a=cat.assets[fid];old_hash=a.get('original',{}).get('dropbox_content_hash')
            # The publisher may have updated the path without its old label.
            # Retain only labels supported by the current folder or its aliases.
            old_family=old.get('family') or ''
            if old_family.casefold() in {family_name.casefold(),*(f.casefold() for f in destination_families)}:
                family=old_family
            if old_hash and old_hash!=row['content_hash']:
                cat.paths.pop(fid,None);cat.preview_paths.pop(fid,None)
                a.pop('cached_file',None);a['local_preview']=False
                a['representation']='Updated Dropbox original; preview pending'
                a['original']={};a['content_changed_since_source']=True
        else:
            cat._asset(fid,row['name'],'Dropbox',family,link(row['path'],'preview'),link(parent),folder_id,
                       'uncertain','CURRENT_NATIVE_FILE_AND_ACTUAL_PARENT_VERIFIED',[],{})
            a=cat.assets[fid];a['newly_discovered']=True
        a.update(name=row['name'],family=family,url=link(row['path'],'preview'),folder_url=link(parent),folder_id=folder_id,
                 folder_label=Path(parent).name,inventory_status='CURRENT_NATIVE_FILE_AND_ACTUAL_PARENT_VERIFIED',live_synced=True)
        context=folder_roles.get(folder_id)
        a['folder_types']=['in_situ'] if context else []
        a['folder_type_evidence']=[{'type':'in_situ','folder_id':context['folder_id'],
                                   'folder_url':link(context['path']),'basis':'Current Dropbox folder is labelled In Situ'}] if context else []
        a.pop('source_unavailable',None)
        a['provenance']={**a.get('provenance',{}),'native_file_id':fid,'native_folder_id':folder_id,
                         'path':row['path'],'revision':row['rev'],'server_modified':row['modified'],
                         'live_inventory_generation':state['generation']}
        a['original']={**a.get('original',{}),'bytes':row['bytes'],'dropbox_content_hash':row['content_hash'],
                       'size_basis':'Dropbox metadata from the automatic image refresh'}
        m=state.get('media',{}).get(fid)
        cached=Path(data_root)/'originals'/(row['content_hash']+'.image')
        if cached.is_file():m={'path':str(cached),'representation':'verified Dropbox original'}
        if m and Path(m['path']).is_file():
            local=Path(m['path']).resolve()
            if not local.is_relative_to(Path(data_root).resolve()):raise ValueError('Image cache path is outside the app data directory.')
            cat.paths[fid]=(local,m['representation']);a.update(local_preview=True,representation=m['representation'])
            if 'thumbnail' in m['representation']:cat.preview_paths[fid]=local
        exact=anchors.get(folder_id,set())
        candidates=exact or {pid for pid,p in cat.products.items() if p['family']==family}
        for pid in candidates:
            if fid in cat.edges[pid]:
                if pid in exact and cat.edges[pid][fid].get('tier')=='related':
                    cat.edges[pid][fid]['tier']='folder'
                    cat.edges[pid][fid]['uses'].append('live_folder_candidate')
                continue
            cat.edges[pid][fid]={'asset_id':fid,'uses':['live_folder_candidate' if pid in exact else 'live_family_candidate'],
                               'qualifications':['Current containing-folder association; image identity, finish and use remain unreviewed.'],
                               'association_ids':[],'tier':'folder' if pid in exact else 'related'}
    # A platform copy cannot resurrect a missing Dropbox original. A new native
    # upload with the same bytes is live in its own right and can be reviewed.
    for a in cat.assets.values():
        h=a.get('original',{}).get('dropbox_content_hash')
        if a['source']!='Dropbox' and h in absent_hashes-active_hashes:a['source_unavailable']=True
    # Imported files removed after the preceding refresh remain in the local
    # state history; source-bound reviews are retained even when not displayed.
    cat.asset_products=defaultdict(list)
    for pid,edges in cat.edges.items():
        for aid in edges:cat.asset_products[aid].append(pid)
    for aid,a in cat.assets.items():a['product_ids']=cat.asset_products[aid]
    for p in cat.products.values():
        if p.get('primary_id') in images:p['image_url']=cat.assets[p['primary_id']]['url']
    enrich(cat,data_root)
    cat.source.update(asset_count=len(cat.assets),local_preview_count=len(cat.paths),association_count=sum(len(x) for x in cat.edges.values()))
    cat.source['live_dropbox']={'path':state['snapshot_path'],'sha256':state['snapshot_sha256'],'signature':state['signature'],
                              'generation':state['generation'],'checked_utc':state['checked_utc'],
                              'images':state['image_count'],'new_images':state['new_image_count'],
                              'folder_type_policy':'In Situ folder labels supply default types; explicit app types override them. Exact unambiguous product-folder stems supply folder associations.',
                              'scope':'Read-only Wall Sculptures image inventory; canonical catalogue and saved reviews remain separate.'}
    cat.native_root_folders = [{'id': r['id'], 'name': r['name'], 'path': r['path']}
                               for r in records.values() if r['kind'] == 'folder'
                               and str(Path(r['path']).parent).casefold() == ROOT_PATH.casefold()]
    return cat

class DropboxSync:
    def __init__(self,app,enabled=True,interval=60):
        self.app=app;self.base=app.catalogue;self.interval=interval
        self.root=app.store.root/'dropbox-sync';self.root.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.lock=threading.Lock();self.wake=threading.Event();self.stop_event=threading.Event()
        self.process=None;self.thread=None;self.retry_at=0;self.inventory_state=None
        self.status={'enabled':enabled,'state':'starting' if enabled else 'disabled','generation':0,
                     'interval_seconds':interval,'last_checked':None,'error':'','new_images':0,'pending_previews':0}
        atomic_json(self.root/'baseline.json',{aid:{'hash':a.get('original',{}).get('dropbox_content_hash'),'preview':bool(a.get('local_preview'))}
                                             for aid,a in self.base.assets.items() if a['source']=='Dropbox'})
        if enabled and (self.root/'inventory.json').exists():
            try:self.install(read_inventory(self.root/'inventory.json'))
            except Exception:self.status.update(state='error',error='The saved image refresh could not be loaded. Retrying Dropbox.')

    def install(self,state):
        with self.app.catalogue_lock:
            if state['generation'] < self.status['generation']:
                return
            if state['generation']!=self.status['generation']:
                # Source refresh and inventory installation share this lock:
                # an in-flight scan cannot reinstall an older publisher base.
                cat=apply_inventory(self.base,state,self.app.store.root)
                # Import lazily to keep the native worker independent of the UI.
                from filename_overlay import apply_filename_overlay
                apply_filename_overlay(cat, self.app.store.root, state['checked_utc'])
                if getattr(self.app, 'jobs', None):
                    self.app.jobs.overlay_locations(cat, state['checked_utc'])
                self.app.catalogue=cat;self.app.deletions.cat=cat
            self.inventory_state=state
            self.status.update(state='ready',generation=state['generation'],last_checked=state['checked_utc'],error='',
                           new_images=state['new_image_count'],pending_previews=state['pending_previews'],images=state['image_count'])

    def snapshot(self):
        with self.lock:return {**self.status, 'catalogue_source': {
            k: self.app.catalogue.source.get(k) for k in ('register', 'register_sha256', 'gallery_database', 'gallery_sha256')}}

    def start(self):
        if not self.status['enabled'] or self.thread:return
        self.thread=threading.Thread(target=self.loop,name='dropbox-image-refresh',daemon=True);self.thread.start()

    def request(self):
        if self.status['enabled'] and self.status['state']!='checking':self.wake.set()
        return self.snapshot()

    def loop(self):
        while not self.stop_event.is_set():
            if time.time()<self.retry_at:
                self.stop_event.wait(min(self.retry_at-time.time(),60));continue
            with self.lock:self.status.update(state='checking')
            try:
                python=self.base.project/'application/.venv/bin/python'
                if not python.is_file():raise ValueError('Dropbox runtime is unavailable on this Mac.')
                self.process=subprocess.Popen([str(python),str(Path(__file__).with_name('dropbox_sync_worker.py')),
                    '--project',str(self.base.project),'--data-dir',str(self.app.store.root)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
                stdout,_=self.process.communicate(timeout=300)
                result=json.loads(stdout)
                if self.process.returncode or result.get('error'):
                    self.retry_at=time.time()+max(60,result.get('retry_after',60))
                    raise ValueError(result.get('error','Image refresh failed.'))
                state=read_inventory(self.root/'inventory.json')
                self.install(state)
            except Exception as error:
                if self.process and self.process.poll() is None:self.process.kill();self.process.communicate()
                self.retry_at=max(self.retry_at,time.time()+60)
                with self.lock:self.status.update(state='error',error=str(error) if isinstance(error,ValueError) else 'Image refresh is temporarily unavailable; your saved work is intact.')
            finally:self.process=None
            self.wake.wait(self.interval);self.wake.clear()

    def stop(self):
        self.stop_event.set();self.wake.set()
        if self.process and self.process.poll() is None:self.process.terminate()
