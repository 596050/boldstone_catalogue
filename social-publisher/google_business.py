"""Google Business Profile native records, without replaying a submission.

Google's standalone manager renders uploaded photographs as SVG images. Its
published inventory supplies the stable location/post IDs and public status;
the saved editor independently supplies the description, photograph and button.
"""
import re
import time

from common import Hold, atomic_json, digest, read_json, utc
from chrome import VERIFICATION


def rejected_revision_context(context, directory):
    """A durable, caption-only edit of one concretely rejected existing record."""
    from pathlib import Path
    from journal import Store
    path=Path(directory)/'evidence'/(context['id']+'-google-rejected-revision.json')
    if not path.exists():return context
    proof=read_json(path);sha=digest(path.read_bytes())
    ledger=Store.__new__(Store);ledger.ledger_path=Path(directory)/'intent-ledger.jsonl'
    events=ledger.read_ledger()
    matches=[e for e in events if e['kind']=='GOOGLE_REJECTED_REVISION_INTENT' and e['job_id']==context['id'] and e['evidence_sha256']==sha and e['evidence_path']==str(path.resolve())]
    if len(matches)!=1 or proof.get('job_id')!=context['id'] or proof.get('profile_hash')!=context['profile_hash'] or proof.get('media_sha256')!=context['media_sha256'] or proof.get('original_caption')!=context['caption'] or proof.get('location_id')!=context['location_id'] or not 0<len(proof.get('revised_caption',''))<=1500:
        raise Hold('GOOGLE_REJECTED_REVISION_NOT_PROVEN')
    rejection=proof['rejected_record'];records=set(re.findall(r'data-post-name="accounts/-/locations/(\d+)/localPosts/(\d+)"',rejection['snapshot'].get('html','')))
    if records!={(context['location_id'],proof['post_id'])} or norm(rejection['caption']['text'])!=norm(context['caption']) or norm(rejection['status']['text'])!='Rejected':
        raise Hold('GOOGLE_REJECTED_REVISION_NOT_PROVEN')
    expected=context['inventory_url']+'/'+proof['post_id']+'/edit'
    if proof['native_url']!=expected:raise Hold('GOOGLE_REJECTED_REVISION_NOT_PROVEN')
    return {**context,'caption':proof['revised_caption'],'caption_before_revision':context['caption'],'native_revision_url':expected,'caption_revision_evidence_path':str(path.resolve()),'caption_revision_evidence_sha256':sha,'caption_revision_verification_base':proof['verification_attempts_before_revision']}


def observed_revision_context(context, caption):
    if not context.get('native_revision_url'):return context
    if norm(caption)==norm(context['caption']):return {**context,'caption_revision_applied':True}
    if norm(caption)==norm(context['caption_before_revision']):return {**context,'caption':context['caption_before_revision'],'caption_revision_applied':False}
    raise Hold('NATIVE_CAPTION_MISMATCH')


def norm(value):
    return ' '.join(str(value or '').replace('\u200b', '').replace('\ufeff', '').split())


def unattempted_reconciliation_base(context, directory):
    """A first actual click gets its own bounded read-only verification budget."""
    from pathlib import Path
    from journal import Store
    from common import ROOT
    path=Path(directory)/'evidence'/(context['id']+'-unattempted-document-resume.json')
    if not path.exists():return 0
    proof=read_json(path);sha=digest(path.read_bytes())
    allowed={(Path(directory)/'intent-ledger.jsonl').resolve(),(ROOT/'state/intent-ledger.jsonl').resolve()}
    ledger_path=Path(proof.get('intent_ledger_path',Path(directory)/'intent-ledger.jsonl')).resolve()
    if ledger_path not in allowed:raise Hold('UNATTEMPTED_SUBMISSION_PROOF_NOT_PROVEN')
    ledger=Store.__new__(Store);ledger.ledger_path=ledger_path
    events=ledger.read_ledger()
    resumes=[e for e in events if e['kind']=='GOOGLE_UNATTEMPTED_SUBMISSION_RESUME_INTENT' and e['job_id']==context['id'] and e['evidence_path']==str(path.resolve()) and e['evidence_sha256']==sha]
    original=[e for e in events if e['kind']=='PUBLISH_INTENT' and e['job']['id']==context['id']]
    base=proof.get('verification_attempts_before_resume')
    if (len(resumes)!=1 or len(original)!=1 or proof.get('original_publish_intent_sha256')!=original[0]['sha256'] or
        proof.get('job_id')!=context['id'] or proof.get('profile_hash')!=context['profile_hash'] or
        proof.get('media_sha256')!=context['media_sha256'] or proof.get('native_url')!=context['compose_url'] or
        type(base) is not int or base<0):raise Hold('UNATTEMPTED_SUBMISSION_PROOF_NOT_PROVEN')
    return base


