"""Replay the unchanged original hybrids on a separately retained source vintage.

Reuses original fit, controls, execution, all 31 metrics and causal checks. Only
source references and output locations are rebound. This is an exposed-history
source refresh, never an independent confirmation sample or parameter search.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
import numpy as np
from threadpoolctl import threadpool_limits
from research.candidates.directional_forecasting.full_history_shadow_vote_hybrid_20260922_v2 import source, evaluation, analysis
from research.testing_stages.stage_01_data.frozen_refresh import daily_panel
from research.testing_stages.models import Panel

ORIGINAL = source.HERE
OUT = ORIGINAL / 'refresh_20260922_v1'
LOCAL = ROOT / 'utils/offload_network/.source-state/full_history_shadow_vote_hybrid_20260922_v2_refresh_20260922_v1'
STAGING = ROOT / 'utils/offload_network/.source-state/frozen96_iqfeed_refresh_20260922_v1'
VIX_FREEZE = ROOT / 'research/candidates/directional_forecasting/parent_session_loss_warning_20260919_v2/run_02/FREEZE.json'
old_read = source.read
old_ref = source.ref


def read_bound(path):
    path = Path(path)
    if path == VIX_FREEZE:
        prior = old_read(path)
        return {**prior, 'sources': {**prior['sources'], 'vix': source.ref(STAGING / 'context/VIX_History.csv')}}
    if path == ORIGINAL / 'STATISTICAL_DESIGN.json':
        return old_read(OUT / 'STATISTICAL_DESIGN.json')
    return old_read(path)


def analysis_ref(path):
    if Path(path) == ORIGINAL / 'STATISTICAL_DESIGN.json':
        return old_ref(OUT / 'STATISTICAL_DESIGN.json')
    return old_ref(path)


def setup():
    plan = old_read(HERE / 'REFRESH_PLAN.json')
    config = dict(old_read(ORIGINAL / 'CONFIG.json'), required_end=plan['end'], available_snapshot_end=plan['end'])
    source.LOCAL = LOCAL
    evaluation.OUT = analysis.OUT = OUT
    evaluation.LOCAL = analysis.LOCAL = LOCAL
    evaluation.CONFIG = analysis.CONFIG = config
    evaluation.read = analysis.read = read_bound
    analysis.ref = analysis_ref
    return plan, config


def prepare():
    plan, config = setup()
    refresh = old_read(HERE / 'REFRESH.json')
    daily = [r for r in refresh['entries'] if r['kind'] == 'daily']
    assert len(daily) == 96 and all(r['status'] == 'UPDATED' for r in daily), 'Incomplete daily source refresh'
    for r in daily:
        source.verify(r)
    assert {r['symbol'] for r in daily} == set(plan['symbols'])
    vix_receipt = old_read(HERE / 'VIX_RECEIPT.json'); source.verify(vix_receipt)
    # Verify inherited implementation/dependency identity before any new fit.
    original_freeze = old_read(ORIGINAL / 'run_01/FIT_FREEZE.json')
    for r in original_freeze['dependencies']:
        source.verify(r)
    OUT.mkdir(exist_ok=False); LOCAL.mkdir(parents=True, exist_ok=False)
    design = old_read(ORIGINAL / 'STATISTICAL_DESIGN.json')
    # Preserve the original family and reserve this repeated 84-test look.
    # This remains a lower bound, not a claim that wider research is closed.
    prior_family_path = ORIGINAL.parent / 'hybrid_direction_cash_gate_20260922_v1/CONFIG.json'
    inherited = max(design['family_size'], old_read(prior_family_path)['statistics']['family_lower_bound'])
    design.update(family_size=inherited + design['tests'],
                  inherited_family_size=inherited, inherited_family_reference=source.ref(prior_family_path), additional_refresh_look=design['tests'],
                  prespecification='Original hypotheses and algorithms retained; source refresh look reserved before new outcomes',
                  independent_confirmation=False, wider_research_family='NOT_CLOSED')
    source.write(OUT / 'STATISTICAL_DESIGN.json', design)
    source.write(OUT / 'RETEST_DESIGN.json', dict(at_utc=source.now(), runner=source.ref(__file__),
        original_config=source.ref(ORIGINAL / 'CONFIG.json'), config=config,
        original_fit=source.ref(ORIGINAL / 'run_01/FIT_FREEZE.json'),
        acquisition=source.ref(HERE / 'REFRESH.json'), vix_acquisition=source.ref(HERE / 'VIX_RECEIPT.json'),
        change='Source vintage only: full IQFeed daily refresh and the same official Cboe VIX source; unchanged algorithm, expert policies, controls, costs and capital',
        rule_application={'L09':'Same original dependencies and causal prefix/mutation checks; source changes separately reported',
                          'L10':'Same all31 metrics and unchanged full objective; missing native minute inputs remain unavailable',
                          'L12':'Old history remains exposed; copies and repeated replay add no independent observations'},
        matched_control='Both unchanged frozen parents and original H/G/C/HG/C_TWO_SLOT controls',
        meaningful_effect=config['meaningful_effect'], falsifier=config['falsifier'],
        independent_confirmation=False, original_evidence_overwritten=False))
    raw, bindings = daily_panel(dict(feature_symbols=plan['symbols'], daily_directory=str(STAGING / 'daily'), execution_resources={'source_workers':1}), plan['end'])
    start = raw.days.index('2011-01-03')
    panel = Panel(raw.days[start:], raw.symbols, raw.values[start:].copy(), raw.close_times_et[start:])
    scorer, geometry, targets = source.parents(panel)
    checks = source.audit_parents(panel, scorer, geometry, targets)
    old_inputs = old_read(ORIGINAL / 'run_01/SOURCE_PREFLIGHT.json')['daily_available']['inputs']
    source.verify(old_inputs)
    with np.load(old_inputs['path']) as z:
        assert np.array_equal(z['symbols'], panel.symbols)
        assert np.array_equal(z['days'], panel.days[:len(z['days'])])
        old_values=z['values']; new_values=panel.values[:len(old_values)]
        same=(old_values==new_values)|(np.isnan(old_values)&np.isnan(new_values))
        drift=dict(overlap_sessions=len(old_values), revised_value_cells=int((~same).sum()),
                   overlap_exact=bool(same.all()), additional_sessions=len(panel.days)-len(old_values),
                   additional_dates=list(panel.days[len(old_values):]))
    p=LOCAL / 'daily_current_INPUTS.npz'
    np.savez_compressed(p,days=panel.days,symbols=panel.symbols,values=panel.values,**targets)
    prepared=dict(start=panel.days[0],end=panel.days[-1],sessions=len(panel.days),symbols=len(panel.symbols),
                  inputs=source.ref(p),parents=checks,daily_raw=[dict(path=k,sha256=v) for k,v in bindings.items()],
                  source_revision=drift,scope='CURRENT_VINTAGE_HYPOTHETICAL_DAILY_GBP_RULE_TRANSPORT')
    source.write(OUT / 'SOURCE_PREFLIGHT.json', prepared)
    print(json.dumps(dict(stage='PREFLIGHT',sources=len(bindings),**drift,
                         parents={k:v['status'] for k,v in checks.items()})),flush=True)


def fit():
    setup(); p=old_read(OUT / 'SOURCE_PREFLIGHT.json')
    assert all(v['status']=='PASS' for v in p['parents'].values()), 'Required parent cash marks absent'
    for r in p['daily_raw']:
        source.verify(r)
    evaluation.daily_experiment(p)
    # Retain the original runner's detailed outputs; accurately qualify this new
    # run in its own additional record rather than changing historical evidence.
    source.write(OUT / 'REFRESH_SCOPE.json',dict(status='CURRENT_DAILY_REFERENCE_REPLAY_COMPLETE',
                 period=[p['start'],p['end']],sessions=p['sessions'],new_sessions=p['source_revision']['additional_sessions'],
                 original_algorithm_unchanged=True,source_vintage_changed=True,independent_confirmation=False,
                 native_minute_cash_complete=False,full_native_acceptance=False))


def analyse():
    setup(); analysis.main()


if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['prepare','fit','analyse']);args=p.parse_args()
    with threadpool_limits(limits=1):
        dict(prepare=prepare,fit=fit,analyse=analyse)[args.stage]()
