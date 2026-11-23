"""Use two clean owned tabs while preserving the uncertain Moon composer intact."""
from pathlib import Path
import json, sys
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1]
sys.path.insert(0,str(ROOT/'social-publisher'))
from common import atomic_json,digest,utc
from settings import Settings
from google_fast import GoogleFastChrome
from workflow import Workflow
from engine import Engine
from journal import Store

settings=Settings();state=ROOT/'social-publisher/state';temporary=OUT/'remaining-linkedin-state'
jid='5a53f95ee57851114ddf052f74e016a0'
with Store(state) as store:
    job=store.get(jid)
    assert job['payload']['batch_id']=='component-sculptures-linkedin-google-20261123'
    assert not store.has_intent(jid) and job['state']=='BLOCKED'
    requested=settings.jobs(OUT/'manifest.json')
    assert all(store.get(j['id'])['state']=='PUBLISHED' for j in requested if j['payload']['platform']=='google_business_profile')
    main=GoogleFastChrome(settings,state)
    original=json.loads(json.dumps(main.bindings))
    proof={'utc':utc(),'bindings_before':original,'retained_uncertain_composer':original['sally_linkedin'],'clean_tabs':{}}
    for name in ['verification','boldstone_google_business_profile']:
        b=main.bindings[name]
        assert not b.get('dirty')
        snap=main.call(name,{'op':'snapshot','fullDocument':True})
        assert not snap.get('editors')
        proof['clean_tabs'][name]=snap
    path=OUT/'remaining-linkedin-tab-allocation.json';atomic_json(path,proof)
    temporary.mkdir(exist_ok=True)
    atomic_json(temporary/'bindings.json',{'verification':original['verification']})
    chrome=GoogleFastChrome(settings,temporary)
    chrome.navigate('verification',settings.profile('sally_linkedin')['compose_url'],jid)
    writer={**chrome.bindings['verification'],'profile_hash':settings.fingerprint('sally_linkedin')}
    reader={**original['boldstone_google_business_profile'],'profile_hash':chrome.profile_hash('verification')}
    chrome.bindings={'sally_linkedin':writer,'verification':reader};chrome.save_bindings()
    store.event('CLEAN_OWNED_TABS_ALLOCATED_FOR_AUTHORIZED_DELIVERY',job_id=jid,evidence_path=str(path),evidence_sha256=digest(path.read_bytes()),uncertain_composer_preserved=True)
    try:
        store.change(jid,'QUEUED')
        Engine(store,Workflow(settings,chrome,state),settings.policy).run(job_id=jid)
        job=store.get(jid)
        atomic_json(OUT/'remaining-linkedin-result.json',{'utc':utc(),'job_id':jid,'state':job['state'],'receipt':job['receipt'],'last_error':job['last_error'],'uncertain_moon_composer_preserved':True})
        print(json.dumps({'job_id':jid,'state':job['state'],'last_error':job['last_error']}),flush=True)
    finally:
        # Restore the two original tab roles only when the new composer is clean.
        # A failure retains both its draft and its isolated bindings for inspection.
        if not chrome.bindings['sally_linkedin'].get('dirty'):
            inventory=settings.profile('boldstone_google_business_profile')['inventory_url']
            if chrome.bindings['verification']['url']!=inventory:
                chrome.navigate('verification',inventory,recovery=True)
            former_writer=chrome.bindings['sally_linkedin']
            chrome.bindings={'verification':{**former_writer,'profile_hash':chrome.profile_hash('verification')}}
            chrome.save_bindings()
            chrome.navigate('verification',inventory,recovery=True)
            latest=json.loads((state/'bindings.json').read_text())
            assert latest['sally_linkedin']==original['sally_linkedin']
            latest['verification']={**original['verification'],'url':inventory,'dirty':False,'step':0}
            latest['boldstone_google_business_profile']={**original['boldstone_google_business_profile'],'url':inventory,'dirty':False,'step':0}
            atomic_json(state/'bindings.json',latest)
        chrome.close();store.export();store.backup()
