"""Bounded AppleScript operations with durable, duplicate-safe Meta publication receipts.

This operates visible browser controls. It never reads cookies, private app state or
tokens, and never retries Publish after an uncertain result. Permission prompts and
CAPTCHAs are handed to the user. A verified live UI profile is required for publishing.
"""
import argparse
import contextlib
import fcntl
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).resolve().parent
BUSINESS = '2380586078685156'
PAGE = '103781478537396'
ACCOUNT = 'boldstonesculpture'
PREFLIGHT = '''ObjC.import("Cocoa"); ObjC.import("ApplicationServices");
var f=$.NSWorkspace.sharedWorkspace.frontmostApplication;
JSON.stringify({frontmost:ObjC.unwrap(f.bundleIdentifier),accessibilityTrusted:Boolean($.AXIsProcessTrusted())});'''

class Blocked(RuntimeError): pass

def stamp(): return datetime.now(timezone.utc).isoformat()
def digest(value): return hashlib.sha256(value).hexdigest()

def bounded(argv, timeout=9, run=subprocess.run):
    try:
        p=run(argv, capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as error:
        raise Blocked('AppleScript wall-clock timeout; no automatic retry') from error
    if p.returncode:
        message=p.stderr.strip()[-900:]
        raise Blocked('AppleScript refused or timed out: '+message)
    return p.stdout.strip()

def preflight(run=subprocess.run):
    state=json.loads(bounded(['/usr/bin/osascript','-l','JavaScript','-e',PREFLIGHT],run=run))
    if state['frontmost']=='com.apple.UserNotificationCenter':
        raise Blocked('A protected macOS permission prompt holds focus. Ask the user to clear it.')
    if not state['accessibilityTrusted']:
        raise Blocked('The posting runner lacks macOS Accessibility access. No browser action attempted.')
    if state['frontmost']!='com.google.Chrome':
        raise Blocked('Chrome is not frontmost. No keyboard operation attempted.')
    return state

def check_url(url, composer=False):
    u=urlparse(url);q=parse_qs(u.query)
    if u.scheme!='https' or u.netloc!='business.facebook.com' or not u.path.startswith('/latest/'):
        raise Blocked('Wrong website')
    if q.get('business_id')!=[BUSINESS] or q.get('asset_id')!=[PAGE]:
        raise Blocked('Wrong Meta business or Page')
    if composer and u.path!='/latest/composer/': raise Blocked('Expected the Meta composer')

def required_script(name):
    path = HERE / name
    if not path.is_file():
        raise Blocked('Required posting helper is missing: '+str(path)+'. Restore the reviewed AppleScript source before using the standalone runner. No browser action attempted.')
    return path

def bridge(url, operation, arguments=None, run=subprocess.run):
    check_url(url)
    request=dict(operation=operation,arguments=arguments or {})
    # This source uses only visible DOM and ordinary controls.
    js='('+DOM_DRIVER+')('+json.dumps(request,ensure_ascii=True)+')'
    result=bounded(['/usr/bin/osascript',str(required_script('meta_browser.applescript')),url,js],run=run)
    value=json.loads(result)
    if not value.get('ok'): raise Blocked(value.get('error','No browser receipt'))
    return value

DOM_DRIVER = r'''function(request){
try{
 const visible=e=>!!(e.getClientRects().length)&&getComputedStyle(e).visibility!=='hidden';
 const label=e=>e.getAttribute('aria-label')||e.innerText||e.getAttribute('title')||'';
 const controls=()=>Array.from(document.querySelectorAll('button,[role="button"],textarea,input,[contenteditable="true"]')).filter(visible);
 const find=(name)=>{const a=controls().filter(e=>label(e).trim()===name);if(a.length!==1)throw Error('Expected one visible control: '+name+'; found '+a.length);return a[0];};
 const args=request.arguments;
 if(request.operation==='snapshot')return JSON.stringify({ok:true,url:location.href,title:document.title,text:document.body.innerText,controls:controls().map(e=>({role:e.getAttribute('role')||e.tagName.toLowerCase(),label:label(e),disabled:e.disabled||e.getAttribute('aria-disabled')==='true'})),instagramLinks:Array.from(document.querySelectorAll('a[href]')).filter(visible).map(e=>({text:label(e),href:e.href})).filter(x=>/^https:\/\/(www\.)?instagram\.com\/(p|reel)\//.test(x.href))});
 if(request.operation==='click'){
   if(args.name==='Publish')throw Error('Publish requires the guarded publish operation');
   find(args.name).click();return JSON.stringify({ok:true,status:'CONTROL_CLICKED',name:args.name});
 }
 if(request.operation==='caption'){
   const field=find('Write in the dialogue box to include text with your post.');
   field.focus();
   if(field.isContentEditable){document.execCommand('selectAll',false,null);document.execCommand('insertText',false,args.caption);}
   else{const proto=field.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;Object.getOwnPropertyDescriptor(proto,'value').set.call(field,args.caption);field.dispatchEvent(new Event('input',{bubbles:true}));field.dispatchEvent(new Event('change',{bubbles:true}));}
   const value=field.isContentEditable?field.innerText:field.value;
   if(value!==args.caption)throw Error('Caption did not read back exactly');
   return JSON.stringify({ok:true,status:'CAPTION_READBACK',caption:value});
 }
 if(request.operation==='verifyReady'||request.operation==='publish'){
   const caption=find('Write in the dialogue box to include text with your post.');
   if((caption.isContentEditable?caption.innerText:caption.value)!==args.caption)throw Error('Caption changed');
   if(!document.body.innerText.includes('boldstonesculpture'))throw Error('Instagram account not visible');
   const tag=Array.from(document.querySelectorAll(args.tagSelector)).filter(visible);
   if(tag.length!==1||tag[0].innerText.trim()!==args.tagText)throw Error('Exact selected Commerce product tag is absent or changed');
   const media=Array.from(document.querySelectorAll(args.mediaSelector)).filter(visible);
   if(media.length!==1)throw Error('Expected exactly one uploaded media preview');
   const button=find('Publish');if(button.disabled||button.getAttribute('aria-disabled')==='true')throw Error('Publish is disabled');
   if(request.operation==='publish')button.click();
   return JSON.stringify({ok:true,status:request.operation==='publish'?'PUBLISH_CLICKED_UNCONFIRMED':'READY_READBACK',tagText:args.tagText});
 }
 throw Error('Unsupported operation');
}catch(error){return JSON.stringify({ok:false,error:String(error.message||error)});}
}'''

def validate_item(item):
    required=['catalogue_id','sku','caption','media_path','sha256','title']
    if any(not item.get(k) for k in required):raise Blocked('Incomplete post manifest')
    media=Path(item['media_path'])
    if not media.is_absolute() or not media.is_file():raise Blocked('Media file unavailable')
    if digest(media.read_bytes())!=item['sha256']:raise Blocked('Media changed after review')
    if not item['catalogue_id'].startswith('BSI-'):raise Blocked('Unexpected catalogue identity')
    return digest((item['catalogue_id']+'\n'+item['caption']+'\n'+item['sha256']).encode())

class Journal:
    def __init__(self,path):self.path=Path(path);self.events=[]
    @contextlib.contextmanager
    def locked(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.path.with_suffix('.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            self.events=[json.loads(line) for line in self.path.read_text().splitlines()] if self.path.exists() else []
            yield self
    def append(self,kind,item_hash,**values):
        event=dict(kind=kind,item_hash=item_hash,utc=stamp(),**values)
        with self.path.open('a') as stream:
            stream.write(json.dumps(event,ensure_ascii=False)+'\n');stream.flush();os.fsync(stream.fileno())
        self.events.append(event)
    def may_publish(self,item_hash):
        if any(e['item_hash']==item_hash and e['kind'] in ['PUBLISH_INTENT','PUBLISH_CLICKED_UNCONFIRMED','PUBLISHED','UNCERTAIN_NEEDS_RECONCILIATION'] for e in self.events):
            raise Blocked('A publish intent already exists. Reconcile the actual post before any retry.')

def publish_once(item,url,profile,journal,execute=bridge,permission_check=preflight):
    item_hash=validate_item(item);check_url(url,composer=True)
    if not profile.get('duplicate_search_verified_utc') or profile.get('duplicate_search_result')!='NO_MATCH':
        raise Blocked('Search the published content for this exact product/caption before publishing')
    if profile.get('catalogue_id')!=item['catalogue_id'] or profile.get('sku')!=item['sku']:
        raise Blocked('Commerce tag identity differs from the reviewed product')
    if not all(profile.get(k) for k in ['tag_selector','tag_text','media_selector']):
        raise Blocked('Missing verified visible UI profile for selected tag/media')
    args=dict(caption=item['caption'],tagSelector=profile['tag_selector'],tagText=profile['tag_text'],mediaSelector=profile['media_selector'])
    with journal.locked():
        journal.may_publish(item_hash)
        permission_check()
        ready=execute(url,'verifyReady',args)
        if ready.get('status')!='READY_READBACK':raise Blocked('No exact ready-state readback')
        # An intent is durable BEFORE the irreversible browser click.
        journal.append('PUBLISH_INTENT',item_hash,catalogue_id=item['catalogue_id'],sku=item['sku'],caption_sha256=digest(item['caption'].encode()),media_sha256=item['sha256'],tag=ready['tagText'])
        try:
            result=execute(url,'publish',args)
        except Exception as error:
            journal.append('UNCERTAIN_NEEDS_RECONCILIATION',item_hash,error_type=type(error).__name__)
            raise
        journal.append('PUBLISH_CLICKED_UNCONFIRMED',item_hash,result=result)
        return dict(status='NEEDS_NATIVE_POST_ID_AND_PERMALINK_READBACK',item_hash=item_hash)

def reconcile(item,url,permalink,journal,execute=bridge):
    item_hash=validate_item(item);check_url(url)
    if not re.fullmatch(r'https://www\.instagram\.com/(?:p|reel)/[A-Za-z0-9_-]+/?',permalink):
        raise Blocked('Expected a native Instagram post permalink')
    with journal.locked():
        if not any(e['item_hash']==item_hash and e['kind']=='PUBLISH_INTENT' for e in journal.events):
            raise Blocked('No matching publish intent')
        native=execute(url,'snapshot')
        normalize=lambda s:' '.join(s.split())
        if normalize(item['caption']) not in normalize(native['text']):
            raise Blocked('The full reviewed caption is not visible on the native post')
        if not any(p['href'].rstrip('/')==permalink.rstrip('/') for p in native['instagramLinks']):
            raise Blocked('The permalink is not visible in the native Meta readback')
        journal.append('PUBLISHED',item_hash,catalogue_id=item['catalogue_id'],sku=item['sku'],native_url=url,permalink=permalink)
        return dict(status='PUBLISHED_NATIVE_READBACK',permalink=permalink)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation',choices=['preflight','inspect','caption','click','choose-file','publish','reconcile'])
    parser.add_argument('--url');parser.add_argument('--manifest',type=Path);parser.add_argument('--item')
    parser.add_argument('--name');parser.add_argument('--profile',type=Path);parser.add_argument('--journal',type=Path)
    parser.add_argument('--permalink')
    args=parser.parse_args()
    try:
        if args.operation=='preflight': result=preflight()
        else:
            preflight()
            if args.operation=='inspect':result=bridge(args.url,'snapshot')
            else:
                if not args.manifest or not args.item:raise Blocked('Manifest and catalogue item are required')
                matches=[p for p in json.loads(args.manifest.read_text()) if p['catalogue_id']==args.item]
                if len(matches)!=1:raise Blocked('Expected one manifest item')
                item=matches[0];validate_item(item)
                if args.operation=='caption':check_url(args.url,True);result=bridge(args.url,'caption',dict(caption=item['caption']))
                elif args.operation=='click':result=bridge(args.url,'click',dict(name=args.name))
                elif args.operation=='choose-file':result=dict(status=bounded(['/usr/bin/osascript',str(required_script('meta_choose_file.applescript')),item['media_path']]))
                elif args.operation=='reconcile':
                    if not args.journal:raise Blocked('Durable journal required')
                    result=reconcile(item,args.url,args.permalink,Journal(args.journal))
                else:
                    if not args.profile or not args.journal:raise Blocked('Verified UI profile and durable journal required')
                    result=publish_once(item,args.url,json.loads(args.profile.read_text()),Journal(args.journal))
        print(json.dumps(dict(status='PASS',result=result),ensure_ascii=False));return 0
    except (Blocked,BlockingIOError) as error:
        print(json.dumps(dict(status='BLOCKED',reason=str(error)),ensure_ascii=False));return 2

if __name__=='__main__':sys.exit(main())
