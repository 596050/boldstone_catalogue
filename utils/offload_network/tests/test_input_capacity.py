"""Do not consume attempts when concurrent immutable volume copies cannot fit."""
import json
import sqlite3
from types import SimpleNamespace
from concurrent.futures import ThreadPoolExecutor

import pytest
from offload_service.core import Worker
from research_workflows.input_capacity import Snapshot, observe
from research_workflows.simulation import configuration
from research_workflows.worker import WorkflowWorker

M = 1 << 20


def payload(*refs, work=10, transport='docker-volume'):
    return {'workflow_input_transport':transport,
        'workflow_mounts':[{'object_sha256':r,'target':'inputs/'+str(i)} for i,r in enumerate(refs)],
        'inputs':[], 'template':{'max_input_mb':200,'max_work_mb':work,'cpus':1,'memory_mb':512,'pids':128}}


def test_aliases_cost_one_copy_per_attempt_but_concurrent_attempts_cost_two():
    db=sqlite3.connect(':memory:'); db.execute('CREATE TABLE jobs(payload TEXT,state TEXT)')
    worker=SimpleNamespace(min_free_mb=10,max_store_mb=200,
                           _execution_storage_bytes=Worker._execution_storage_bytes)
    snap=Snapshot({'a':60*M},40*M); job=payload('a','a')
    assert snap.copies(job)==60*M
    assert snap.allows(worker,db,job,100*M)
    db.execute('INSERT INTO jobs VALUES (?,?)',(json.dumps(job),'running'))
    assert not snap.allows(worker,db,job,100*M)
    assert snap.allows(worker,db,job,150*M)
    db.close()


def test_store_cap_can_block_despite_plentiful_host_space():
    db=sqlite3.connect(':memory:'); db.execute('CREATE TABLE jobs(payload TEXT,state TEXT)')
    worker=SimpleNamespace(min_free_mb=0,max_store_mb=100,
                           _execution_storage_bytes=Worker._execution_storage_bytes)
    assert not Snapshot({'a':60*M},31*M).allows(worker,db,payload('a'),1000*M)
    assert Snapshot({'a':60*M},30*M).allows(worker,db,payload('a'),1000*M)
    db.close()


def test_new_or_damaged_declarations_use_approved_bound_and_bind_has_no_copy():
    snap=Snapshot({},0)
    assert snap.copies(payload('new','new'))==200*M
    assert snap.copies(payload('a',transport='bind'))==0


@pytest.mark.parametrize('configured_transport', ['bind','docker-volume'])
def test_claim_waits_without_spending_attempt_then_proceeds_after_capacity_recovery(tmp_path,monkeypatch,configured_transport):
    config=configuration()
    with WorkflowWorker(tmp_path/'worker',[],backend='trusted-local',workflow_config=config,
                        concurrency=2,min_free_mb=0,max_store_mb=100) as worker:
        # No Docker execution is requested in this focused admission regression.
        worker.input_transport=configured_transport
        declared={'a':60*M}
        monkeypatch.setattr('research_workflows.input_capacity.observe',lambda _:Snapshot(declared,40*M))
        for name in ('a','b'):
            with worker.transaction() as db:
                db.execute("INSERT INTO jobs(id,request,state,created,updated,cancel,payload) VALUES (?,?,'queued',0,0,0,?)",
                           (name,'{}',json.dumps(payload('a'))))
        assert worker._claim() is None
        assert [(r['state'],r['attempt']) for r in worker.db.execute('SELECT * FROM jobs')]==[('queued',None),('queued',None)]
        monkeypatch.setattr('research_workflows.input_capacity.observe',lambda _:Snapshot(declared,0))
        with ThreadPoolExecutor(max_workers=2) as pool:
            claims=list(pool.map(lambda _:worker._claim(),range(2)))
        assert sum(c is not None for c in claims)==1
        with worker.transaction() as db:
            db.execute("UPDATE jobs SET state='succeeded' WHERE state='running'")
        assert worker._claim() is not None


def test_size_lookup_and_filesystem_observation_release_database_lock(tmp_path,monkeypatch):
    import threading
    lock=threading.Lock(); db=sqlite3.connect(':memory:')
    db.execute('CREATE TABLE jobs(payload TEXT,state TEXT)')
    db.execute('INSERT INTO jobs VALUES (?,?)',(json.dumps(payload('a','a')),'queued'))
    def outside(value):
        assert lock.acquire(blocking=False)
        lock.release()
        return 10
    monkeypatch.setattr('research_workflows.input_capacity.live_tree_bytes',outside)
    worker=SimpleNamespace(db_lock=lock,db=db,root=tmp_path,
        workflows=SimpleNamespace(objects=SimpleNamespace(declared_size=outside)))
    assert observe(worker)==Snapshot({'a':10},10)
    db.close()
