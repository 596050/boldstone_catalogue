import collections, datetime, hashlib, json, posixpath, re, zipfile
import xml.etree.ElementTree as E
from pathlib import Path
from urllib.parse import unquote, urlsplit, parse_qs, quote

HERE=Path(__file__).resolve().parent
CAT=HERE.parents[2]
def load(p): return json.loads(p.read_text())
pointer=load(CAT/'current-master.json')
book=CAT/pointer['workbook']
book_sha=hashlib.sha256(book.read_bytes()).hexdigest()
assert book_sha==pointer['workbook_sha256']
families=load(HERE/'family-listings.json')
known={}
for page in families['pages']:
    f=page['folder'];known[f['path_display'].lower()]={'file_id':f['file_id'],'object_type':'folder','display_path':f['path_display']}
    for r in page['listing']['entries']:
        known[r['path_display'].lower()]={'file_id':r['file_id'],'object_type':r['object_type'],'display_path':r['path_display']}
old='/BOLDSTONE MASTER/Products/01 Wall Sculptures/Acanthus Two Leaves Pewter/'
new='/BOLDSTONE MASTER/Products/01 Wall Sculptures/Acanthus/'
ns={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
rn='{http://schemas.openxmlformats.org/package/2006/relationships}'
hits=[]; unsupported=[]; backup=[]
with zipfile.ZipFile(book) as z:
    wb=E.fromstring(z.read('xl/workbook.xml'))
    rels={r.attrib['Id']:r.attrib['Target'] for r in E.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
    for sh in wb.find('m:sheets',ns):
        target=rels[sh.attrib['{'+ns['r']+'}id']]
        sp=target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/'+target)
        rp=posixpath.dirname(sp)+'/_rels/'+posixpath.basename(sp)+'.rels'
        if rp not in z.namelist():continue
        sr={r.attrib['Id']:r.attrib.get('Target','') for r in E.fromstring(z.read(rp))}
        sx=E.fromstring(z.read(sp))
        for h in sx.findall('m:hyperlinks/m:hyperlink',ns):
            rid=h.attrib.get('{'+ns['r']+'}id');url=sr.get(rid,'')
            if not url:continue
            if re.search(r'BOLDSTONE[_ ]BACKUP',unquote(url),re.I):backup.append({'sheet':sh.attrib['name'],'cell':h.attrib['ref']})
            p=urlsplit(url);dec=unquote(p.path)
            if old not in dec:continue
            candidate=dec.replace(old,new,1)
            relpath=re.sub(r'^/(home|preview)','',candidate)
            q=parse_qs(p.query)
            exact=relpath
            if q.get('preview'):exact=relpath.rstrip('/')+'/'+q['preview'][0]
            evidence=known.get(exact.lower())
            rec={'sheet':sh.attrib['name'],'cell':h.attrib['ref'],'saved_target':url,'suggested_target':url.replace(quote(old,safe='/'),quote(new,safe='/'),1),'native_target':evidence,'verified_against':'family-listings.json'}
            (hits if evidence else unsupported).append(rec)
assert hashlib.sha256(book.read_bytes()).hexdigest()==book_sha
result={'schema':1,'recorded_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'PRE_EXISTING_SAVED_WORKBOOK_LINK_DRIFT','workbook':str(book),'workbook_sha256':book_sha,'published_register':pointer['register'],'scope':'Acanthus native path refresh only. Exact native IDs and current paths in fresh family listing; no photo-role or identity changes. Existing frozen merge preserved unrelated workbook references.','matched_stale_hyperlinks':hits,'unmatched_candidates':unsupported,'active_backup_hyperlinks':backup,'canonical_changes_performed':False,'workbook_changes_performed':False,'dropbox_changes_performed':False}
(HERE/'workbook-folder-link-drift.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({'status':result['status'],'verified_stale_links':len(hits),'unmatched_candidates':len(unsupported),'by_sheet':dict(collections.Counter(x['sheet'] for x in hits)),'native_target_ids':sorted({x['native_target']['file_id'] for x in hits}),'backup_links':len(backup)}))
