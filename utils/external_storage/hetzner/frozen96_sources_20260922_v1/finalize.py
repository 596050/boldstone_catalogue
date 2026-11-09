"""Accurate source-scope reporting and immutable delivery evidence."""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
ORIGINAL=ROOT/'research/candidates/directional_forecasting/full_history_shadow_vote_hybrid_20260922_v2'
OUT=ORIGINAL/'refresh_20260922_v1'


def read(p):return json.loads(Path(p).read_text())
def ref(p):
    p=Path(p).resolve()
    return dict(path=str(p),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
def write(p,v):Path(p).write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')


def repair():
    if (OUT/'SOURCE_SCOPE_REPAIR.json').exists():return
    assert read(OUT/'REFRESH_SCOPE.json')['status']=='CURRENT_DAILY_REFERENCE_REPLAY_COMPLETE'
    files=['EVALUATION.json','FIT_STATUS.json','ANALYSIS_FREEZE.json']
    old={}
    for name in files:
        p=OUT/name;q=OUT/(p.stem+'_AS_EMITTED.json')
        assert not q.exists();q.write_bytes(p.read_bytes());old[name]=ref(q)
    before=read(OUT/'EVALUATION.json');after=copy.deepcopy(before)
    after['scope']='2011-01-03 through 2026-09-21 refreshed daily snapshot; hypothetical GBP rule transport. Current daily horizon complete; native minute cash and full native acceptance remain incomplete.'
    assert {k:v for k,v in before.items() if k!='scope'}=={k:v for k,v in after.items() if k!='scope'}
    write(OUT/'EVALUATION.json',after)
    status=read(OUT/'FIT_STATUS.json')
    status.update(status='COMPLETE_CURRENT_DAILY_REFERENCE',full_test_complete=False,
                  reason='Current daily reference replay complete through pinned 2026-09-21 cutoff. Native minute event prices/accounting and native catalogue evidence remain unresolved.')
    write(OUT/'FIT_STATUS.json',status)
    freeze=read(OUT/'ANALYSIS_FREEZE.json')
    freeze.update(evaluation=ref(OUT/'EVALUATION.json'),
                  reporting_repair='Only inherited stale-tail wording repaired after verifying every metric and model result unchanged; original emitted metadata retained in SOURCE_SCOPE_REPAIR.json.')
    write(OUT/'ANALYSIS_FREEZE.json',freeze)
    write(OUT/'SOURCE_SCOPE_REPAIR.json',dict(at_utc=datetime.now(timezone.utc).isoformat(),code=ref(__file__),
          original_emitted_files=old,changed_fields=['EVALUATION.scope','FIT_STATUS.status','FIT_STATUS.reason','ANALYSIS_FREEZE.evaluation'],
          metrics_or_predictions_changed=False,reason='Reused original evaluator had static September 11 stale-tail boilerplate; this new run has all six requested daily sessions.'))


def report():
    archive=read(HERE/'ARCHIVE.json');updated=read(HERE/'UPDATED_ARCHIVE.json')
    assert archive['status']==updated['status']=='VERIFIED'
    assert read(HERE/'RESULT_READBACK.json')['status']=='PASS'
    assert read(HERE/'ORIGINAL_TRACE_READBACK.json')['status']=='PASS'
    assert read(OUT/'CAUSAL_VERIFICATION.json')['status']=='PASS'
    repair()
    result=read(OUT/'EVALUATION.json');models=result['models'];stats=read(OUT/'STATISTICS.json')
    contrast=read(OUT/'CONTRASTS.json');manifest=read(HERE/'SOURCE_MANIFEST.json');refresh=read(HERE/'REFRESH.json')
    selected=[]
    for parent in ['base','crash']:
        selected.append(next(r for r in contrast if r['candidate']==parent+'_HGC_POOL' and r['control']==parent and r['cost_bps']==20))
    binding=read(HERE/'SOURCE_BINDING.json')
    binding.update(historical_snapshot_id=archive['snapshot_id'],update_snapshot_id=updated['snapshot_id'],
                   historical_readback=ref(HERE/'REMOTE_READBACK.json'),updated_readback=ref(HERE/'UPDATED_REMOTE_READBACK.json'))
    write(HERE/'SOURCE_BINDING.json',binding)
    lines=['# Original hybrid source refresh and Hetzner copy','',
      'The 96-stock source copy and parallel IQFeed refresh are verified. **Neither original hybrid achieved adjusted statistical confirmation.**','',
      'The pinned cutoff is 21 September 2026, the latest completed session when acquisition started. All 96 daily histories were refreshed in full and all 96 minute tails were downloaded concurrently with four workers. The six new sessions are September 14, 15, 16, 17, 18 and 21. The source update contains 679,293 daily rows and 326,564 minute-tail rows; raw inconsistent observations remain retained.', '',
      '## Storage','',f"Existing encrypted Restic repository: `{manifest['repository']}`.",
      f"Repository ID: `{manifest['repository_id']}`.",'',
      f"- Original sources: **526 files / {manifest['source_bytes']:,} bytes**: 96 daily files and 430 overlapping raw-minute components. Snapshot `{archive['snapshot_id']}`; group `{manifest['group']}`.",
      f"- Refresh: **96 daily files, 96 minute tails, one historical SLB probe**, plus receipts and VIX context. Snapshot `{updated['snapshot_id']}`; group `{updated['group']}`.",
      f"- Full remote content readback passed for all {archive['readback_files']} historical/provenance files and {updated['readback_files']} refresh/receipt files. Every file was decrypted and SHA256-compared with its bound source hash.",
      '- No Toshiba source was deleted or overwritten. Updates are separate, immutable source versions in Hetzner, with a bounded local staging copy used for this replay. Existing source directories remain bound to their original vintage.',
      '- [Source binding](SOURCE_BINDING.json), [historical readback](REMOTE_READBACK.json), [refresh readback](UPDATED_REMOTE_READBACK.json), [acquisition receipt](REFRESH.json).','',
      'The snapshots retain the original absolute source paths. Use the existing storage utility to list or restore a group; restore to a separate destination with sufficient free space:','',
      '```sh',
      'python3 utils/external_storage/hetzner/storage_box.py --profile market-data snapshots --group frozen96-original-hybrid-sources-20260922',
      'python3 utils/external_storage/hetzner/storage_box.py --profile market-data snapshots --group frozen96-iqfeed-update-20260922',
      '```','',
      '## Refreshed original comparison','',
      'The daily study now covers **2011-01-03–2026-09-21, 3,952 sessions**. Original algorithms, expert policies, matched controls, GBP capital and 0/20/40 bp costs are unchanged. All 14 model books and all 31 common metric rows, annual and stock-level breakdowns are retained. These remain hypothetical daily GBP rule-transport results; native broker execution and point-in-time evidence are not established.','',
      '| Hybrid versus its own parent, 20 bp per leg | Additional net profit | Fewer losing sessions | Adjusted profit p |',
      '| --- | ---: | ---: | ---: |']
    for label,row in zip(['Carry96 HGC_POOL','Crash90 HGC_POOL'],selected):
        stat=next(r for r in stats if r['id']==row['id']+'_net')
        lines.append(f"| {label} | £{row['profit_gain']:,.2f} | {row['fewer_losses']} | {stat['signflip_p_research_adjusted']:.2f} |")
    lines += ['', 'A negative fewer-losses count means more losing sessions. Carry96 hybrid requires £21,707.92 under the 40 bp capital proxy, exceeding the retained £21,195.51 limit. Crash90 hybrid remains within that proxy limit. Neither passes the original joint improvement criterion or the full 50% objective.','',
              '| Model | Long direction accuracy | Short direction accuracy |', '| --- | ---: | ---: |']
    for name,label in [('base','Carry96 parent'),('base_HGC_POOL','Carry96 hybrid'),('crash','Crash90 parent'),('crash_HGC_POOL','Crash90 hybrid')]:
        m=models[name]['metrics'];a=m['long_accuracy'];b=m['short_accuracy']
        lines.append(f"| {label} | {100*a['value']:.4f}% ({a['numerator']}/{a['denominator']}) | {100*b['value']:.4f}% ({b['numerator']}/{b['denominator']}) |")
    lines += ['', 'Direction accuracy uses the original next-close direction contract, with zero moves counted as non-wins; it is distinct from costed profitability. The short Crash90 denominator is only 94. These accuracy differences are point estimates, not adjusted statistical confirmations.','',
      'The 84 original profit/loss comparisons were retained. The known family was extended from 42,180 to 42,264 slots before fitting; the wider research family remains unclosed. Both year-bootstrap and exact year-sign-flip adjusted p-values for the primary comparisons are 1.00. Under the retained 16-year/100,000-draw design, the minimum achievable adjusted sign-flip p is 1.00 and the bootstrap minimum is 0.4226. Six sessions inside 2026 do not add independent year clusters. This is a limit of this declared confirmation procedure, not a claim that improved trading is impossible. [Resolution audit](INFERENCE_RESOLUTION.json).','',
      '## Verification and remaining minute gap','',
      'The first 3,946 daily input sessions and the earlier VIX bytes match the original source. Action and holding prefixes match all 14 original books across 3,945 pre-terminal sessions; the old final liquidation session is horizon-dependent. All six causal checks pass. Separate result readback checked scalar long/short direction counts, 42 costed cash totals, 42 paired contrasts and all 84 exact tests using all 65,536 sign assignments.','',
      'The direct IQFeed SLB request for 2008-11-28–2008-12-10 returned 230 rows, all on November 28 and December 10: **zero on December 1**. Thus the original required event-day minute price is still unavailable. Native funding/account/corporate-action inputs also remain unresolved. No completed 2007-onward native minute cash comparison or statistical confirmation is claimed. [Minute refresh coverage](MINUTE_REFRESH_COVERAGE.json).','',
      f"[Updated 31-metric table]({OUT}/ALL31_METRICS.csv) · [Statistical tests]({OUT}/STATISTICS.json) · [Full-scope comparison summary]({OUT}/COMPARISON_SUMMARY.json) · [Independent result readback](RESULT_READBACK.json)", '']
    (HERE/'README.md').write_text('\n'.join(lines))
    (OUT/'REPORT.md').write_text('# Refreshed original hybrid comparison\n\n'+f'[Complete report and source-copy evidence]({HERE}/README.md).\n\nNeither original hybrid achieved adjusted statistical confirmation. Daily coverage now ends 2026-09-21 (3,952 sessions); the native minute comparison remains blocked by the SLB event-day gap and unresolved accounting inputs.\n')
    artifacts=[ref(p) for p in sorted(HERE.glob('*.json')) if p.name!='DELIVERY.json']
    artifacts += [ref(p) for p in sorted(OUT.glob('*.json'))]
    write(HERE/'DELIVERY.json',dict(at_utc=datetime.now(timezone.utc).isoformat(),status='COPY_AND_REFRESH_VERIFIED_RETEST_UNCONFIRMED',
          repository_id=manifest['repository_id'],historical_snapshot_id=archive['snapshot_id'],update_snapshot_id=updated['snapshot_id'],
          copied_original_source_files=manifest['source_file_count'],copied_original_source_bytes=manifest['source_bytes'],
          refreshed_daily_symbols=96,refreshed_minute_symbols=96,cutoff=refresh['plan']['end'],daily_sessions=3952,
          adjusted_statistical_confirmation=False,native_minute_cash_complete=False,source_deletions=0,
          code=ref(__file__),report=ref(HERE/'README.md'),primary_comparisons=selected,artifacts=artifacts))
    print('Verified source delivery and unconfirmed research report published')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('operation',choices=['repair','report']);args=p.parse_args()
    dict(repair=repair,report=report)[args.operation]()
