"""Read-only historical report viewer; supplies verified archived images on demand."""
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, quote, urlsplit
from collections import OrderedDict
import argparse
import hashlib
import html
import json
import mimetypes
import threading
import archive_images as archive

PORT = 8778


def image_type(data):
    if data.startswith(b'\xff\xd8\xff'): return 'image/jpeg'
    if data.startswith(b'\x89PNG'): return 'image/png'
    if data.startswith((b'GIF87a',b'GIF89a')): return 'image/gif'
    if data.startswith(b'RIFF') and data[8:12]==b'WEBP': return 'image/webp'
    if data.startswith(b'BM'): return 'image/bmp'
    if data.startswith((b'II*\0',b'MM\0*')): return 'image/tiff'
    return 'application/octet-stream'


class ArchiveServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, port):
        self.manifest = archive.manifest()
        self.rows = {r['path']:r for r in self.manifest['records']}
        self.cache = OrderedDict()
        self.cache_bytes = 0
        self.cache_lock = threading.Lock()
        self.fetch_slots = threading.BoundedSemaphore(3)
        super().__init__(('127.0.0.1', port), Handler)

    def image(self, row):
        sha = row['sha256']
        with self.cache_lock:
            if sha in self.cache:
                self.cache.move_to_end(sha)
                return self.cache[sha]
        with self.fetch_slots:
            data = archive.load_image(self.manifest,self.manifest['blobs'][sha])
        with self.cache_lock:
            if sha not in self.cache and len(data)<=64*1024*1024:
                while self.cache and self.cache_bytes+len(data)>64*1024*1024:
                    _,old=self.cache.popitem(last=False);self.cache_bytes-=len(old)
                self.cache[sha]=data;self.cache_bytes+=len(data)
        return data


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_): pass

    def do_GET(self):
        try:
            path=unquote(urlsplit(self.path).path).lstrip('/')
            absolute_prefix=str(archive.ROOT).lstrip('/')+'/'
            if path.startswith(absolute_prefix):path=path[len(absolute_prefix):]
            if not path:path=str(archive.HERE.relative_to(archive.ROOT)/'index.html')
            requested=archive.ROOT/path
            if '..' in Path(path).parts or not requested.resolve().is_relative_to(archive.ROOT):
                self.send_error(403);return
            # Archived images always use the manifest, even if a new unrelated
            # file later appears at the historical filename.
            if path in self.server.rows:
                row=self.server.rows[path]
                data=self.server.image(row);kind=image_type(data)
            elif requested.is_file() and requested.resolve()==requested:
                data=requested.read_bytes()
                kind=mimetypes.guess_type(requested.name)[0] or 'application/octet-stream'
                if kind=='text/html':
                    # Old file:// and absolute local links become viewer routes.
                    data=data.replace(('file://'+str(archive.ROOT)+'/').encode(),b'/')
                    data=data.replace((str(archive.ROOT)+'/').encode(),b'/')
            else:
                self.send_error(404,'This path is not in the retained report or image archive');return
            self.send_response(200)
            self.send_header('Content-Type',kind)
            self.send_header('Content-Length',str(len(data)))
            self.send_header('Cache-Control','private, max-age=300')
            self.send_header('X-Content-Type-Options','nosniff')
            self.end_headers();self.wfile.write(data)
        except (BrokenPipeError,ConnectionResetError):
            return
        except Exception as error:
            # Never expose Dropbox credentials or request/response exception text.
            self.send_error(503,'Archived image unavailable; use the restoration instructions ('+type(error).__name__+')')


