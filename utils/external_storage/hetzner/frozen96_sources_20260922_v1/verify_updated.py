"""Publish and fully read back the already-uploaded IQFeed refresh snapshot."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tarfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
sys.path.insert(0,str(ROOT))
from utils.external_storage.hetzner import storage_box as sb

STAGING=ROOT/'utils/offload_network/.source-state/frozen96_iqfeed_refresh_20260922_v1'
GROUP='frozen96-iqfeed-update-20260922'


def main():
    profile=sb.Profile(sb.DEFAULT_ROOT/'market-data')
    r=sb.Repository(profile);r.bind()
    rows=r.snapshots('group:'+GROUP)
    if len(rows)!=1:
        raise RuntimeError('Expected exactly one scoped refresh snapshot')
    row=rows[0]
    if sb.COMPLETE not in row.get('tags',[]):
        # The transfer's completion tag can have waited behind another shared
        # backup lock. Finish that same snapshot, without uploading again.
        r.successful(['tag','--retry-lock','5m','--add',sb.COMPLETE,'--remove',sb.PENDING,row['id']])
        rows=r.snapshots('group:'+GROUP+','+sb.COMPLETE)
        assert len(rows)==1
        row=rows[0]
    snapshot=r.resolve(row['id'])
    expected={}
    for p in sorted(STAGING.rglob('*')):
        if p.is_symlink():raise RuntimeError('Unexpected staging symlink')
        if p.is_file():
            expected[str(p)]=dict(path=str(p),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
    assert len(expected)==388
    refresh=json.loads((HERE/'REFRESH.json').read_text())
    assert refresh['status']=='COMPLETE'
    for v in refresh['entries']:
        assert expected[v['path']]['sha256']==v['sha256']
    sb.write_json(HERE/'UPDATED_MANIFEST.json',dict(snapshot_id=snapshot,files=list(expected.values())))
    state=dict(status='READBACK_RUNNING',snapshot_id=snapshot,repository_id=profile.data['repository_id'],
               group=GROUP,started_at=sb.now(),source_deletions=0,expected_files=len(expected))
    sb.write_json(HERE/'UPDATED_ARCHIVE.json',state)
    seen=set();total=0;verified=[]
    try:
        with (HERE/'updated_readback.stderr.log').open('a') as errors:
            with subprocess.Popen(r.base+['dump',snapshot,'/'],env=r.env,stdout=subprocess.PIPE,stderr=errors) as proc:
                with tarfile.open(fileobj=proc.stdout,mode='r|') as tar:
                    for member in tar:
                        if member.isdir():continue
                        name='/'+member.name.lstrip('/')
                        if not member.isfile() or name not in expected or name in seen:
                            raise RuntimeError('Unexpected remote member: '+name)
                        h=hashlib.sha256();n=0
                        with tar.extractfile(member) as f:
                            for b in iter(lambda:f.read(4*1024**2),b''):
                                h.update(b);n+=len(b)
                        e=expected[name]
                        if n!=e['bytes'] or h.hexdigest()!=e['sha256']:
                            raise RuntimeError('Remote content mismatch: '+name)
                        seen.add(name);total+=n;verified.append(dict(**e,status='PASS'))
                        state.update(readback_files=len(seen),readback_bytes=total,updated_at=sb.now())
                        sb.write_json(HERE/'UPDATED_ARCHIVE.json',state)
                while proc.stdout.read(1024**2):pass
                code=proc.wait()
        if code or seen!=set(expected):raise RuntimeError('Incomplete remote readback')
        sb.write_json(HERE/'UPDATED_REMOTE_READBACK.json',dict(status='PASS',snapshot_id=snapshot,
                      method='Authenticated Restic decrypt and full streamed SHA256 of every uploaded file',
                      files=verified,file_count=len(verified),bytes=total,completed_at=sb.now()))
        state.update(status='VERIFIED',verified_at=sb.now())
        profile.receipt('frozen96-update-verified-20260922',state)
    except BaseException as exc:
        state.update(status='READBACK_FAILED',error=repr(exc));raise
    finally:sb.write_json(HERE/'UPDATED_ARCHIVE.json',state)
    print(json.dumps(state,indent=2))


if __name__=='__main__':main()
