"""Compare saved rendered galleries with the exact current selected-photo manifest.

Uses small public CDN renditions in memory. Never changes a product or keeps an
original image copy. Matching is rendered-image evidence, not original-byte identity.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
import hashlib
import itertools
import json
import random
import sys
import threading
import urllib.request
import urllib.error
from PIL import Image, ImageChops, ImageDraw, ImageOps, ImageStat

OUT=Path(__file__).parent;PACKET=OUT.parent
load=lambda p:json.loads(Path(p).read_text())
RENDERED_CACHE={}
CACHE_LOCK=threading.Lock()


def assignment(cost):
    """Minimum-cost one-to-one assignment, O(n cubed), with no numeric dependency."""
    n=len(cost)
    assert all(len(r)==n for r in cost)
    u,v,p,way=[0.]*(n+1),[0.]*(n+1),[0]*(n+1),[0]*(n+1)
    for i in range(1,n+1):
        p[0]=i;j0=0;minimum=[float('inf')]*(n+1);used=[False]*(n+1)
        while True:
            used[j0]=True;i0=p[j0];delta=float('inf');j1=0
            for j in range(1,n+1):
                if used[j]:continue
                current=cost[i0-1][j-1]-u[i0]-v[j]
                if current<minimum[j]:minimum[j]=current;way[j]=j0
                if minimum[j]<delta:delta=minimum[j];j1=j
            for j in range(n+1):
                if used[j]:u[p[j]]+=delta;v[j]-=delta
                else:minimum[j]-=delta
            j0=j1
            if not p[j0]:break
        while True:
            j1=way[j0];p[j0]=p[j1];j0=j1
            if not j0:break
    result=[None]*n
    for j in range(1,n+1):result[p[j]-1]=j-1
    return result


def verify_assignment():
    rng=random.Random(20261108)
    for n in range(1,7):
        for _ in range(4):
            cost=[[rng.randrange(100) for _ in range(n)] for _ in range(n)]
            chosen=assignment(cost)
            actual=sum(cost[i][chosen[i]] for i in range(n))
            exact=min(sum(cost[i][order[i]] for i in range(n)) for order in itertools.permutations(range(n)))
            assert actual==exact


def source_thumb(url):
    parts=urlsplit(url)
    assert parts.scheme=='https' and parts.hostname=='images.squarespace-cdn.com'
    query=dict(parse_qsl(parts.query));query['format']='300w'
    return urlunsplit((parts.scheme,parts.netloc,parts.path,urlencode(query),parts.fragment))


def fetch(item):
    with CACHE_LOCK:
        cached=RENDERED_CACHE.get(item['url'])
    if cached is not None:
        return {**cached,**item,'bytes_read':0,'rendition_reused_in_memory':True}
    request=urllib.request.Request(item['url'],headers={'User-Agent':'BoldstoneCatalogueImageAudit/1.0'})
    try:
        with urllib.request.urlopen(request,timeout=45) as response:
            assert response.headers.get_content_type().startswith('image/')
            body=response.read(4_000_001)
            assert len(body)<=4_000_000,'Unexpectedly large rendition; stop rather than retain originals'
    except urllib.error.HTTPError as exc:
        # The native editor was independently observed falling back from AVIF to
        # same-stem JPEG on new uploads. Follow only that one observed fallback.
        if (exc.code==404 and item['kind']=='native' and item['url'].endswith('.avif')):
            observed_fallback=load(OUT/'native-jpeg-fallback-observed.json')
            assert observed_fallback['before']=='_S.avif' and observed_fallback['after']=='_S.jpg'
            return fetch({**item,'url':item['url'][:-5]+'.jpg',
                          'native_initial_avif_url':item['url'],
                          'fallback_basis':'native-jpeg-fallback-observed.json'})
        raise RuntimeError(f"Rendition unavailable: {item['kind']} {item['key']} {exc.code} {item['url']}") from exc
    im=ImageOps.exif_transpose(Image.open(BytesIO(body)));im.load()
    white=Image.new('RGB',im.size,'white')
    if im.mode=='RGBA':white.paste(im,mask=im.getchannel('A'))
    else:white.paste(im.convert('RGB'))
    normalized=white.resize((96,96),Image.Resampling.LANCZOS)
    thumb=white.copy();thumb.thumbnail((140,140))
    result={**item,'normalized':normalized,'thumb':thumb,'bytes_read':len(body),
            'response_sha256':hashlib.sha256(body).hexdigest(),'dimensions':list(im.size),
            'rendition_reused_in_memory':False}
    with CACHE_LOCK:
        RENDERED_CACHE[item['url']]=result
    return result


def distance(a,b):
    return sum(ImageStat.Stat(ImageChops.difference(a['normalized'],b['normalized'])).mean)/3


def run(sku):
    native=load(OUT/(sku+'.json'))
    plan=load(PACKET/'brandboom-restore-plan.json')
    product=next(p for p in plan['records'] if p['sku']==sku)
    assert native['image_count']==len(native['images'])
    urls=load(PACKET/'current-public-images-verified.json')
    observed=load(OUT/'native-image-url-observed.json')['url']
    assert observed=='https://d3k2yxl6efztlc.cloudfront.net/presentation/000347063570B5C6_M.avif'
    base=observed.rsplit('/',1)[0]+'/'
    inputs=[dict(kind='expected',key=i,url=source_thumb(urls[i]['url'])) for i in product['image_ids']]
    inputs += [dict(kind='native',key=i['native_media_id'],url=base+i['native_stem']+'_M.'+i.get('native_extension','avif')) for i in native['images']]
    with ThreadPoolExecutor(max_workers=3) as pool:images=list(pool.map(fetch,inputs))
    expected=[r for r in images if r['kind']=='expected'];actual=[r for r in images if r['kind']=='native']
    costs=[[distance(a,b) for b in expected] for a in actual]
    n=max(len(actual),len(expected))
    padded=[row+[0.]*(n-len(expected)) for row in costs]+[[0.]*n for _ in range(n-len(actual))]
    chosen=assignment(padded)[:len(actual)]
    comparisons=[];canvas=Image.new('RGB',(720,180*len(actual)),'white');draw=ImageDraw.Draw(canvas)
    for row,(a,col) in enumerate(zip(actual,chosen)):
        scores=sorted((c,i) for i,c in enumerate(costs[row]));best,runner=scores[0],scores[1] if len(scores)>1 else (float('inf'),None)
        assigned=col<len(expected)
        display_col=col if assigned else best[1]
        comparisons.append(dict(native_media_id=a['key'],assigned_source_id=expected[col]['key'] if assigned else None,
            native_rendition_url=a['url'],native_response_sha256=a['response_sha256'],
            native_format_fallback_used='native_initial_avif_url' in a,
            mean_absolute_pixel_difference=round(costs[row][display_col],6),best_source_id=expected[best[1]]['key'],
            runner_up_difference=round(runner[0],6) if runner[1] is not None else None,
            exact_order_matches=col==row))
        y=row*180;canvas.paste(a['thumb'],(10,y+25));canvas.paste(expected[display_col]['thumb'],(200,y+25))
        draw.text((10,y+5),'Native '+a['key'],fill='black');draw.text((200,y+5),('Selected ' if assigned else 'EXTRA; closest ')+expected[display_col]['key'][-12:],fill='black')
        draw.text((365,y+45),'Rendered mean difference: '+str(round(costs[row][display_col],4)),fill='black')
    canvas.save(OUT/(sku+'-contact.jpg'),quality=86)
    worst=max(costs[i][j] for i,j in enumerate(chosen) if j<len(expected))
    result=dict(checked_at=datetime.now(timezone.utc).isoformat(),
        status=('REVIEW_GALLERY_COUNT_MISMATCH' if len(actual)!=len(expected) else
                'REVIEW_RENDERED_MATCHES' if worst>2.0 else 'RENDERED_CANDIDATES_WITHIN_BOUND_FOR_VISUAL_REVIEW'),
        sku=sku,catalogue_id=product['catalogue_id'],expected_count=len(expected),native_count=len(actual),
        primary_assignment_matches=chosen[0]==0,all_order_matches=all(i==j for i,j in enumerate(chosen)),
        primary_expected_pixel_difference=round(costs[0][0],6),
        unassigned_native_media_ids=[actual[i]['key'] for i,j in enumerate(chosen) if j>=len(expected)],
        missing_selected_source_ids=[expected[j]['key'] for j in range(len(expected)) if j not in chosen],
        worst_mean_absolute_pixel_difference=round(worst,6),comparisons=comparisons,
        network_bytes_read=sum(r['bytes_read'] for r in images),original_copies_retained=0,
        qualification='One-to-one comparison of small public rendered renditions. This is comparative photo evidence; original byte identities, product publication and account approvals are separate. Review the contact sheet before accepting uncertain matches.',
        source_rendition_specification='https://developers.squarespace.com/commerce-apis/v2/products',
        native_endpoint_basis='CDN directory and M rendition naming observed through Chrome Open Image in New Tab and native gallery previews. Native stems are read from saved thumbnails. Only the independently observed AVIF-to-JPEG fallback is followed.',
        source_manifest_sha256=hashlib.sha256((PACKET/'brandboom-restore-plan.json').read_bytes()).hexdigest())
    (OUT/(sku+'-comparison.json')).write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    verify_assignment()
    if sys.argv[1:]==['--repaired']:
        skus=[row['sku'] for row in load(OUT/'repair-intent.json')['duplicate_associations']]
    elif sys.argv[1:] in (['--available'],['--all-inventoried']):
        products=load(PACKET/'brandboom-restore-plan.json')['records']
        skus=[p['sku'] for p in products
              if (OUT/(p['sku']+'.json')).is_file()
              and (sys.argv[1:] == ['--all-inventoried'] or not (OUT/(p['sku']+'-comparison.json')).exists())]
    else:
        skus=sys.argv[1:]
    for sku in skus:
        result=run(sku)
        print(json.dumps({k:v for k,v in result.items() if k!='comparisons'}),flush=True)
