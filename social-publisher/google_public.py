"""Read-only Google post verification through its rendered individual post view.

The manager cannot reopen saved video attachments. The public post supplies
the exact article ID, business feature ID, caption, action and native media URL.
Videos are fetched from that observed URL and fully decoded without activating
the browser or playing audio. No private API or framework state is consulted.
"""
import os,re,subprocess,tempfile,time
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse,parse_qs
from urllib.request import Request,urlopen

from common import Hold,atomic_json,digest,read_json,sync_directory,utc
from google_business import norm,rejected_revision_context,observed_revision_context

class FirstTag(HTMLParser):
    def __init__(self,html):
        super().__init__();self.tag=None;self.attrs={};self.feed(html)
    def handle_starttag(self,tag,attrs):
        if self.tag is None:self.tag=tag;self.attrs=dict(attrs)

def public_record(article,caption,author,context,post_id,calibration):
    parsed=urlparse(article.get('url',''));tag=FirstTag(article.get('html',''))
    if (parsed.scheme!='https' or parsed.hostname!='www.google.com' or parsed.path!='/search' or
        parsed.fragment!='lpstate=pid:'+post_id or tag.tag!='article' or
        tag.attrs.get('data-post-id')!=post_id or tag.attrs.get('data-feature-id')!=calibration['feature_id']):
        raise Hold('GOOGLE_PUBLIC_POST_IDENTITY_MISMATCH')
    if norm(caption.get('text'))!=norm(context['caption']) or norm(context['caption']) not in norm(article.get('text')):
        raise Hold('NATIVE_CAPTION_MISMATCH')
    if norm(author.get('text'))!=norm(context['account_name']):raise Hold('WRONG_GOOGLE_BUSINESS_PROFILE')
    if re.search(r'(?im)^\s*(?:Pending|Rejected|Not approved|Only visible to you)\s*$',article.get('text','')):
        raise Hold('GOOGLE_POST_PENDING_OR_REJECTED')
    links=[r for r in article.get('links',[]) if norm(r.get('text'))==norm(context.get('button_label','Buy'))]
    if len(links)!=1 or links[0].get('href')!=context['purchase_url']:raise Hold('NATIVE_PURCHASE_LINK_MISMATCH')
    return {'location_id':context['location_id'],'post_id':post_id,'status':'Public Google post readable',
            'purchase_links':[{'expected':context['purchase_url'],'native_link':links[0]['href'],'method':'Visible action on the exact Google public post'}]}

def native_media_checks(media,context):
    if digest(Path(media['path']).read_bytes())!=media['native_sha256'] or media.get('input_sha256')!=context['media_sha256']:
        raise Hold('NATIVE_MEDIA_HASH_MISMATCH')
    if context.get('media_type')=='video/mp4':
        streams=[r for r in media['metadata'].get('streams',[]) if r.get('codec_type')=='video']
        if len(streams)!=1:raise Hold('NATIVE_VIDEO_MISMATCH')
        v=streams[0];duration=float(v.get('duration',media['metadata'].get('format',{}).get('duration',0)))
        if (v.get('width',0)<=0 or v.get('height',0)<=0 or
            abs(duration-context['video_duration'])>.25 or
            abs(v['width']/v['height']-context['video_width']/context['video_height'])>.01 or
            media.get('complete_movie_decode_exit_code')!=0 or media.get('decode_errors')):raise Hold('NATIVE_VIDEO_MISMATCH')
        return {'src':media['url'],'width':v['width'],'height':v['height'],'duration':duration,
                'input_sha256':context['media_sha256'],'native_sha256':media['native_sha256'],
                'media_type':'video/mp4','rendering':'Native public-post video, fetched from its rendered src and fully decoded'}
    from PIL import Image
    with Image.open(media['path']) as image:
        image.load();width,height=image.size
    if width<=0 or height<=0:raise Hold('NATIVE_PHOTO_MISMATCH')
    return {'src':media['url'],'width':width,'height':height,'input_sha256':context['media_sha256'],
            'native_sha256':media['native_sha256'],'rendering':'Decoded photo from the exact Google public post'}

def public_evidence_checks(proof,context,post_id):
    """Validate the durable public receipt independently of its boolean flags."""
    if proof.get('verification_method')!='google_public_detail_and_decoded_native_media' or proof.get('job_id')!=context['id'] or proof.get('profile_hash')!=context['profile_hash']:
        raise Hold('RECEIPT_INCOMPLETE')
    path=Path(proof['public_profile_calibration_path'])
    if digest(path.read_bytes())!=proof['public_profile_calibration_sha256']:raise Hold('EVIDENCE_CHANGED')
    calibration=read_json(path)
    if context['profile_hash'] not in calibration['profile_hashes'] or context['location_id']!=calibration['location_id']:raise Hold('WRONG_GOOGLE_BUSINESS_PROFILE')
    for reference in calibration['references']:
        if digest(Path(reference['path']).read_bytes())!=reference['sha256']:raise Hold('EVIDENCE_CHANGED')
    kind='video' if context.get('media_type')=='video/mp4' else 'photo'
    prepared_path=Path(proof['prepared_'+kind+'_evidence_path']);prepared=read_json(prepared_path)
    if digest(prepared_path.read_bytes())!=proof['prepared_'+kind+'_evidence_sha256'] or prepared.get('job_id')!=context['id'] or prepared.get('profile_hash')!=context['profile_hash'] or prepared.get('media_sha256')!=context['media_sha256'] or prepared.get(kind,{}).get('input_sha256')!=context['media_sha256']:
        raise Hold('GOOGLE_PREPARED_MEDIA_RECEIPT_MISSING')
    identity=public_record(proof['public_article'],proof['published_caption'],proof['public_author'],context,post_id,calibration)
    return identity,native_media_checks(proof['native_media'],context)

