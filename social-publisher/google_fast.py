"""Google preparation with one native audit call; Post uses the standard bridge."""
import json,os,subprocess,tempfile
from urllib.parse import urlparse
from chrome import Chrome,READONLY
from common import ROOT,Hold,canonical,utc

PREPARATION={'claim','begin_job','navigate','set_text','set_checked','click','upload_begin','upload_chunk',
             'upload_finish','upload_commit','probe_svg_photo','ready'}

class GoogleFastChrome(Chrome):
    def google_target(self,binding):
        parsed=urlparse(binding['url'])
        return parsed.scheme=='https' and parsed.hostname=='www.google.com' and any(
            p.get('platform')=='google_business_profile' and parsed.path.startswith(p['business_path'])
            for p in self.settings.profiles.values())

    @staticmethod
    def foreground(stamp,binding):
        return (stamp['frontmost']=='com.google.Chrome' and stamp['front_window_id']==binding['window_id'] and
                stamp['active_tabs'].get(str(binding['window_id']))==binding['tab_id'])

    def call(self,name,request):
        self.settings.check_current()
        binding=self.bindings.get(name)
        if not binding or not self.google_target(binding) or request['op'] not in READONLY|PREPARATION:
            return super().call(name,request)
        self.settings.check_url(self.profile(name),binding['url'])
        # The standard inspect bridge independently checks the actual window's
        # normal mode and exact URL. Repeating tab-state before it adds no guard.
        if request['op'] in READONLY:
            return self.evaluate(binding,request,readonly=True)
        fd,path=tempfile.mkstemp(prefix='.google-dom-',suffix='.js',dir=str(self.directory))
        try:
            with os.fdopen(fd,'w',encoding='utf-8') as stream:
                stream.write(self.driver+'('+canonical({'expectedURL':binding['url'],'owner':binding['owner'],**request})+')')
            try:
                process=self.execute(['/usr/bin/osascript',str(ROOT/'google-fast.applescript'),str(binding['window_id']),
                                      str(binding['tab_id']),binding['url'],path],capture_output=True,text=True,timeout=8,check=False)
            except subprocess.TimeoutExpired:
                raise Hold('APPLE_EVENT_TIMEOUT','The background preparation operation timed out',retryable=True)
            if process.returncode:
                detail=process.stderr.strip()[-1200:]
                for code in ['TAB_NAVIGATED_EXTERNALLY','FOREGROUND_TAB_PAUSED','NORMAL_PROFILE_REQUIRED','CHROME_NOT_RUNNING']:
                    if code in detail:raise Hold(code,detail)
                raise Hold('APPLE_EVENT_REFUSED',detail,retryable=True)
            try:
                envelope=json.loads(process.stdout);result=json.loads(envelope['result_json'])
                before,after=envelope['before'],envelope['after']
                for stamp in [before,after]:
                    if not (isinstance(stamp['frontmost'],str) and isinstance(stamp['tab_url'],str)):
                        raise ValueError('Incomplete native target stamp')
                    stamp['front_window_id']=int(stamp['front_window_id'])
                    stamp['active_tabs']={key:int(value) for key,value in stamp['active_tabs'].items()}
                    if str(binding['window_id']) not in stamp['active_tabs']:raise ValueError('Missing exact target window ID')
            except (ValueError,KeyError,TypeError):
                raise Hold('DOM_RESPONSE_INVALID','The native preparation audit was incomplete',retryable=True)
            audit={'utc':utc(),'profile_id':name,'operation':request['op'],'before':before,'after':after,
                   'unchanged':before==after,'target_remained_background':not self.foreground(after,binding),
                   'transport':'Google target-scoped native preparation audit'}
            with (self.directory/'focus-audit.jsonl').open('a',encoding='utf-8') as stream:stream.write(canonical(audit)+'\n')
            if self.foreground(after,binding):raise Hold('FOCUS_CHANGED_PAUSED','The target became foreground; its owned draft is retained')
            if not result.get('ok'):
                code=result.get('code','DOM_ERROR')
                raise Hold(code,result.get('detail',code),retryable=code in {'CONTROL_MISSING','PHOTO_NOT_LOADED','VIDEO_NOT_LOADED','SUBMIT_DISABLED','CONTROL_DISABLED','NATIVE_CAPTION_MISMATCH','NATIVE_PHOTO_MISMATCH'})
            return result
        finally:
            os.unlink(path)
