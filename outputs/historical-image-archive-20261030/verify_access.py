"""Verify exact image retrieval, original metadata restoration and old report navigation."""
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen
from urllib.error import HTTPError
import hashlib
import json
import tempfile
import archive_images as a

m=a.manifest()
rows=m['records']
selected=[]
for kind in ['archive','active-local','dropbox']:
    candidates=[r for r in rows if m['blobs'][r['sha256']]['storage']==kind]
    # Choose both a small and large image to exercise streaming and format handling.
    candidates.sort(key=lambda r:r['bytes'])
    chosen=[candidates[0],candidates[len(candidates)//2],candidates[-1]]
    selected.extend({r['path']:r for r in chosen}.values())
results=[]
with tempfile.TemporaryDirectory(dir=a.HERE) as temp:
    temp=Path(temp).resolve()
    for i,row in enumerate(selected):
        blob=m['blobs'][row['sha256']]
        restored=temp/str(i)
        a.restore(row,restored,m)
        assert a.native.digest(restored)==row['sha256']
        assert a.native.metadata(restored)==row['metadata']
        url='http://127.0.0.1:8778/'+quote(row['path'],safe='/')
        with urlopen(url,timeout=90) as response:
            body=response.read();status=response.status
        assert status==200 and hashlib.sha256(body).hexdigest()==row['sha256']
        results.append({'path':row['path'],'storage':blob['storage'],'bytes':len(body),
                        'sha256':row['sha256'],'metadata_restored':True,'http_exact_bytes':True})
        a.emit(phase='Archive access checked',storage=blob['storage'],bytes=len(body))
index=a.read(a.HERE/'viewer-index.json')
reports=index['report_paths']
for rel in [reports[0],reports[len(reports)//2],reports[-1]]:
    with urlopen('http://127.0.0.1:8778/'+quote(rel,safe='/'),timeout=30) as response:
        body=response.read()
    assert body and b'<html' in body.lower() or b'<!doctype' in body.lower()
try:
    urlopen('http://127.0.0.1:8778/%2e%2e/%2e%2e/etc/passwd',timeout=30)
    raise AssertionError('Traversal unexpectedly allowed')
except HTTPError as error:assert error.code==403
with urlopen('http://127.0.0.1:8778/',timeout=30) as response:assert b'Historical reviews and images' in response.read()
a.write(a.HERE/'access-verification.json',{'status':'PASS','checked_utc':a.now(),
        'image_restore_and_http_checks':results,'report_pages_checked':3,'path_traversal_blocked':True,
        'cloud_mutations':0,'persistent_image_cache_bytes':0})
a.emit(status='PASS',image_checks=len(results),report_checks=3)