def build_index():
    m=archive.manifest()
    directories=set()
    for r in m['records']:
        p=Path(r['path']).parent
        while p!=Path('.'):
            directories.add(p);p=p.parent
    reports=[]
    for folder in sorted(directories):
        for p in (archive.ROOT/folder).glob('*.html'):
            if p.is_file() and not p.is_symlink():reports.append(str(p.relative_to(archive.ROOT)))
    reports=sorted(set(reports))
    common='''<!doctype html><html lang="en"><meta charset="utf-8"><style>body{font:16px/1.5 system-ui;max-width:1100px;margin:40px auto;padding:0 20px;color:#23332b;background:#faf9f5}h1{font:36px Georgia}input{font:inherit;padding:10px;width:95%}li{margin:8px 0}a{color:#3c623a}code{overflow-wrap:anywhere}.note{padding:15px;background:#e8eee3}</style>'''
    page=common+'<title>Boldstone historical reviews</title><h1>Historical reviews and images</h1>'
    page+='<p class="note">Historical reports remain here. Their image copies are supplied from the verified local archive, retained active copies or matching Dropbox originals. Dropbox images need an internet connection and the existing Mac Keychain connection. Nothing is written to Dropbox.</p>'
    page+='<p>Open this index through <a href="http://127.0.0.1:8778/">the archive viewer</a>. If it is stopped, open <a href="Open historical reviews.command">Open historical reviews.command</a> in this folder.</p>'
    page+='<p><a href="RESTORE-INSTRUCTIONS.txt">Restore original files</a> · <a href="catalogue.json">Image source catalogue</a></p>'
    page+=f'<p>{len(m["records"]):,} archived image paths; {len(m["blobs"]):,} distinct image contents; {len(reports):,} report pages.</p>'
    page+='<input id="q" placeholder="Find a report by sculpture, family or date"><ul id="reports">'
    for rel in reports:
        page+='<li><a href="http://127.0.0.1:8778/'+quote(rel,safe='/')+'">'+html.escape(rel)+'</a></li>'
    page+='</ul><script>document.querySelector("#q").addEventListener("input",e=>{const q=e.target.value.toLowerCase();document.querySelectorAll("#reports li").forEach(x=>x.hidden=!x.textContent.toLowerCase().includes(q))})</script>'
    (archive.HERE/'index.html').write_text(page)
    catalogue=[{'path':r['path'],'bytes':r['bytes'],'sha256':r['sha256'],'source':m['blobs'][r['sha256']]['storage'],
                'viewer_url':'http://127.0.0.1:8778/'+quote(r['path'],safe='/')} for r in m['records']]
    (archive.HERE/'catalogue.json').write_text(json.dumps(catalogue,indent=2))
    archive.write(archive.HERE/'viewer-index.json',{'report_paths':reports,'image_paths':len(catalogue)})
    instructions=f'''Historical review images - access and restoration

Open index.html or http://127.0.0.1:8778/ to browse historical reports.
Start the viewer by opening "Open historical reviews.command" in this folder.
The viewer only reads. It does not delete, move or upload Dropbox files.
Image memory caching is limited to 64 MiB; it does not rebuild the disk cache.

To restore one image to its original local path, without overwriting:
  {archive.ROOT}/application/.venv/bin/python {archive.HERE}/archive_images.py restore 'RELATIVE/PATH/FROM/CATALOGUE' --apply
Omit --apply to preview. Add --destination /absolute/path to restore elsewhere.

All paths, hashes, original permissions and timestamps are in manifest.json.
historical-images.zip stores one copy of each image that lacked an existing
verified retained source. Every ZIP member was restored and hash-checked before
any local copy was removed. Matching Dropbox files retain their stable ID,
revision and content hash in the manifest. Those restores require access to the
recorded Dropbox revision; do not treat Dropbox history as unlimited retention.
Active-local entries refer to protected byte-identical live app files.

Opening an old HTML page directly as file:// may show missing pictures.
Use the archive viewer link instead, or restore its image paths first.
The original HTML, JSON, spreadsheets and canonical catalogue were not edited.
'''
    (archive.HERE/'RESTORE-INSTRUCTIONS.txt').write_text(instructions)
    launcher=archive.HERE/'Open historical reviews.command'
    launcher.write_text('#!/bin/zsh\ncd '+repr(str(archive.HERE))+'\nexec '+repr(str(archive.ROOT/'application/.venv/bin/python'))+' viewer.py\n')
    launcher.chmod(0o755)
    print(json.dumps({'reports':len(reports),'images':len(catalogue)}),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--build-index',action='store_true');p.add_argument('--port',type=int,default=PORT)
    a=p.parse_args()
    if a.build_index:build_index()
    else:
        print('Historical reviews: http://127.0.0.1:'+str(a.port)+'/',flush=True)
        ArchiveServer(a.port).serve_forever()
