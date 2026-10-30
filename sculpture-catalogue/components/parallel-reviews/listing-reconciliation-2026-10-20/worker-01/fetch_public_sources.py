import json,hashlib,datetime,urllib.request,urllib.error,urllib.parse
from pathlib import Path

OUT=Path(__file__).parent
RAW=OUT/'raw-public';RAW.mkdir(exist_ok=True)
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def fetch(url,label):
 receipt={'url':url,'method':'GET','request_utc':now(),'authentication':'none','cookies_supplied':False,'timeout_seconds':25}
 try:
  request=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; Boldstone catalogue evidence review)','Accept':'application/json'})
  with urllib.request.urlopen(request,timeout=25) as response:
   body=response.read();receipt.update(status=response.status,final_url=response.url,headers=dict(response.headers))
 except urllib.error.HTTPError as e:
  body=e.read();receipt.update(status=e.code,final_url=e.url,headers=dict(e.headers),error=str(e))
 except Exception as e:
  body=b'';receipt.update(status=None,error_type=type(e).__name__,error=str(e))
 file=RAW/(label+'.body');file.write_bytes(body)
 receipt.update(response_utc=now(),body_path=str(file),bytes=len(body),sha256=hashlib.sha256(body).hexdigest())
 try:
  value=json.loads(body);receipt.update(json_parse_success=True,json_type=type(value).__name__,json_keys=list(value) if isinstance(value,dict) else None)
 except Exception as e:
  value=None;receipt.update(json_parse_success=False,json_parse_error=type(e).__name__)
 (RAW/(label+'.receipt.json')).write_text(json.dumps(receipt,indent=2)+'\n')
 return value,receipt

def collection_pages():
 first=RAW/'collection-initial.body'
 if first.is_file():
  data=json.load(open(first));receipt=json.load(open(RAW/'collection-initial.receipt.json'))
 else:data,receipt=fetch('https://boldstonesculpture.com/buy?format=json','collection-initial')
 pages=[];seen=set();number=0
 while True:
  page={'page_index':number,'url':receipt['url'],'receipt_path':str(RAW/('collection-initial.receipt.json' if number==0 else f'collection-page-{number:02}.receipt.json')),
   'body_path':receipt['body_path'],'body_sha256':receipt['sha256'],'http_status':receipt.get('status')}
  if not isinstance(data,dict):page['error']='JSON_OBJECT_NOT_RETURNED';pages.append(page);break
  page.update(item_count=len(data.get('items',[])),item_ids=[x.get('id') for x in data.get('items',[])],pagination=data.get('pagination'),collection_claimed_item_count=data.get('collection',{}).get('itemCount'))
  pages.append(page)
  pagination=data.get('pagination') or {}
  if not pagination.get('nextPage'):break
  next_url=urllib.parse.urljoin('https://boldstonesculpture.com',pagination.get('nextPageUrl',''))
  parsed=urllib.parse.urlparse(next_url)
  if parsed.scheme!='https' or parsed.netloc!='boldstonesculpture.com':page['error']='NEXT_LINK_OUTSIDE_AUTHORIZED_PUBLIC_DOMAIN';break
  query=urllib.parse.parse_qsl(parsed.query,keep_blank_values=True)
  query=[(k,v) for k,v in query if k!='format']+[('format','json')]
  next_url=urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(query)))
  if next_url in seen:page['error']='PAGINATION_LOOP';break
  seen.add(next_url);number+=1
  if number>20:page['error']='BOUNDED_SAFETY_LIMIT';break
  data,receipt=fetch(next_url,f'collection-page-{number:02}')
 result={'schema':'boldstone.squarespace-public-pagination-receipt.v1','created_utc':now(),'source':'official anonymous public collection JSON',
  'pages':pages,'terminal_next_page_false':bool(pages and pages[-1].get('pagination') is not None and pages[-1]['pagination'].get('nextPage') is False),
  'terminal_has_no_next_page_link':bool(pages and pages[-1].get('pagination') is not None and not pages[-1]['pagination'].get('nextPage') and not pages[-1]['pagination'].get('nextPageUrl')),
  'duplicate_item_ids':sorted({x for p in pages for x in p.get('item_ids',[]) if sum(q.get('item_ids',[]).count(x) for q in pages)>1}),
  'received_item_count':sum(x.get('item_count',0) for x in pages),'unique_item_count':len({i for p in pages for i in p.get('item_ids',[])}),
  'account_authenticated':False,'hidden_drafts_or_entire_account_completeness_claimed':False,'remote_writes':0}
 (OUT/'PUBLIC_PAGINATION.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({k:v for k,v in result.items() if k!='pages'},indent=2))
 return result

if __name__=='__main__':collection_pages()
