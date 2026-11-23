"""Preparation-only background Chrome helpers. No publication entry point."""
import sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'social-publisher'))
from settings import Settings
from chrome import Chrome
from common import digest
OUT=Path(__file__).resolve().parent
class DraftSettings:
 def __init__(self):
  self.original=Settings()
  self.profiles={**self.original.profiles,'boldstone_threads':{'platform':'threads','channel_key':'threads:boldstonesculpture','account_name':'boldstonesculpture','allowed_hosts':['www.threads.com','www.threads.net'],'compose_url':'https://www.threads.com/','inventory_url':'https://www.threads.com/@boldstonesculpture'}}
  self.policy=self.original.policy
 def check_current(self): self.original.check_current()
 def profile(self,name): self.check_current();return self.profiles[name]
 def fingerprint(self,name): return digest(self.profiles[name]) if name=='boldstone_threads' else self.original.fingerprint(name)
 def workflow(self,profile): return self.original.workflow(profile)
def browser(key):return Chrome(DraftSettings(),OUT/'tabs'/key)
if __name__=='__main__':
 key=sys.argv[1];c=browser(key)
 if sys.argv[2]=='bind': print(json.dumps(c.bind(sys.argv[3],int(sys.argv[4]),int(sys.argv[5]))))
 elif sys.argv[2]=='call':
  req=json.loads(sys.argv[4]);assert req['op'] not in ('submit','submit_google_rejected_revision','submit_google_validation_correction')
  print(json.dumps(c.call(sys.argv[3],req),ensure_ascii=False))
 elif sys.argv[2]=='navigate': print(json.dumps(c.navigate(sys.argv[3],sys.argv[4])))
