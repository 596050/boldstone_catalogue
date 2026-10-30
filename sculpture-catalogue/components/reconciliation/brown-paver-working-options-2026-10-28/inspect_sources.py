from common import *
from xml.etree import ElementTree as E
import re
for kind in ['core_workbook','comprehensive_workbook']:
    b=Book(manifest['sources'][kind]['snapshot'])
    names=['Master Catalogue','Specifications','Components','Photo Coverage','Missing Pictures'] if kind=='core_workbook' else ['Wall Sculptures','Products','Specifications','Components','Overview']
    print(kind)
    for sn in names:
        cells,links=b.sheet(sn); rows=sorted({int(re.search(r'\d+',a)[0]) for a in cells}); last=rows[-1]
        info={'sheet':sn,'last':last,'last_row':{a:v for a,v in cells.items() if int(re.search(r'\d+',a)[0])==last},'top':{a:v for a,v in cells.items() if int(re.search(r'\d+',a)[0])<=6}}
        sp=b.sheets[sn];rp=str(Path(sp).parent/'_rels'/(Path(sp).name+'.rels'))
        info['tables']=[]
        if rp in b.zip.namelist():
            for r in E.fromstring(b.zip.read(rp)):
                if r.get('Type').endswith('/table'):
                    t=E.fromstring(b.zip.read(native.resolve(sp,r.get('Target'))));info['tables'].append([t.get('name'),t.get('ref')])
        print(json.dumps(info,ensure_ascii=False))
    b.close()
