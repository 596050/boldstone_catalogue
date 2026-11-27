"""Close only idle task-owned reader tabs; keep all ten prepared composers."""
from pathlib import Path
import json,sys,subprocess
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1];sys.path.insert(0,str(ROOT/'social-publisher'))
from chrome import Chrome
from settings import Settings
from common import atomic_json,read_json,utc
c=Chrome(Settings(),ROOT/'social-publisher/state');rows=[]
owned={r['tab_id'] for r in read_json(OUT/'reserved-tab-plan.json')['tabs'][:4]}
for name,statepath in [('sally_linkedin',ROOT/'social-publisher/state'),('boldstone_google_business_profile',ROOT/'social-publisher/state'),('boldstone_threads',OUT/'browser-state')]:
 reader=Chrome(Settings(),statepath);binding=reader.bindings[name];tid=binding['tab_id'];assert tid in owned
 result={'profile_id':name,'tab_id':tid,'window_id':binding['window_id']}
 try:
  b,before=reader.bound(name,mutation=True);w,tab=reader.find(before,b['window_id'],tid)
  assert w['active_tab_id']!=tid and not b.get('dirty')
  snap=reader.call(name,{'op':'snapshot','fullDocument':True})
  assert not any((e.get('value') or e.get('text','')).strip() for e in snap['editors'])
  assert not any(i['value'] not in {'','on'} for i in snap['inputs'])
  script='''on run argv
tell application "Google Chrome"
set w to window id ((item 1 of argv) as integer)
set t to tab id ((item 2 of argv) as integer) of w
if mode of w is not "normal" then error "NORMAL_PROFILE_REQUIRED"
if ((id of active tab of w) as integer) is ((item 2 of argv) as integer) then error "SELECTED_TAB_RETAINED"
if URL of t is not item 3 of argv then error "TAB_NAVIGATED_EXTERNALLY"
close t
end tell
end run
'''
  process=subprocess.run(['/usr/bin/osascript','-',str(b['window_id']),str(tid),b['url']],input=script,capture_output=True,text=True,check=True,timeout=8)
  after=c.inventory();assert not any(t['tab_id']==tid for w in after['windows'] for t in w['tabs'])
  result.update(state='CLOSED_IDLE_READER',before=reader.focus_stamp(before),after=reader.focus_stamp(after))
 except Exception as error:result.update(state='RETAINED',reason=str(error))
 finally:reader.close()
 rows.append(result)
plan=read_json(OUT/'draft-tab-ids.json');inventory=c.inventory();current={t['tab_id']:t for w in inventory['windows'] for t in w['tabs']}
for r in plan['bindings']:
 assert r['tab_id'] in current and 'Draft' in current[r['tab_id']]['title']
atomic_json(OUT/'reader-cleanup.json',{'utc':utc(),'readers':rows,'prepared_tabs_retained':len(plan['bindings']),'draft_titles':[current[r['tab_id']]['title'] for r in plan['bindings']]});print(json.dumps({'readers':[{k:r.get(k) for k in ['profile_id','state','reason']} for r in rows],'prepared_tabs_retained':10},ensure_ascii=False));c.close()
