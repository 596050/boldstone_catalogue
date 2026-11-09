"""Independent readback of refreshed directions, cash contrasts and exact tests."""
from itertools import product
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
from threadpoolctl import threadpool_limits

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
OUT=ROOT/'research/candidates/directional_forecasting/full_history_shadow_vote_hybrid_20260922_v2/refresh_20260922_v1'


def main():
    result=json.loads((OUT/'EVALUATION.json').read_text())
    prepared=json.loads((OUT/'SOURCE_PREFLIGHT.json').read_text())
    with np.load(prepared['inputs']['path']) as z:
        close=z['values'][:,:,3];days=z['days']
    year=np.array([str(d)[:4] for d in days]);unique=sorted(set(year))
    signs=np.asarray(list(product([-1.,1.],repeat=len(unique))))
    books={};direction=[]
    for name,r in result['models'].items():
        p=Path(r['ledger']['path'])
        assert hashlib.sha256(p.read_bytes()).hexdigest()==r['ledger']['sha256']
        with np.load(p) as z:
            target=z['target'];books[name]={cost:z[f'net_pnl_{cost}bp__values'] for cost in (0,20,40)}
            for key,side in [('direction_accuracy',None),('long_accuracy',1),('short_accuracy',-1)]:
                good=total=missing=0
                for t in range(len(days)-1):
                    for j in range(close.shape[1]):
                        vote=float(np.sign(target[t,j]))
                        if vote==0 or side is not None and vote!=side:continue
                        a,b=float(close[t,j]),float(close[t+1,j])
                        if not (np.isfinite(a) and np.isfinite(b) and a>0 and b>0):
                            missing+=1;continue
                        total+=1
                        good+=int(b>a if vote>0 else b<a)
                metric=r['metrics'][key]
                if missing:
                    assert metric['value'] is None
                else:
                    assert metric['numerator']==good and metric['denominator']==total
                    np.testing.assert_allclose(metric['value'],good/total,rtol=0,atol=1e-14)
                direction.append(dict(model=name,metric=key,correct=good,denominator=total,missing=missing))
            for cost in (0,20,40):
                cash=books[name][cost]
                np.testing.assert_allclose(sum(map(float,cash)),r['metrics'][f'net_pnl_{cost}bp']['value'],rtol=1e-12,atol=1e-8)
                assert sum(float(x)<0 for x in cash)==r['session_counts'][str(cost)]['losing']
    stats={r['id']:r for r in json.loads((OUT/'STATISTICS.json').read_text())}
    family=json.loads((OUT/'STATISTICAL_DESIGN.json').read_text())['family_size']
    contrasts=json.loads((OUT/'CONTRASTS.json').read_text())
    for c in contrasts:
        a=books[c['candidate']][c['cost_bps']];b=books[c['control']][c['cost_bps']]
        np.testing.assert_allclose(sum(map(float,a-b)),c['profit_gain'],rtol=1e-12,atol=1e-8)
        assert sum(float(x)<0 for x in b)-sum(float(x)<0 for x in a)==c['fewer_losses']
        for metric,loss in [('net',b-a),('loss_count',(a<0).astype(float)-(b<0).astype(float))]:
            row=stats[c['id']+'_'+metric]
            sums=np.asarray([sum(map(float,loss[year==y])) for y in unique])
            threshold=abs(sum(map(float,sums)));tol=1e-12*max(1,threshold)
            p=float(np.mean(np.abs(signs@sums)>=threshold-tol))
            assert p==row['signflip_p']
            for key in ('bootstrap_p','signflip_p'):
                assert row[key+'_research_adjusted']==min(1,row[key]*family)
    value=dict(status='PASS',models=len(books),sessions=len(days),direction_checks=direction,
               cash_totals_and_losing_counts_checked=len(books)*3,paired_contrasts=len(contrasts),
               exact_signflip_tests=len(stats),full_sign_assignments_per_test=len(signs),
               family_lower_bound=family,independent_market_observations=0,
               qualification='Separate process, scalar direction/cash counts and exhaustive two-sided sign enumeration; same historical observations')
    (HERE/'RESULT_READBACK.json').write_text(json.dumps(value,indent=2)+'\n')
    print(json.dumps({k:v for k,v in value.items() if k!='direction_checks'},indent=2))


if __name__=='__main__':
    with threadpool_limits(limits=1):main()