def record_identity(snapshot, caption_snapshot, status_snapshot, context):
    if norm(caption_snapshot.get('text')) != norm(context['caption']):
        raise Hold('NATIVE_CAPTION_MISMATCH', retryable=True)
    records = set(re.findall(r'data-post-name="accounts/-/locations/(\d+)/localPosts/(\d+)"', snapshot.get('html', '')))
    if len(records) != 1:
        raise Hold('GOOGLE_POST_ID_AMBIGUOUS')
    location, post_id = next(iter(records))
    if location != context['location_id']:
        raise Hold('WRONG_GOOGLE_BUSINESS_PROFILE')
    lines = [norm(line) for line in status_snapshot.get('text', '').splitlines()]
    if any(re.match(r'^(Pending|Not approved|Rejected|Processing)(?:\b|$)', line, re.I) for line in lines):
        raise Hold('GOOGLE_POST_PENDING_OR_REJECTED', 'Google has not marked this post Published; retain its intent and check its status again', retryable=True)
    status = next((line for line in lines if re.match(r'^Published\b', line)), None)
    if not status:
        raise Hold('GOOGLE_POST_NOT_PUBLISHED', retryable=True)
    return {'location_id': location, 'post_id': post_id, 'status': status}


def saved_text_action(snapshot, context):
    """Saved text and destination only; this is never a media publication proof."""
    descriptions = [item for item in snapshot.get('editors', []) if item.get('tag') == 'TEXTAREA' and 'maxlength="1500"' in item.get('html', '')]
    if len(descriptions) != 1 or norm(descriptions[0].get('value')) != norm(context['caption']):
        raise Hold('NATIVE_CAPTION_MISMATCH')
    destinations = [item.get('value') for item in snapshot.get('inputs', []) if 'type="url"' in item.get('html', '')]
    if destinations != [context['purchase_url']]:
        raise Hold('NATIVE_PURCHASE_LINK_MISMATCH')
    button=context.get('button_label','Buy')
    if button not in {'Buy','Learn more'}:
        raise Hold('GOOGLE_BUTTON_UNSUPPORTED')
    if not any(item.get('tag') == 'BUTTON' and item.get('name') == button for item in snapshot.get('controls', [])):
        raise Hold('GOOGLE_BUY_BUTTON_MISSING' if button=='Buy' else 'GOOGLE_ACTION_BUTTON_MISSING')
    return {'purchase_links': [{'expected': context['purchase_url'], 'native_link': destinations[0], 'method': 'saved native '+button+' button destination'}]}


def saved_details(snapshot, photo_proof, context):
    checked=saved_text_action(snapshot,context)
    kind='video' if context.get('media_type')=='video/mp4' else 'photo'
    photos = [item[kind] for item in photo_proof.get('checks', []) if item.get(kind) and (kind=='video' or item.get('image'))]
    if len(photos) != 1 or photos[0].get('input_sha256') != context['media_sha256'] or photos[0].get('width', 0) <= 0 or photos[0].get('height', 0) <= 0:
        raise Hold('NATIVE_'+kind.upper()+'_MISMATCH')
    if kind=='video' and (photos[0].get('media_type')!='video/mp4' or abs(photos[0].get('duration',0)-context['video_duration'])>.25 or abs(photos[0]['width']/photos[0]['height']-context['video_width']/context['video_height'])>.01):
        raise Hold('NATIVE_VIDEO_MISMATCH')
    return {kind: photos[0], **checked}


