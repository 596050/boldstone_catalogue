"""Retained native drafts, isolated from the publishing outbox and intent ledger."""
import fcntl
import re
from pathlib import Path

from common import Hold, atomic_json, digest, read_json, utc
from google_fast import GoogleFastChrome
from upload_bridge import UploadClient
from workflow import Workflow, render


class PreparationOnlyChrome(GoogleFastChrome):
    """A second boundary: the preparation transport refuses submission calls."""
    def call(self, name, request):
        op = request.get('op', '')
        if op.startswith('submit'):
            raise Hold('PREPARATION_ONLY', 'This command cannot submit a post')
        if op == 'click' and any(str(x.get('name','')).strip().lower() in
                                {'post','publish','publish to facebook','publish to instagram','share now'}
                                for x in ([request['locator']] if isinstance(request.get('locator'),dict) else request.get('locator',[]))):
            raise Hold('PREPARATION_ONLY', 'This command cannot click a publication control')
        return super().call(name, request)


def prepare_manifest(settings, store, directory, manifest, tabs, profile=None, post_key=None,
                     chrome_factory=PreparationOnlyChrome, workflow_factory=Workflow):
    """Validate the whole tab plan before filling any composer; never enqueue."""
    directory = Path(directory).resolve()
    jobs = settings.jobs(manifest, require_authorized=False)
    if profile:
        settings.profile(profile)
        jobs = [j for j in jobs if j['payload']['profile_id']==profile]
    if post_key:
        jobs = [j for j in jobs if j['post_key']==post_key]
    if not jobs:
        raise Hold('NO_PREPARATION_TARGETS')
    plan = read_json(Path(tabs))
    if plan.get('schema_version') != 1 or not isinstance(plan.get('bindings'),list) or not plan.get('verification'):
        raise Hold('DRAFT_TAB_PLAN', 'Provide one reserved tab for each profile/post_key plus a verification tab')
    bindings={}
    for row in plan['bindings']:
        key=(row.get('profile_id'),row.get('post_key'))
        if key in bindings:
            raise Hold('DUPLICATE_DRAFT_BINDING')
        bindings[key]=row
    used=set()
    reader=plan['verification']
    reader_tab=(int(reader['window_id']),int(reader['tab_id']))
    previous={j['id']:j for j in store.jobs()}
    for job in jobs:
        if job['id'] in previous:
            raise Hold('EXISTING_DELIVERY', 'This post already has an outbox record; its existing delivery is retained')
        key=(job['payload']['profile_id'],job['post_key'])
        if key not in bindings:
            raise Hold('DRAFT_TAB_MISSING', str(key))
        row=bindings[key]
        tab=(int(row['window_id']),int(row['tab_id']))
        if tab in used or tab==reader_tab:
            raise Hold('DRAFT_TAB_REUSED', 'Each retained draft needs its own reserved tab')
        used.add(tab)
    batch=read_json(Path(manifest))['batch_id']
    slug=re.sub('[^a-zA-Z0-9_-]+','-',str(batch))[:80]
    output=directory/'drafts'/(slug+'-'+digest(str(batch))[:8])
    output.mkdir(parents=True,exist_ok=True,mode=0o700)
    frozen=output/'manifest.json'
    source=read_json(Path(manifest))
    if frozen.exists() and digest(read_json(frozen))!=digest(source):
        raise Hold('DRAFT_MANIFEST_CHANGED','Keep the original manifest or use a new batch ID')
    before=len([e for e in store.ledger if e['kind']=='PUBLISH_INTENT'])
    results=[]
    with (output/'prepare.lock').open('a') as lock:
        try:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            raise Hold('PREPARATION_ALREADY_ACTIVE')
        atomic_json(frozen,source)
        atomic_json(output/'tabs.json',plan)
        for job in jobs:
            name=job['payload']['profile_id'];row=bindings[(name,job['post_key'])]
            state=output/job['id'];chrome=chrome_factory(settings,state)
            result={'id':job['id'],'post_key':job['post_key'],'title':job['payload']['title'],
                    'profile_id':name,'window_id':int(row['window_id']),'tab_id':int(row['tab_id'])}
            try:
                for role,binding in [(name,row),('verification',reader)]:
                    old=chrome.bindings.get(role)
                    if old:
                        if (old['window_id'],old['tab_id'])!=(int(binding['window_id']),int(binding['tab_id'])):
                            raise Hold('DRAFT_BINDING_CHANGED','Inspect the retained draft before replacing its tab')
                    else:
                        chrome.bind(role,binding['window_id'],binding['tab_id'])
                        if role == name and chrome.bindings[role].get('url') not in (None,'about:blank'):
                            context={**settings.profile(name),**job['payload']}
                            clean=chrome.call(role,{'op':'clean_state',**render(job['payload']['workflow_snapshot']['clean_state'],context)})
                            if not clean['clean']:
                                raise Hold('EXISTING_DRAFT_RETAINED','The reserved tab already contains a draft; use an empty tab')
                if any(s.get('method')=='helper' for s in job['payload']['workflow_snapshot'].get('prepare',[])):
                    chrome.upload_client=UploadClient(directory)
                ready=workflow_factory(settings,chrome,state).prepare(job)
                result.update(state='PREPARED_NOT_PUBLISHED',ready=ready)
            except Exception as error:
                result.update(state='HELD',code=error.code if isinstance(error,Hold) else type(error).__name__,detail=str(error))
            finally:
                chrome.close()
            atomic_json(state/'preparation-result.json',result)
            results.append(result)
            atomic_json(output/'preparation-report.json',{'utc':utc(),'mode':'prepare_only','publish_clicks':0,
                        'publish_intents_written':0,'outbox_jobs_added':0,'drafts':results})
    after=len([e for e in store.ledger if e['kind']=='PUBLISH_INTENT'])
    if after!=before:
        raise Hold('PREPARATION_INTENT_INVARIANT','Preparation unexpectedly changed the intent ledger')
    return {'utc':utc(),'mode':'prepare_only','complete':all(r['state']=='PREPARED_NOT_PUBLISHED' for r in results),
            'prepared':sum(r['state']=='PREPARED_NOT_PUBLISHED' for r in results),'held':sum(r['state']=='HELD' for r in results),
            'publish_clicks':0,'publish_intents_written':after-before,'outbox_jobs_added':0,
            'report':str(output/'preparation-report.json'),'drafts':results}