class GooglePublicReadback:
    def __init__(self,workflow,calibration_path,post_id):
        self.workflow=workflow;self.chrome=workflow.chrome;self.directory=workflow.directory
        self.calibration_path=Path(calibration_path);self.post_id=str(post_id)
        if not re.fullmatch(r'\d+',self.post_id):raise Hold('GOOGLE_POST_ID_AMBIGUOUS')

    def reconciliation_epoch(self,job):return self.workflow.reconciliation_epoch(job)

    def calibration(self,context):
        data=read_json(self.calibration_path)
        for ref in data['references']:
            if digest(Path(ref['path']).read_bytes())!=ref['sha256']:raise Hold('GOOGLE_PUBLIC_CALIBRATION_CHANGED')
        if data['location_id']!=context['location_id'] or context['profile_hash'] not in data['profile_hashes']:
            raise Hold('GOOGLE_PUBLIC_PROFILE_RECALIBRATION_REQUIRED')
        parsed=urlparse(data['public_base_url']);query=parse_qs(parsed.query)
        if parsed.scheme!='https' or parsed.hostname!='www.google.com' or parsed.path!='/search' or query.get('q')!=[context['account_name']] or not query.get('stick'):
            raise Hold('GOOGLE_PUBLIC_PROFILE_RECALIBRATION_REQUIRED')
        return data

    def verify(self,job,native_url=None):
        c=rejected_revision_context(self.workflow.context(job),self.directory)
        if c.get('platform')!='google_business_profile':raise Hold('GOOGLE_PUBLIC_READBACK_ONLY')
        if digest(Path(c['media_path']).read_bytes())!=c['media_sha256']:raise Hold('MEDIA_HASH_CHANGED')
        cal=self.calibration(c)
        editor=c['inventory_url']+'/'+self.post_id+'/edit'
        url=cal['public_base_url'].split('#',1)[0]+'#lpstate=pid:'+self.post_id
        if native_url is not None and native_url not in {editor,url}:raise Hold('NATIVE_PERMALINK_INVALID')
        selector='[role=dialog] article[data-post-id="'+self.post_id+'"]'
        try:
            # A fragment-only change can retain the previous article. A full
            # navigation, followed by the exact rendered article ID, prevents
            # stale content from being attributed to another post.
            self.chrome.navigate('verification',c['inventory_url'],job['id'],recovery=True)
            self.chrome.navigate('verification',url,job['id'],recovery=True)
            deadline=time.monotonic()+25
            while not self.chrome.call('verification',{'op':'exists','locator':[{'selector':selector,'painted':True}]})['exists']:
                if time.monotonic()>=deadline:raise Hold('GOOGLE_PUBLIC_POST_NOT_AVAILABLE',retryable=True)
                time.sleep(.5)
            article=self.chrome.call('verification',{'op':'snapshot','scope':[{'selector':selector,'painted':True}],'includeHTML':True})
            caption=self.chrome.call('verification',{'op':'snapshot','scope':[{'selector':selector+' span.A5yTVb','painted':True}]})
            author=self.chrome.call('verification',{'op':'snapshot','scope':[{'selector':selector+' div.LHVjrc','painted':True}]})
            c=observed_revision_context(c,caption['text']);identity=public_record(article,caption,author,c,self.post_id,cal)
            kind='video' if c.get('media_type')=='video/mp4' else 'photo'
            if kind=='video':
                candidates=[r for r in article.get('videos',[]) if r.get('visible') and r.get('src')]
            else:
                candidates=[r for r in article.get('images',[]) if r.get('width',0)>=200 and r.get('height',0)>=200 and r.get('alt')!=c['account_name']]
            if len(candidates)!=1:raise Hold('NATIVE_'+kind.upper()+'_MISMATCH')
            src=candidates[0]['src'];host=urlparse(src)
            if host.scheme!='https' or not (host.hostname or '').endswith('.googleusercontent.com'):raise Hold('NATIVE_MEDIA_SOURCE_INVALID')
            with urlopen(Request(src,headers={'User-Agent':'Mozilla/5.0'}),timeout=30) as response:
                raw=response.read(20_000_001);content_type=response.headers.get('Content-Type','')
            if not raw or len(raw)>20_000_000:raise Hold('NATIVE_MEDIA_SIZE_INVALID')
            media_path=self.directory/'evidence'/(job['id']+'-public-media-'+digest(raw)[:12]+('.mp4' if kind=='video' else '.jpg'))
            if media_path.exists() and digest(media_path.read_bytes())!=digest(raw):raise Hold('EVIDENCE_CHANGED')
            if not media_path.exists():
                fd,temporary=tempfile.mkstemp(prefix='.public-native-',dir=str(media_path.parent))
                try:
                    with os.fdopen(fd,'wb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
                    os.replace(temporary,media_path);sync_directory(media_path.parent)
                finally:
                    if os.path.exists(temporary):os.unlink(temporary)
            media={'url':src,'path':str(media_path.resolve()),'native_sha256':digest(raw),'bytes':len(raw),'content_type':content_type,'input_sha256':c['media_sha256']}
            if kind=='video':
                import json
                result=subprocess.run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(media_path)],capture_output=True,text=True,timeout=30,check=True)
                media['metadata']=json.loads(result.stdout)
                decoded=subprocess.run(['ffmpeg','-nostdin','-v','error','-threads','1','-i',str(media_path),'-f','null','-'],capture_output=True,text=True,timeout=90,check=True)
                media.update(complete_movie_decode_exit_code=decoded.returncode,decode_errors=decoded.stderr)
            checked=native_media_checks(media,c)
            prepared_path=self.directory/'evidence'/(job['id']+'-google-'+kind+'.json');prepared=read_json(prepared_path)
            if prepared.get('job_id')!=job['id'] or prepared.get('profile_hash')!=c['profile_hash'] or prepared.get('media_sha256')!=c['media_sha256'] or prepared.get(kind,{}).get('input_sha256')!=c['media_sha256']:
                raise Hold('GOOGLE_PREPARED_MEDIA_RECEIPT_MISSING')
            composer={}
            # Release only this exact retained original upload, after the
            # independent public post and complete native media are proven.
            # Older held jobs must never touch a different job's current form.
            binding=self.chrome.bindings.get(c['profile_id'])
            if binding and binding.get('job_id')==job['id'] and binding['url']==c['compose_url'] and binding.get('dirty'):
                try:
                    from workflow import render
                    recipe=self.workflow.settings.workflow(self.workflow.settings.profile(c['profile_id']))
                    self.chrome.confirm_upload_preview(c['profile_id'],render(recipe['google_'+kind],c),c)
                    self.chrome.call(c['profile_id'],{'op':'assert','checks':[{'locator':[{'selector':'textarea[maxlength="1500"]'}],'text':c['caption']},{'locator':[{'selector':'input[type=url]'}],'text':c['purchase_url']}]})
                    self.chrome.checkpoint(c['profile_id'],0,dirty=False)
                    self.chrome.navigate(c['profile_id'],c['inventory_url'],job['id'],recovery=True)
                    composer={'retained_confirmed_original_form_released':True}
                except Hold as error:composer={'composer_warning':str(error)}
            evidence={'job_id':job['id'],'profile_hash':c['profile_hash'],'verified_utc':utc(),'verification_method':'google_public_detail_and_decoded_native_media',
                'url':url,'native_record':identity,'public_article':article,'published_caption':caption,'public_author':author,
                'native_media':media,kind:checked,'purchase_links':identity['purchase_links'],
                'public_profile_calibration_path':str(self.calibration_path.resolve()),'public_profile_calibration_sha256':digest(self.calibration_path.read_bytes()),
                'prepared_'+kind+'_evidence_path':str(prepared_path.resolve()),'prepared_'+kind+'_evidence_sha256':digest(prepared_path.read_bytes()),**composer}
            path=self.directory/'evidence'/(job['id']+'-public-native-'+digest(evidence)[:12]+'.json');atomic_json(path,evidence)
            receipt={'native_url':url,'native_url_kind':'Google public post detail','google_location_id':c['location_id'],'google_post_id':self.post_id,
                'google_status':identity['status'],'caption_verified':True,'author_verified':True,'photo_verified':kind=='photo','video_verified':kind=='video',
                'public_detail_verified':True,'media_sha256':c['media_sha256'],'purchase_links':identity['purchase_links'],'verified_utc':evidence['verified_utc'],
                'evidence_path':str(path.resolve()),'evidence_sha256':digest(path.read_bytes())}
            if c.get('caption_revision_evidence_path'):receipt.update(effective_caption=c['caption'],caption_revision_applied=c['caption_revision_applied'],caption_revision_evidence_path=c['caption_revision_evidence_path'],caption_revision_evidence_sha256=c['caption_revision_evidence_sha256'])
            return receipt
        finally:
            b=self.chrome.bindings['verification']
            if b['url']!=c['inventory_url']:self.chrome.navigate('verification',c['inventory_url'],job['id'],recovery=True)