def unattempted_document(upload, prepared, ready, context):
    """Prove the original upload document has never reached its Post click."""
    kind='video' if context.get('media_type')=='video/mp4' else 'photo'
    media=[r[kind] for r in ready.get('checks',[]) if r.get(kind)]
    original=prepared.get(kind,{})
    if ('submission_marker' not in upload or upload.get('document_url')!=context['compose_url'] or upload.get('document_job')!=context['id'] or
        not upload.get('same_job') or not upload.get('committed') or upload.get('submission_marker') is not None or
        upload.get('sha256')!=context['media_sha256'] or prepared.get('job_id')!=context['id'] or
        prepared.get('profile_hash')!=context['profile_hash'] or prepared.get('media_sha256')!=context['media_sha256'] or
        len(media)!=1 or not original.get('src','').startswith('blob:https://www.google.com/') or
        media[0].get('src')!=original.get('src') or media[0].get('input_sha256')!=context['media_sha256']):
        raise Hold('ORIGINAL_UNATTEMPTED_DOCUMENT_NOT_PROVEN')
    return {'same_original_blob':True,'committed_original_media':True,'submission_marker_absent':True,'media_kind':kind}


def link_validation_rejection(snapshot, context):
    """A concrete client-side rejection, never a timeout or inventory absence."""
    fields=[item for item in snapshot.get('inputs',[]) if 'type="url"' in item.get('html','')]
    descriptions=[item for item in snapshot.get('editors',[]) if item.get('tag')=='TEXTAREA']
    return (snapshot.get('url')==context['compose_url'] and len(fields)==1 and
            'aria-invalid="true"' in fields[0].get('html','') and
            fields[0].get('value')==context['purchase_url'] and
            'A link is required for this button' in snapshot.get('text','') and
            len(descriptions)==1 and norm(descriptions[0].get('value'))==norm(context['caption']) and
            any(item.get('tag')=='BUTTON' and item.get('name')==context.get('button_label','Buy') for item in snapshot.get('controls',[])))


