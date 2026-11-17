#!/usr/bin/env python3
"""Exercise the file hook in an isolated, signed-out headless Chrome profile."""
import base64
import html
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHROME = Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')


def run():
    if not CHROME.is_file():
        raise RuntimeError('Installed Chrome is required for the upload fixture')
    source = (ROOT / 'browser-helper/page-upload.js').read_text().replace('export async function', 'async function', 1)
    image = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aXioAAAAASUVORK5CYII='
    template = r'''<!doctype html><html><meta charset="utf-8"><title>Upload fixture</title>
<div id="actor">Fixture Account</div><button id="media">Media</button><button id="post">Post</button><div id="preview"></div><pre id="result">RUNNING</pre>
<script>__SOURCE__
(async () => {
  const results = [];
  const assert = (value, name) => { if (!value) throw new Error(name); results.push(name); };
  let foreground = false, changes = 0, pickers = 0, publishes = 0, mime = 'image/png';
  Object.defineProperty(document, 'hasFocus', {value:() => foreground});
  const savedClick = HTMLInputElement.prototype.click;
  const savedPicker = HTMLInputElement.prototype.showPicker;
  Object.defineProperty(HTMLInputElement.prototype, 'click', {configurable:true, writable:true, value() { pickers++; }});
  Object.defineProperty(HTMLInputElement.prototype, 'showPicker', {configurable:true, writable:true, value() { pickers++; }});
  const clickDescriptor = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'click');
  const pickerDescriptor = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'showPicker');
  document.querySelector('#post').onclick = () => publishes++;
  document.querySelector('#media').onclick = () => {
    const input = document.createElement('input'); input.type='file'; input.accept=mime;
    input.click(); // deliberately detached, and the handler is registered afterwards
    input.onchange = () => {
      changes++;
      const img = new Image(); img.src=URL.createObjectURL(input.files[0]);
      document.querySelector('#preview').replaceChildren(img);
    };
  };
  const bytes=Uint8Array.from(atob('__IMAGE__'), c=>c.charCodeAt(0));
  const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),b=>b.toString(16).padStart(2,'0')).join('');
  const owner='fixture-owned-tab';
  document.documentElement.setAttribute('data-boldstone-publisher',owner);
  document.documentElement.setAttribute('data-boldstone-job','fixture-job');
  const request = {request_id:'1'.repeat(32),sha256:hash,base64:'__IMAGE__',size:bytes.length,name:'original.png',mime_type:'image/png',
    expected_url:location.href, owner, job_id:'fixture-job', expires_at:Date.now()/1000+120, timeout_ms:300,
    trigger:[{selector:'#media',name:'Media'}],guards:[{purpose:'account',locator:[{selector:'#actor'}],contains:'Fixture Account'}]};
  try {
    const good=await uploadPhoto(request);
    assert(good.ok && good.sha256===hash && good.phase==='FILE_EVENTS_DISPATCHED','detached input accepted the exact original bytes');
    const img=document.querySelector('#preview img');
    if (!img.complete) await new Promise((resolve,reject)=>{img.onload=resolve;img.onerror=reject;});
    assert(img.complete && img.naturalWidth===1,'an actual image preview loaded after change');
    assert(changes===1 && pickers===0,'one file change and zero native picker calls');
    assert(Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'click').value===clickDescriptor.value &&
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'showPicker').value===pickerDescriptor.value,'prototype methods restored');
    assert((await uploadPhoto(request)).ok && changes===1,'same request receipt returns without repeating file events');
    const badHash=await uploadPhoto({...request,request_id:'2'.repeat(32),sha256:'0'.repeat(64)});
    assert(!badHash.ok && badHash.code==='MEDIA_HASH_CHANGED' && changes===1,'tampered media rejected before upload');
    foreground=true;
    const focused=await uploadPhoto({...request,request_id:'3'.repeat(32)}); foreground=false;
    assert(!focused.ok && focused.code==='FOREGROUND_TAB_PAUSED','foreground document pauses');
    const ownerResult=await uploadPhoto({...request,request_id:'4'.repeat(32),owner:'another-tab'});
    assert(!ownerResult.ok && ownerResult.code==='TAB_OWNERSHIP_LOST','wrong tab owner rejected');
    const jobResult=await uploadPhoto({...request,request_id:'8'.repeat(32),job_id:'another-job'});
    assert(!jobResult.ok && jobResult.code==='UPLOAD_JOB_CHANGED','an old queued job cannot upload into a newer composer');
    const accountResult=await uploadPhoto({...request,request_id:'5'.repeat(32),guards:[{purpose:'account',locator:[{selector:'#actor'}],contains:'Another Account'}]});
    assert(!accountResult.ok && accountResult.code==='WRONG_SELECTED_ACCOUNT','wrong account rejected');
    const postResult=await uploadPhoto({...request,request_id:'6'.repeat(32),trigger:[{selector:'#post',name:'Post'}]});
    assert(!postResult.ok && postResult.code==='UPLOAD_CONTROL_REQUIRED' && publishes===0,'helper cannot click a publish control');
    mime='application/pdf';
    const wrongInput=await uploadPhoto({...request,request_id:'7'.repeat(32)});
    assert(!wrongInput.ok && wrongInput.code==='WRONG_FILE_INPUT' && changes===1,'incompatible file input rejected');
    mime='image/png';
    document.querySelector('#media').textContent='Upload from computer';
    const linkedinUpload=await uploadPhoto({...request,request_id:'9'.repeat(32),trigger:[{selector:'#media',name:'Upload from computer'}]});
    assert(linkedinUpload.ok && changes===2 && pickers===0 && publishes===0,'current LinkedIn upload label supplies one photo without a native picker');
    document.querySelector('#result').textContent=JSON.stringify({passed:true,checks:results,changes,pickers,publishes,scope:'isolated signed-out fixture; no platform publication'});
  } catch(error) {document.querySelector('#result').textContent=JSON.stringify({passed:false,checks:results,error:String(error.stack||error)});}
  finally {
    if(savedClick) HTMLInputElement.prototype.click=savedClick;
    if(savedPicker) HTMLInputElement.prototype.showPicker=savedPicker;
  }
})();</script></html>'''
    with tempfile.TemporaryDirectory(prefix='boldstone-upload-fixture-') as directory:
        directory = Path(directory)
        sys.path.insert(0, str(ROOT))
        from chrome import Chrome
        from settings import Settings
        observer = Chrome(Settings(), directory / 'readonly-observer')
        before = observer.focus_stamp(observer.inventory())
        page = directory / 'upload.html'
        page.write_text(template.replace('__SOURCE__', source).replace('__IMAGE__', image))
        process = subprocess.run([str(CHROME), '--headless=new', '--user-data-dir=' + str(directory / 'profile'),
                                  '--no-first-run', '--no-default-browser-check', '--disable-background-networking',
                                  '--disable-sync', '--dump-dom', '--virtual-time-budget=10000', page.as_uri()],
                                 capture_output=True, text=True, timeout=40, check=False)
        match = re.search(r'<pre id="result">(.*?)</pre>', process.stdout, re.S)
        if process.returncode or not match or html.unescape(match.group(1)) == 'RUNNING':
            raise RuntimeError('Chrome fixture did not finish: ' + process.stderr[-1500:])
        report = json.loads(html.unescape(match.group(1)))
        after = observer.focus_stamp(observer.inventory())
        report['focus_before_after_unchanged'] = before == after
        report['observed_focus_before'] = before
        report['observed_focus_after'] = after
        report['passed'] = report['passed'] and before == after
        print(json.dumps(report, indent=2))
        return 0 if report['passed'] else 1


if __name__ == '__main__':
    sys.exit(run())
