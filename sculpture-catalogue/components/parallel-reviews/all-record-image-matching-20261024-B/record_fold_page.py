"""Store B's disjoint manual Fold Unfold visual-role review, never shared index."""
import argparse,hashlib,json
from datetime import datetime,timezone
from pathlib import Path
H=Path(__file__).resolve().parent
P=H.parents[3]/'reports/dropbox-wall-complete-role-review-20261024T214349Z/families/fold-unfold'
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
a=argparse.ArgumentParser();a.add_argument('--page',type=int,required=True);a.add_argument('--roles',required=True);a.add_argument('--notes',default='{}');a.add_argument('--flags',default='{}');a.add_argument('--secondary-installation',default='');args=a.parse_args()
board=next(b for b in read(P/'contact-board-index.json') if b['page']==args.page)
rows={r['review_index']:r for r in read(P/'indexed-current-images-and-links.json')}
codes=args.roles.split();assert len(codes)==len(board['indices'])
roles={'I':'individual','D':'detail','R':'rear','T':'installation','G':'group_context','U':'uncertain'}
notes=json.loads(args.notes);flags=json.loads(args.flags);secondary={int(x) for x in args.secondary_installation.split(',') if x}
f=H/'fold-unfold-manual-decisions.json';d=read(f) if f.exists() else {}
for index,code in zip(board['indices'],codes):
    r=rows[index];s=r['visual_source'];assert sha(s['source_image_path'])==s['actual_visual_source_sha256']
    d[str(index)]={'index':index,'file_id':r['file_id'],'page':args.page,'visual_role':roles[code],
        'secondary_installation':index in secondary,'note':notes.get(str(index),''),'flags':flags.get(str(index),[]),
        'board':board['path'],'board_sha256':sha(board['path']),'source_image_path':s['source_image_path'],
        'source_image_sha256':s['actual_visual_source_sha256'],'reviewed_utc':datetime.now(timezone.utc).isoformat(),
        'reviewer_thread_id':'01a13fe6-495b-7253-b923-31823b4cbca8'}
f.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'page':args.page,'records':len(codes),'reviewed_total':len(d)}))