class GoogleBusinessProfile:
    def __init__(self, workflow):
        self.workflow = workflow
        self.chrome = workflow.chrome
        self.directory = workflow.directory

    def find_inventory_record(self, reader, row):
        """Expand the observed native More posts control without submitting."""
        more=[{'selector':'button','name':'More posts'}]
        self.workflow.wait(reader,[{'selector':'h1','text':'Your posts'}],timeout=30)
        for page in range(65):
            if self.chrome.call(reader,{'op':'exists','locator':row})['exists']:return
            if not self.chrome.call(reader,{'op':'exists','locator':more})['exists']:
                self.workflow.wait(reader,row,timeout=3);return
            if page==64:raise Hold('GOOGLE_INVENTORY_PAGE_LIMIT')
            before=self.chrome.call(reader,{'op':'probe'}).get('googlePostRecordNames')
            if not isinstance(before,list):raise Hold('GOOGLE_INVENTORY_PAGE_NOT_PROVEN')
            self.chrome.call(reader,{'op':'click','locator':more,'method':'mouse'})
            deadline=time.monotonic()+15
            while True:
                if self.chrome.call(reader,{'op':'exists','locator':row})['exists']:return
                after=self.chrome.call(reader,{'op':'probe'}).get('googlePostRecordNames')
                if isinstance(after,list) and set(after)-set(before):break
                if time.monotonic()>=deadline:raise Hold('GOOGLE_INVENTORY_PAGE_NOT_LOADED',retryable=True)
                time.sleep(.25)

    def resolve_caption_record(self, reader, context, recipe):
        """Disambiguate equal captions by each exact saved action destination."""
        cards=self.chrome.call(reader,{'op':'probe'}).get('googlePostCards',[])
        cards=[r for r in cards if norm(r['caption'])==norm(context['caption'])]
        if len(cards)<2:raise Hold('GOOGLE_CAPTION_CANDIDATES_NOT_PROVEN')
        matches=[];evidence=[]
        for card in cards:
            ids=set()
            for name in card['record_names']:
                match=re.fullmatch(r'accounts/-/locations/(\d+)/localPosts/(\d+)',name or '')
                if match:ids.add(match.groups())
            if len(ids)!=1:raise Hold('GOOGLE_POST_ID_AMBIGUOUS')
            location,post_id=next(iter(ids))
            if location!=context['location_id']:raise Hold('WRONG_GOOGLE_BUSINESS_PROFILE')
            url=context['inventory_url']+'/'+post_id+'/edit'
            self.chrome.navigate(reader,url,context['id'],recovery=True)
            self.workflow.wait(reader,[{'selector':'textarea[maxlength="1500"]'}],timeout=30)
            saved=self.chrome.call(reader,{'op':'snapshot','fullDocument':True})
            try:saved_text_action(saved,context);matches.append(post_id);matched=True
            except Hold as error:
                if error.code!='NATIVE_PURCHASE_LINK_MISMATCH':raise
                matched=False
            evidence.append({'post_id':post_id,'url':url,'saved_editor':saved,'expected_destination_matched':matched})
        if len(set(matches))!=1:raise Hold('GOOGLE_NATIVE_DESTINATION_AMBIGUOUS')
        path=self.directory/'evidence'/(context['id']+'-caption-candidates-'+digest(evidence)[:12]+'.json')
        atomic_json(path,{'job_id':context['id'],'profile_hash':context['profile_hash'],'expected_destination':context['purchase_url'],'selected_post_id':matches[0],'candidates':evidence})
        self.chrome.navigate(reader,context['inventory_url'],context['id'],recovery=True)
        return matches[0],{'caption_resolution_evidence_path':str(path.resolve()),'caption_resolution_evidence_sha256':digest(path.read_bytes())}

    def resume_unattempted(self, store, job):
        """Finish a first Post only in its intact, provably unclicked document."""
        from pathlib import Path
        from engine import Engine
        from workflow import render
        c=self.workflow.context(job);name=c['profile_id']
        if c.get('platform')!='google_business_profile' or job['state']!='OUTCOME_UNKNOWN' or not store.has_intent(job['id']):
            raise Hold('UNATTEMPTED_SUBMISSION_NOT_ALLOWED')
        binding,_=self.chrome.bound(name,mutation=True)
        if binding.get('job_id')!=job['id'] or binding['url']!=c['compose_url'] or binding['profile_hash']!=c['profile_hash']:
            raise Hold('ORIGINAL_UNATTEMPTED_DOCUMENT_NOT_PROVEN')
        recipe=self.workflow.settings.workflow(self.workflow.settings.profile(name));kind='video' if c.get('media_type')=='video/mp4' else 'photo'
        prepared_path=self.directory/'evidence'/(job['id']+'-google-'+kind+'.json');prepared=read_json(prepared_path)
        def check_document():
            upload=self.chrome.call(name,{'op':'upload_status','job':job['id'],'mediaSha256':c['media_sha256']})
            ready=self.chrome.call(name,{'op':'ready','job':job['id'],'mediaSha256':c['media_sha256'],'checks':self.workflow.guards(recipe,c),'submit':render(recipe['submit'],c)})
            return upload,ready,unattempted_document(upload,prepared,ready,c)
        before=check_document()
        self.chrome.navigate(VERIFICATION,c['inventory_url'],job['id'],recovery=True)
        self.workflow.wait(VERIFICATION,[{'selector':'h1','text':'Your posts'}],timeout=30)
        deadline=time.monotonic()+30
        while not self.chrome.call(VERIFICATION,{'op':'probe'}).get('googlePostRecordNames'):
            if time.monotonic()>=deadline:raise Hold('GOOGLE_INVENTORY_NOT_LOADED',retryable=True)
            time.sleep(.25)
        row=[{'selector':recipe['readback']['row_selector'],'contains':c['caption']}]
        # The atomic marker in the intact original upload document proves that
        # this job has never invoked Post. Inventory is an additional duplicate
        # check, not the basis for replaying an uncertain submission. A failed
        # More posts control cannot turn the same unclicked document into an
        # attempted submission. We explicitly record the limited inventory scope.
        if self.chrome.call(VERIFICATION,{'op':'exists','locator':row})['exists']:
            raise Hold('GOOGLE_POST_ALREADY_PRESENT','Reconcile the existing record instead')
        inventory_more_posts_present=self.chrome.call(VERIFICATION,{'op':'exists','locator':[{'selector':'button','name':'More posts'}]})['exists']
        inventory=self.chrome.call(VERIFICATION,{'op':'snapshot','fullDocument':True});after=check_document()
        previous=[e for e in store.ledger if e['kind']=='GOOGLE_UNATTEMPTED_SUBMISSION_RESUME_INTENT' and e['job_id']==job['id']]
        if len(previous)>1:raise Hold('UNATTEMPTED_SUBMISSION_PROOF_AMBIGUOUS')
        if previous:
            path=Path(previous[0]['evidence_path'])
            if digest(path.read_bytes())!=previous[0]['evidence_sha256']:raise Hold('EVIDENCE_CHANGED')
            old=read_json(path)
            if old['job_id']!=job['id'] or old['media_sha256']!=c['media_sha256'] or old['original_blob']!=prepared[kind]['src'] or old['prepared_evidence_sha256']!=digest(prepared_path.read_bytes()):raise Hold('ORIGINAL_UNATTEMPTED_DOCUMENT_NOT_PROVEN')
        else:
            path=self.directory/'evidence'/(job['id']+'-unattempted-document-resume.json')
            if path.exists():raise Hold('UNATTEMPTED_SUBMISSION_PROOF_REQUIRES_INSPECTION')
            intent=[e for e in store.ledger if e['kind']=='PUBLISH_INTENT' and e['job']['id']==job['id']]
            if len(intent)!=1:raise Hold('UNATTEMPTED_SUBMISSION_PROOF_AMBIGUOUS')
            atomic_json(path,{'utc':utc(),'job_id':job['id'],'profile_hash':c['profile_hash'],'media_sha256':c['media_sha256'],'original_blob':prepared[kind]['src'],'native_url':c['compose_url'],'original_publish_intent_sha256':intent[0]['sha256'],'intent_ledger_path':str(getattr(store,'ledger_path',self.directory/'intent-ledger.jsonl').resolve()),'verification_attempts_before_resume':job.get('verify_attempts',0),'prepared_evidence_path':str(prepared_path.resolve()),'prepared_evidence_sha256':digest(prepared_path.read_bytes()),'before':before,'after':after,'native_inventory':inventory,'loaded_inventory_caption_absent':True,'inventory_more_posts_control_present':inventory_more_posts_present,'inventory_scope':'Currently loaded native cards; no all-history absence claim','first_submission_basis':'Absent atomic Post marker in the intact original committed upload document, checked before and after independent inventory inspection'})
            store.event('GOOGLE_UNATTEMPTED_SUBMISSION_RESUME_INTENT',job_id=job['id'],evidence_path=str(path.resolve()),evidence_sha256=digest(path.read_bytes()))
        try:
            # The standard guarded submit sets the job marker before clicking.
            # Any later call in this document is consequently unable to click.
            self.workflow.submit(job);store.change(job['id'],'VERIFYING')
            return Engine(store,self.workflow,self.workflow.settings.policy).reconcile(job['id'])
        finally:store.export();store.backup()

    def correct_link_validation(self, store, job, rejection_path):
        """Bounded corrections of proven rejected forms; never reset intent."""
        from pathlib import Path
        from engine import Engine
        c=self.workflow.context(job);name=c['profile_id']
        if c['platform']!='google_business_profile' or not store.has_intent(job['id']) or job['state']!='OUTCOME_UNKNOWN':
            raise Hold('GOOGLE_VALIDATION_CORRECTION_NOT_ALLOWED')
        corrections=[e for e in store.ledger if e['kind']=='GOOGLE_VALIDATION_CORRECTION_INTENT' and e['job_id']==job['id']]
        if len(corrections)>=2:
            raise Hold('SUBMISSION_ALREADY_ATTEMPTED','The bounded correction limit was reached; reconcile only')
        path=Path(rejection_path).resolve();rejection=read_json(path)
        rejection_hash=digest(path.read_bytes())
        for previous in corrections:
            previous_path=Path(previous['evidence_path'])
            if digest(previous_path.read_bytes())!=previous['evidence_sha256']:
                raise Hold('EVIDENCE_CHANGED')
            if read_json(previous_path)['rejection_sha256']==rejection_hash:
                raise Hold('SUBMISSION_ALREADY_ATTEMPTED','This rejection was already corrected; reconcile only')
        if rejection.get('job_id')!=job['id'] or rejection.get('profile_hash')!=c['profile_hash'] or rejection.get('media_sha256')!=c['media_sha256'] or not link_validation_rejection(rejection.get('snapshot',{}),c):
            raise Hold('GOOGLE_VALIDATION_REJECTION_NOT_PROVEN')
        profile=self.workflow.settings.profile(name);recipe=self.workflow.settings.workflow(profile)
        binding,_=self.chrome.bound(name,mutation=True)
        if binding.get('job_id')!=job['id'] or binding['url']!=c['compose_url']:
            raise Hold('GOOGLE_VALIDATION_CORRECTION_CONTEXT_MISSING')
        live_rejection=self.chrome.call(name,{'op':'snapshot','fullDocument':True})
        if not link_validation_rejection(live_rejection,c):
            raise Hold('GOOGLE_VALIDATION_REJECTION_NOT_LIVE','The exact native link rejection must still be present before a correction')
        # Reload only the independent inventory, never the retained form.
        self.chrome.navigate(VERIFICATION,c['inventory_url'],job['id'],recovery=True)
        self.workflow.wait(VERIFICATION,[{'selector':'h1','text':'Your posts'}])
        inventory=self.chrome.call(VERIFICATION,{'op':'snapshot','fullDocument':True,'includeHTML':True})
        if norm(c['caption']) in norm(inventory.get('text','')) or norm(c['title']) in norm(inventory.get('text','')):
            raise Hold('GOOGLE_POST_ALREADY_PRESENT','Reconcile the existing native record instead')
        # Focusing the URL field initializes Google's controller. Separate Apple
        # events let it settle; moving focus back to the description commits blur.
        self.chrome.call(name,{'op':'assert','checks':[{'locator':[{'selector':'textarea[maxlength="1500"]'}],'text':c['caption']}]})
        for value in ['',c['purchase_url']]:
            self.chrome.call(name,{'op':'set_text','locator':[{'selector':'input[type=url]'}],'value':value,'focus':True,
                                  **({'method':'insert_text'} if value else {})})
        self.chrome.call(name,{'op':'set_text','locator':[{'selector':'textarea[maxlength="1500"]'}],'value':c['caption'],'focus':True})
        from workflow import render
        kind='video' if c.get('media_type')=='video/mp4' else 'photo'
        self.chrome.confirm_upload_preview(name,render(recipe['google_'+kind],c),c)
        guards=self.workflow.guards(recipe,c)+[{'locator':[{'selector':'input[type="url"][aria-invalid="false"]'}],'text':c['purchase_url']}]
        ready=self.chrome.call(name,{'op':'ready','job':job['id'],'mediaSha256':c['media_sha256'],'checks':guards,'submit':recipe['submit']})
        corrected=self.chrome.call(name,{'op':'snapshot','fullDocument':True,'includeHTML':True})
        proof={'utc':utc(),'job_id':job['id'],'rejection_path':str(path),'rejection_sha256':digest(path.read_bytes()),
               'live_rejection':live_rejection,'inventory_without_matching_post':inventory,'corrected_form':corrected,'ready':ready,
               'original_publish_intent_retained':True,'correction_number':len(corrections)+1,
               'max_corrections':2,'same_rejection_can_be_retried':False}
        proof_path=self.directory/'evidence'/(job['id']+'-google-validation-correction-'+str(len(corrections)+1)+'.json')
        atomic_json(proof_path,proof)
        store.event('GOOGLE_VALIDATION_CORRECTION_INTENT',job_id=job['id'],evidence_path=str(proof_path.resolve()),evidence_sha256=digest(proof_path.read_bytes()))
        try:
            self.chrome.call(name,{'op':'submit_google_validation_correction','job':job['id'],'mediaSha256':c['media_sha256'],
                                  'checks':guards,'submit':recipe['submit'],'purchaseURL':c['purchase_url'],
                                  'rejectionEvidenceSha256':digest(path.read_bytes())})
            return Engine(store,self.workflow,self.workflow.settings.policy).reconcile(job['id'])
        finally:
            store.export();store.backup()

    def verify(self, job, native_url=None):
        c = rejected_revision_context(self.workflow.context(job),self.directory)
        profile = self.workflow.settings.profile(c['profile_id'])
        recipe = self.workflow.settings.workflow(profile)
        retained=self.chrome.call(c['profile_id'],{'op':'snapshot','fullDocument':True})
        if link_validation_rejection(retained,c):
            rejected_path=self.directory/'evidence'/(job['id']+'-google-link-rejection.json')
            if not rejected_path.exists():
                atomic_json(rejected_path,{'utc':utc(),'job_id':job['id'],'profile_hash':c['profile_hash'],
                            'media_sha256':c['media_sha256'],'snapshot':retained})
            raise Hold('GOOGLE_LINK_VALIDATION_REJECTED','The native form rejected its Buy link; preserve the intent and inspect the saved rejection evidence')
        reader = VERIFICATION
        self.workflow.settings.check_url(profile, c['inventory_url'])
        # The independent reader may already show the pre-submission inventory.
        # Refresh that owned, clean page even when its URL is unchanged.
        self.chrome.navigate(reader, c['inventory_url'], job['id'], recovery=True)
        row = [{'selector': recipe['readback']['row_selector'], 'contains': c['caption']}]
        if c.get('native_revision_url'):
            post_id=c['native_revision_url'].rsplit('/',2)[1]
            row=[{'selector':recipe['readback']['row_selector']+':has(div[data-post-name="accounts/-/locations/'+c['location_id']+'/localPosts/'+post_id+'"])'}]
        resolution={}
        try:self.find_inventory_record(reader,row)
        except Hold as error:
            if error.code!='AMBIGUOUS_CONTROL' or c.get('native_revision_url'):raise
            post_id,resolution=self.resolve_caption_record(reader,c,recipe)
            row=[{'selector':recipe['readback']['row_selector']+':has(div[data-post-name="accounts/-/locations/'+c['location_id']+'/localPosts/'+post_id+'"])'}]
            self.find_inventory_record(reader,row)
        snapshot = self.chrome.call(reader, {'op': 'snapshot', 'scope': row, 'includeHTML': True})
        caption = self.chrome.call(reader, {'op': 'snapshot', 'scope': [{'selector': selector, 'within':row[0],**({} if c.get('native_revision_url') else {'text':c['caption']})} for selector in recipe['readback']['caption_selectors']]})
        c=observed_revision_context(c,caption['text'])
        status = self.chrome.call(reader, {'op': 'snapshot', 'scope': [{'selector': recipe['readback']['status_selector'], 'within':row[0]}]})
        atomic_json(self.directory/'evidence'/(job['id']+'-google-record.json'), {'utc': utc(), 'job_id': job['id'], 'snapshot': snapshot, 'caption': caption, 'status':status})
        identity = record_identity(snapshot, caption, status, c)
        editor_url = c['inventory_url']+'/'+identity['post_id']+'/edit'
        if c.get('native_revision_url') and editor_url!=c['native_revision_url']:
            raise Hold('GOOGLE_REJECTED_REVISION_WRONG_RECORD')
        self.workflow.settings.check_url(profile, editor_url)
        if native_url is not None and native_url != editor_url:
            raise Hold('NATIVE_PERMALINK_INVALID')
        # Full navigation is deliberate: the embedded manager's SPA links can
        # otherwise depend on a parent Google Search frame that is not present.
        self.chrome.navigate(reader, editor_url, job['id'], recovery=True)
        self.workflow.wait(reader, [{'selector': 'textarea[maxlength="1500"]'}], timeout=30)
        kind='video' if c.get('media_type')=='video/mp4' else 'photo'
        from workflow import render
        photo = self.chrome.confirm_upload_preview(reader, render(recipe['google_'+kind],c), c)
        detail = self.chrome.call(reader, {'op': 'snapshot', 'fullDocument': True})
        checked = saved_details(detail, photo, c)
        prepared_path = self.directory/'evidence'/(job['id']+'-google-'+kind+'.json')
        prepared = read_json(prepared_path)
        if prepared.get('job_id') != job['id'] or prepared.get('media_sha256') != c['media_sha256'] or prepared.get('profile_hash') != c['profile_hash']:
            raise Hold('GOOGLE_PREPARED_'+kind.upper()+'_RECEIPT_MISSING')
        evidence = {'job_id': job['id'], 'profile_hash': c['profile_hash'], 'verified_utc': utc(),
                    'url': editor_url, 'native_record': identity, 'caption_verified': True,
                    'author_verified': True, 'photo_verified': kind=='photo', 'video_verified':kind=='video',
                    'account_verification_method': 'exact managed Google Business Profile location and native post IDs',
                    'account_name': c['account_name'], 'published_inventory': snapshot,
                    'published_caption': caption, 'published_status':status, 'saved_post': detail,
                    kind: checked[kind], 'purchase_links': checked['purchase_links'],
                    'prepared_'+kind+'_evidence_path': str(prepared_path.resolve()),
                    'prepared_'+kind+'_evidence_sha256': digest(prepared_path.read_bytes()),
                    **({'caption_revision_applied':c['caption_revision_applied']} if 'caption_revision_applied' in c else {}),**resolution}
        # This form was inspected without changing any field. It is safe to
        # navigate the read-only inspection tab back to its native inventory.
        try:
            self.chrome.navigate(reader, c['inventory_url'], job['id'], recovery=True)
            self.chrome.checkpoint(reader, 0, dirty=False)
        except Hold as error:
            evidence['inspection_warning'] = str(error)
        # A standalone Google composer can retain its values after publishing.
        # Only release a retained form after the independent published record
        # matches those exact values; unexpected user edits stay protected.
        try:
            self.chrome.sync_after_submit(c['profile_id'])
            current = self.chrome.call(c['profile_id'], {'op': 'snapshot', 'fullDocument': True})
            fields = [e for e in current.get('editors', []) if e.get('tag') == 'TEXTAREA']
            if fields:
                if len(fields) != 1 or norm(fields[0].get('value')) != norm(c['caption']):
                    raise Hold('DRAFT_NEEDS_INSPECTION')
                self.chrome.call(c['profile_id'], {'op': 'assert', 'checks': [{'locator': [{'selector': 'input[type=url]'}], 'text': c['purchase_url']}]})
            self.chrome.checkpoint(c['profile_id'], 0, dirty=False)
            self.chrome.navigate(c['profile_id'], c['inventory_url'], job['id'], recovery=True)
        except Hold as error:
            evidence['composer_warning'] = str(error)
        path = self.directory/'evidence'/(job['id']+'-native-'+digest(evidence)[:12]+'.json')
        atomic_json(path, evidence)
        return {'native_url': editor_url, 'native_url_kind': 'Google Business Profile published post record',
                'google_location_id': identity['location_id'], 'google_post_id': identity['post_id'],
                'google_status': identity['status'], 'caption_verified': True, 'author_verified': True,
                'photo_verified': kind=='photo', 'video_verified':kind=='video', 'media_sha256': c['media_sha256'],
                'purchase_links': checked['purchase_links'], 'verified_utc': evidence['verified_utc'],
                'evidence_path': str(path.resolve()), 'evidence_sha256': digest(path.read_bytes()),
                **({k:c[k] for k in ['caption_revision_evidence_path','caption_revision_evidence_sha256']} if c.get('caption_revision_evidence_path') else {}),
                **({'effective_caption':c['caption'],'caption_revision_applied':c['caption_revision_applied']} if c.get('caption_revision_evidence_path') else {}),**resolution}
