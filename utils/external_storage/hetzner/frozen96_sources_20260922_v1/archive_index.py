"""Retain the source index and copy/readback receipts beside the remote data."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tarfile
from types import SimpleNamespace

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
sys.path.insert(0,str(ROOT))
from utils.external_storage.hetzner import storage_box as sb


def main():
    historical=json.loads((HERE/'ARCHIVE.json').read_text())
    updated=json.loads((HERE/'UPDATED_ARCHIVE.json').read_text())
    assert historical['status']==updated['status']=='VERIFIED'
    delivery=json.loads((HERE/'DELIVERY.json').read_text())
    names=['SOURCE_BINDING.json','SOURCE_MANIFEST.json','REFRESH.json','REFRESH_PLAN.json','VIX_RECEIPT.json',
           'MINUTE_REFRESH_COVERAGE.json','REMOTE_READBACK.json','UPDATED_REMOTE_READBACK.json','POST_COPY_SOURCE_IDENTITY.json']
    expected={str(HERE/name):dict(sha256=hashlib.sha256((HERE/name).read_bytes()).hexdigest(),bytes=(HERE/name).stat().st_size) for name in names}
    sb.write_json(HERE/'DATA_ARCHIVE_INDEX.json',dict(schema=1,created_at=sb.now(),
        repository_id=historical['repository_id'],historical_snapshot_id=historical['snapshot_id'],
        updated_snapshot_id=updated['snapshot_id'],cutoff=delivery['cutoff'],symbols=96,
        historical_source_files=delivery['copied_original_source_files'],files=expected,
        purpose='Discover and restore the verified original source files and updated IQFeed source version',
        post_copy_identity_status=json.loads((HERE/'POST_COPY_SOURCE_IDENTITY.json').read_text())['status']))
    p=HERE/'DATA_ARCHIVE_INDEX.json';expected[str(p)]=dict(sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size)
    profile=sb.Profile(sb.DEFAULT_ROOT/'market-data')
    with sb.locked(profile.directory):
        r=sb.Repository(profile);r.bind()
        group='frozen96-source-index-20260922'
        sb.upload(r,SimpleNamespace(paths=list(expected),group=group,require_mount=None,dry_run=False))
        snapshot=r.resolve('latest',group)
        seen=set();total=0
        with (HERE/'index_readback.stderr.log').open('a') as errors:
            with subprocess.Popen(r.base+['dump',snapshot,'/'],env=r.env,stdout=subprocess.PIPE,stderr=errors) as proc:
                with tarfile.open(fileobj=proc.stdout,mode='r|') as tar:
                    for member in tar:
                        if member.isdir():continue
                        name='/'+member.name.lstrip('/')
                        assert member.isfile() and name in expected and name not in seen
                        h=hashlib.sha256();n=0
                        with tar.extractfile(member) as stream:
                            for b in iter(lambda:stream.read(1024**2),b''):h.update(b);n+=len(b)
                        assert dict(sha256=h.hexdigest(),bytes=n)==expected[name]
                        seen.add(name);total+=n
                while proc.stdout.read(1024**2):pass
                code=proc.wait()
        assert code==0 and seen==set(expected)
        result=dict(status='VERIFIED',snapshot_id=snapshot,repository_id=profile.data['repository_id'],group=group,
                    files=len(seen),bytes=total,verified_at=sb.now(),method='Full remote decrypted SHA256 readback')
        sb.write_json(HERE/'DATA_INDEX_ARCHIVE.json',result)
        print(json.dumps(result,indent=2))


if __name__=='__main__':main()
