"""Read-only classification and lossless compression measurement of old records."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import collections
import csv
import hashlib
import html
import json
import os
import stat
import zlib
import zipfile
import cache_cleanup as c

ROOT, HERE = c.ROOT, c.HERE


def main():
    inventory = c.read(HERE/'snapshot-inventory.json')
    current = c.read(HERE/'protected-before.json')
    pointer = c.read(ROOT/'sculpture-catalogue/current-master.json')
    source = current['source']
    protected = {r['path'] for r in current['protected_files']}
    protected.update(current['protected_paths'])
    protected.add(str(ROOT/'sculpture-catalogue/current-master.json'))
    # Retain the whole current publication and upload folders, including their provenance inputs.
    current_dirs = {Path(source['register']).parent}
    for section in ('current_app_review_workbook','current_upload_preparation'):
        p=pointer.get(section,{}).get('path')
        if p:current_dirs.add(Path(p).parent)
    opened = c.open_paths()
    rows=[]
    for r in inventory:
        row=dict(r);p=ROOT/r['path'];parts=p.relative_to(ROOT).parts
        if str(p) in protected or any(p.is_relative_to(d) for d in current_dirs):
            category='Keep current publication and upload data'
        elif str(p) in opened:
            category='Keep open file'
        elif not p.is_file() or p.is_symlink() or (p.stat().st_size,p.stat().st_mtime_ns)!=(r['bytes'],r['mtime_ns']):
            category='Keep changed or unavailable file'
        elif r['path'].startswith(('outputs/storage-cleanup-20261030/','outputs/historical-image-archive-20261030/',
                                   'outputs/cache-clear-and-snapshot-audit-20261030/','outputs/local-image-storage-audit-20261030/')):
            category='Keep archive manifests and restoration evidence'
        elif p.name.endswith('.xlsx.inspect.ndjson') and p.with_name(p.name.removesuffix('.inspect.ndjson')).is_file():
            category='Workbook inspection dumps with retained XLSX'
            row['retained_workbook']=str(p.with_name(p.name.removesuffix('.inspect.ndjson')).relative_to(ROOT))
        elif p.suffix=='.before' and r['path'].startswith(('sculpture-catalogue/components/','catalogue-review/reviews/')):
            category='Historical before snapshots - archive before removal'
        elif p.suffix in ('.sqlite','.sqlite3','.db') and r['path'].startswith(('sculpture-catalogue/components/','sculpture-catalogue/outputs/','catalogue-review/reviews/','outputs/01a13fe6-495b-7253-b923-31823b4cbca8/')):
            category='Historical database snapshots - archive before removal'
        elif p.suffix=='.json' and r['path'].startswith(('sculpture-catalogue/components/reconciliation/',
                                                      'sculpture-catalogue/components/parallel-reviews/',
                                                      'sculpture-catalogue/components/reviews/',
                                                      'catalogue-review/reviews/')):
            category='Historical JSON review snapshots - archive before removal'
        else:
            category='Keep source exports, configuration or further dependency review'
        row['category']=category
        row['candidate']=category in ('Workbook inspection dumps with retained XLSX',
            'Historical before snapshots - archive before removal',
            'Historical database snapshots - archive before removal',
            'Historical JSON review snapshots - archive before removal')
        rows.append(row)
    # Check compressed bytes by streaming each output straight back through a decompressor.
    # No archive is retained and no input is modified or removed.
    def measure(row):
        p=ROOT/row['path'];before=p.lstat()
        if not stat.S_ISREG(before.st_mode):raise ValueError('Not regular')
        compressor=zlib.compressobj(6,zlib.DEFLATED,31);decoder=zlib.decompressobj(31)
        original=hashlib.sha256();restored=hashlib.sha256();packed=0;restored_bytes=0
        def consume(data):
            nonlocal packed,restored_bytes
            packed+=len(data)
            plain=decoder.decompress(data)
            restored.update(plain);restored_bytes+=len(plain)
        with p.open('rb') as f:
            for chunk in iter(lambda:f.read(1024*1024),b''):
                original.update(chunk);consume(compressor.compress(chunk))
        consume(compressor.flush())
        tail=decoder.flush();restored.update(tail);restored_bytes+=len(tail)
        after=p.lstat()
        if c.native.identity(before)!=c.native.identity(after) or not decoder.eof:
            raise ValueError('Changed while measuring')
        if restored_bytes!=before.st_size or original.digest()!=restored.digest():raise ValueError('Compression round trip failed')
        return {**row,'sha256':original.hexdigest(),'gzip_bytes':packed,
                'measured_logical_reduction_bytes':before.st_size-packed,'gzip_roundtrip':'PASS'}
    candidates=[r for r in rows if r['candidate']]
    measured={}
    with ThreadPoolExecutor(max_workers=3) as pool:
        for index,row in enumerate(pool.map(measure,candidates),1):
            measured[row['path']]=row
            if index%1500==0:c.emit(phase='Snapshot compression round trips verified',files=index,total=len(candidates))
    rows=[measured.get(r['path'],r) for r in rows]
    workbooks=sorted({r['retained_workbook'] for r in rows if r.get('retained_workbook')})
    workbook_checks=[]
    for name in workbooks:
        p=ROOT/name
        try:
            with zipfile.ZipFile(p) as z:
                bad=z.testzip()
                ok=bad is None and 'xl/workbook.xml' in z.namelist()
            workbook_checks.append({'path':name,'status':'PASS' if ok else 'FAIL','sha256':c.native.digest(p)})
        except Exception as error:workbook_checks.append({'path':name,'status':'FAIL','reason':type(error).__name__})
    failed={x['path'] for x in workbook_checks if x['status']!='PASS'}
    for r in rows:
        if r.get('retained_workbook') in failed:
            r.update(candidate=False,category='Keep inspection dump - workbook verification failed')
    groups=collections.defaultdict(list)
    for r in rows:
        if r['candidate']:groups[r['sha256']].append(r)
    duplicate_groups=[{'sha256':sha,'bytes_each':rs[0]['bytes'],'paths':[r['path'] for r in rs],
                       'repeated_logical_bytes':sum(r['bytes'] for r in rs[1:])}
                      for sha,rs in groups.items() if len(rs)>1]
    categories={}
    for r in rows:
        g=categories.setdefault(r['category'],{'files':0,'bytes':0,'candidate':r['candidate'],'measured_gzip_bytes':0})
        g['files']+=1;g['bytes']+=r['bytes'];g['measured_gzip_bytes']+=r.get('gzip_bytes',0)
    summary={'utc':c.now(),'mode':'Read-only assessment; no snapshot removed or compressed in place',
             'all_files':len(rows),'all_bytes':sum(r['bytes'] for r in rows),'categories':categories,
             'candidate_files':sum(r['candidate'] for r in rows),
             'candidate_bytes':sum(r['bytes'] for r in rows if r['candidate']),
             'candidate_gzip_bytes':sum(r.get('gzip_bytes',0) for r in rows if r['candidate']),
             'deduplicated_archive_gzip_bytes':sum(rs[0]['gzip_bytes'] for rs in groups.values()),
             'duplicate_groups':len(duplicate_groups),'repeated_logical_bytes':sum(r['repeated_logical_bytes'] for r in duplicate_groups),
             'verified_workbooks':len(workbooks)-len(failed),'failed_workbooks':len(failed),
             'current_directories_retained':[str(p) for p in sorted(current_dirs)],
             'caveat':'Logical sizes and compression measurements are not promised free-space gains. APFS clones share extents. Historical consumers require an archive resolver or restoration before original paths can be retired.'}
    c.write(HERE/'snapshot-assessment.json',summary)
    c.write(HERE/'snapshot-file-assessment.json',rows)
    c.write(HERE/'snapshot-exact-duplicates.json',duplicate_groups)
    c.write(HERE/'snapshot-workbook-checks.json',workbook_checks)
    with (HERE/'snapshot-candidates.csv').open('x',newline='') as out:
        fields=['path','category','bytes','gzip_bytes','sha256','retained_workbook']
        w=csv.DictWriter(out,fieldnames=fields,extrasaction='ignore');w.writeheader()
        w.writerows(r for r in rows if r['candidate'])
    head='<!doctype html><meta charset="utf-8"><title>Boldstone snapshot audit</title><style>body{font:16px/1.5 system-ui;max-width:1100px;margin:40px auto;padding:0 20px}td,th{text-align:left;padding:10px;border-bottom:1px solid #ddd}table{border-collapse:collapse;width:100%}code{overflow-wrap:anywhere}a{color:#45663e}</style>'
    page=head+'<h1>Remaining data snapshots</h1><p>Read-only assessment. No data snapshot has been deleted. Current publication, source records and archive manifests remain protected.</p><table><tr><th>Classification</th><th>Files</th><th>GiB</th><th>Measured gzip GiB</th></tr>'
    for k,v in categories.items():page+=f'<tr><td>{html.escape(k)}</td><td>{v["files"]:,}</td><td>{v["bytes"]/2**30:.3f}</td><td>{v["measured_gzip_bytes"]/2**30:.3f}</td></tr>'
    page+='</table><p>Every proposed compression was streamed back through decompression and matched by SHA-256. This measures a possible archive; it has not created a retained archive or authorised deleting unique records. Existing report and pipeline path references need a restoration or archive-access mechanism first.</p>'
    page+='<p>'+html.escape(summary['caveat'])+'</p><p><a href="snapshot-candidates.csv">Exact candidate file list</a> · <a href="snapshot-assessment.json">Summary receipt</a> · <a href="snapshot-exact-duplicates.json">Exact duplicate groups</a> · <a href="snapshot-workbook-checks.json">Workbook verification</a></p>'
    (HERE/'snapshot-assessment.html').write_text(page)
    c.emit(phase='Snapshot assessment finished',**summary)


if __name__=='__main__':main()
