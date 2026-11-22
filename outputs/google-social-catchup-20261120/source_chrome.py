"""A read-only source browser: only owned navigation and page scrolling mutate UI."""
from urllib.parse import urlparse
from chrome import Chrome,READONLY
from google_fast import GoogleFastChrome
from common import Hold

class SourceChrome(GoogleFastChrome):
    def google_target(self,binding):
        p=urlparse(binding['url'])
        return p.scheme=='https' and p.hostname in {'www.facebook.com','www.instagram.com','business.facebook.com'}

    def call(self,name,request):
        if request['op'] not in READONLY|{'claim','navigate','scroll_page'}:
            raise Hold('SOURCE_READER_READ_ONLY')
        if request['op']=='scroll_page':
            return Chrome.call(self,name,request)
        if self.bindings.get(name,{}).get('pending_url'):
            self.bound(name,mutation=False)
        return super().call(name,request)
