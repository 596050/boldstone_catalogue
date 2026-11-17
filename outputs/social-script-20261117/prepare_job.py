#!/usr/bin/env python3
"""Run the production preparation checks without writing a publish intent."""
import json
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKSPACE / 'social-publisher'))
from common import Hold, atomic_json, utc
from settings import Settings
from chrome import Chrome
from workflow import Workflow
from journal import Store

directory = WORKSPACE / 'social-publisher/state'
settings = Settings()
chrome = Chrome(settings, directory)
workflow = Workflow(settings, chrome, directory)
job_id = sys.argv[1]
result = {'utc': utc(), 'job_id': job_id, 'publish_actions': 0}
with Store(directory) as store:
    if store.has_intent(job_id):
        raise Hold('INTENT_CANNOT_BE_RESET')
    try:
        ready = workflow.prepare(store.get(job_id))
        store.change(job_id, 'READY')
        result.update(status='READY_NOT_SUBMITTED', ready=ready)
    except Hold as error:
        store.change(job_id, 'BLOCKED', error=error.code + ': ' + str(error))
        result.update(status='HELD', code=error.code, detail=str(error))
    finally:
        workflow.close()
    result['new_publish_intents'] = int(store.has_intent(job_id))
    store.export()
    store.backup()
atomic_json(Path(__file__).parent / (job_id + '-preparation.json'), result)
print(json.dumps(result, indent=2))
