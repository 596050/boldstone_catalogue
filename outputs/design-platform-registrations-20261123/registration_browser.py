"""Prepare account forms in explicitly owned background tabs, never submit them."""
from pathlib import Path
import json, sys
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'social-publisher'))
from common import atomic_json,read_json,digest,utc,Hold
from chrome import Chrome

class RegistrationSettings:
    def __init__(self):
        self.path=OUT/'registration-config.json'
        self.data=read_json(self.path);self.sha=digest(self.data);self.profiles=self.data['profiles']
    def check_current(self):
        assert digest(read_json(self.path))==self.sha
    def profile(self,name):
        self.check_current();return self.profiles[name]
    def fingerprint(self,name):return digest(self.profile(name))
    @staticmethod
    def check_url(profile,url,allow_blank=False):
        from settings import Settings
        from urllib.parse import urlsplit
        parsed=urlsplit(url)
        # This task explicitly prepares this site's visible login form. The
        # publisher's general login-route hold remains unchanged everywhere else.
        if parsed.scheme=='https' and parsed.hostname=='www.architonic.com' and parsed.path=='/en/login':
            return Settings.check_url(profile,'https://www.architonic.com/',allow_blank=allow_blank)
        Settings.check_url(profile,url,allow_blank=allow_blank)

class RegistrationChrome(Chrome):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        original='const sensitiveRoute = () => /\\/(checkpoint|challenge|login|accounts\\/login|authwall)(\\/|$)/.test(location.pathname);'
        permitted='const sensitiveRoute = () => /\\/(checkpoint|challenge|login|accounts\\/login|authwall)(\\/|$)/.test(location.pathname) && !(location.origin==="https://www.architonic.com" && location.pathname==="/en/login");'
        assert original in self.driver
        self.driver=self.driver.replace(original,permitted,1)
        fields='textarea,input[type="text"],input[type="search"],input[type="url"],input:not([type])'
        assert fields in self.driver
        self.driver=self.driver.replace(fields,fields+',input[type="email"]',1)
    def bound(self,name,mutation=False):
        self.settings.check_current()
        if name not in self.bindings:raise Hold('RESERVED_TAB_NOT_BOUND')
        b=self.bindings[name];state=self.state_for(b);w,tab=self.find(state,b['window_id'],b['tab_id'])
        if tab['url']!=b['url']:
            if b.get('pending_url')!=tab['url']:raise Hold('TAB_NAVIGATED_EXTERNALLY')
            b['url']=tab['url'];b.pop('pending_url',None);self.save_bindings()
        self.settings.check_url(self.profile(name),tab['url'],allow_blank=True)
        if mutation and self.target_foreground(state,b):raise Hold('FOREGROUND_TAB_PAUSED')
        return b,state
    def call(self,name,request):
        if request['op'] in {'submit','submit_google_validation_correction','submit_google_rejected_revision','upload_begin','upload_chunk','upload_commit'}:
            raise Hold('ACCOUNT_FINAL_ACTION_RESERVED_FOR_USER')
        return super().call(name,request)

def browser():return RegistrationChrome(RegistrationSettings(),OUT/'browser-state')

if __name__=='__main__':
    c=browser();action=sys.argv[1]
    if action=='init':
        inventory=c.inventory();tabs={'archilovers':962003168,'archiproducts':962003171,'architonic':962003174}
        before=c.focus_stamp(inventory)
        for name,tid in tabs.items():
            matches=[(w,t) for w in inventory['windows'] for t in w['tabs'] if t['tab_id']==tid]
            assert len(matches)==1
            w,t=matches[0];assert t['url']=='about:blank'
            c.bind(name,w['window_id'],tid)
            c.navigate(name,c.settings.profile(name)['start_url'])
            snap=c.call(name,{'op':'snapshot','fullDocument':True,'includeHTML':True})
            atomic_json(OUT/(name+'-initial.json'),{'utc':utc(),'snapshot':snap})
            print(json.dumps({'platform':name,'tab_id':tid,'url':snap['url'],'text':snap.get('text','')[:7000],'controls':snap.get('controls',[])[:35]},ensure_ascii=False),flush=True)
        atomic_json(OUT/'initial-focus-check.json',{'utc':utc(),'before':before,'after':c.focus_stamp(c.inventory())})
    elif action=='inspect':
        name=sys.argv[2];snap=c.call(name,{'op':'snapshot','fullDocument':True,'includeHTML':True});atomic_json(OUT/(name+'-current.json'),{'utc':utc(),'snapshot':snap});print(json.dumps(snap,ensure_ascii=False))
    else:raise ValueError(action)
