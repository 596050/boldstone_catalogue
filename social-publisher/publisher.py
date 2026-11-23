#!/usr/bin/env python3
"""Background social publishing via AppleScript and the signed-in Chrome app."""
import argparse
import contextlib
import fcntl
import html
import json
import os
import shutil
import sqlite3
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

from chrome import VERIFICATION
from google_fast import GoogleFastChrome as Chrome
from common import ROOT, Hold, atomic_json, canonical, digest, read_json, sync_directory, utc
from engine import Engine
from journal import Store
from settings import Settings
from workflow import Workflow
from upload_bridge import UploadClient, UploadServer, build_helper


def concise(report):
    return {'utc': report['utc'], 'complete': report['complete'], 'counts': report['counts'], 'run_results': report.get('run_results'),
            **({'requested_job':report['requested_job']} if report.get('requested_job') else {}),
            'jobs': [{'id': r['id'], 'title': r['payload']['title'], 'profile_id': r['payload']['profile_id'],
                      'state': r['state'], 'attempts': r['attempts'], 'last_error': r['last_error'],
                      'native_url': (r['receipt'] or {}).get('native_url')} for r in report['jobs']]}


def report_html(directory, report):
    rows = []
    for job in report['jobs']:
        receipt = job['receipt'] or {}
        url = receipt.get('native_url')
        link = '<a href="' + html.escape(url, quote=True) + '">Open post</a>' if url else 'Pending'
        rows.append('<tr><td>' + html.escape(job['payload']['title']) + '</td><td>' + html.escape(job['payload']['profile_id']) +
                    '</td><td>' + html.escape(job['state']) + '</td><td>' + link + '</td><td>' + html.escape(job['last_error'] or '') + '</td></tr>')
    page = '<!doctype html><html lang="en"><meta charset="utf-8"><title>Boldstone publisher status</title><style>body{font:16px/1.5 system-ui;margin:40px;max-width:1400px}td,th{padding:12px;text-align:left;border-bottom:1px solid #ddd}a{color:#245e71}</style><h1>Boldstone publisher</h1><p>' + html.escape(report['utc']) + '</p><table><thead><tr><th>Post</th><th>Profile</th><th>State</th><th>Native receipt</th><th>Attention</th></tr></thead><tbody>' + ''.join(rows) + '</tbody></table></html>'
    (directory / 'status.html').write_text(page, encoding='utf-8')


def doctor(settings, chrome, directory, probe=False):
    before = chrome.inventory()
    candidates = []
    hosts = {h for p in settings.profiles.values() for h in p['allowed_hosts']}
    for window in before['windows']:
        if window['mode'] != 'normal':
            continue
        for tab in window['tabs']:
            if tab['url'] != 'about:blank' and urlparse(tab['url']).hostname not in hosts:
                continue
            row = {'window_id': window['window_id'], 'tab_id': tab['tab_id'], 'url': tab['url'],
                   'bound_profiles': [name for name, b in chrome.bindings.items() if b['window_id'] == window['window_id'] and b['tab_id'] == tab['tab_id']]}
            if probe:
                try:
                    binding = {'window_id': window['window_id'], 'tab_id': tab['tab_id'], 'url': tab['url'], 'owner': 'readonly-doctor'}
                    row['probe'] = chrome.evaluate(binding, {'op': 'probe'}, readonly=True)
                except Hold as error:
                    row['hold'] = {'code': error.code, 'detail': str(error)}
            candidates.append(row)
    after = chrome.inventory()
    report = {'utc': utc(), 'chrome_running': before['chrome_running'], 'chrome_version': before.get('chrome_version'),
              'transport': 'public Chrome AppleScript, existing normal browser instance',
              'focus_before_after_unchanged': Chrome.focus_stamp(before) == Chrome.focus_stamp(after),
              'reserved_profile_bindings': sorted(chrome.bindings), 'required_profiles': sorted(list(settings.profiles) + [VERIFICATION]),
              'social_tabs': candidates, 'live_publishing_test': 'NOT_RUN',
              'transport_probe_ok': any(row.get('probe', {}).get('ok') for row in candidates) if probe else None,
              'ready_for_batch': False, 'batch_readiness': 'REQUIRES_MANIFEST_AND_NATIVE_READY_GUARDS',
              'next_step': 'Reserve one background tab per profile and bind its window/tab IDs. Inspect and calibrate exact controls before the first live batch.'}
    atomic_json(directory / 'health.json', report)
    return report


def history(settings, store, source):
    source = Path(source).resolve()
    posts = read_json(source / 'posts.json')
    if not isinstance(posts, list):
        raise Hold('HISTORY_SCHEMA')
    inserted = 0
    by_platform = {p['platform']: name for name, p in settings.profiles.items()}
    for platform, profile_id in by_platform.items():
        file = source / (platform + '-publication-receipts.json')
        if not file.exists():
            continue
        receipts = {r['catalogue_id']: r for r in read_json(file)}
        profile = settings.profile(profile_id)
        recipe = settings.workflow(profile)
        for p in posts:
            r = receipts.get(p['catalogue_id'])
            if not r:
                continue
            if r.get('status') != 'PUBLISHED_NATIVE_READBACK' or not (r.get('full_caption_readback') or r.get('full_product_text_readback')):
                raise Hold('HISTORY_NOT_VERIFIED', p['title'])
            import re
            if not re.fullmatch(recipe['native_url_pattern'], r['url']):
                raise Hold('HISTORY_PERMALINK', r['url'])
            caption = p['captions'][platform]
            channel = profile['channel_key']
            payload = {'batch_id': source.name, 'post_key': p['catalogue_id'], 'title': p['title'],
                       'catalogue_id': p['catalogue_id'], 'sku': p['sku'], 'caption': caption,
                       'media_path': p['media_path'], 'media_sha256': p['sha256'], 'alt_text': p['alt_text'],
                       'profile_id': profile_id, 'profile_hash': settings.fingerprint(profile_id),
                       'platform': platform, 'channel_key': channel, 'source_history': str(source)}
            job = {'id': digest([channel, p['catalogue_id']])[:32], 'channel_key': channel, 'post_key': p['catalogue_id'],
                   'content_hash': digest({'caption': caption, 'media_sha256': p['sha256']}), 'payload': payload}
            receipt = {'native_url': r['url'], 'source': str(file), 'source_sha256': digest(file.read_bytes()),
                       'verified_utc': r.get('verified_utc'), 'imported_utc': utc(),
                       'verification': 'Imported durable native-readback receipt; not freshly republished or reverified'}
            inserted += store.import_history(job, receipt)
    store.backup()
    return {'historical_deliveries_imported': inserted, 'source': str(source)}


def restore(directory, backup):
    """Explicit backup restoration preserves the independent intent ledger."""
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    source = Path(backup).resolve()
    destination = directory / 'outbox.sqlite3'
    if source == destination.resolve() or not source.is_file():
        raise Hold('RESTORE_SOURCE_INVALID')
    with (directory / 'runner.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Hold('RUNNER_ALREADY_ACTIVE')
        with sqlite3.connect('file:' + str(source) + '?mode=ro', uri=True) as check:
            if check.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                raise Hold('BACKUP_INTEGRITY')
            if not check.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='jobs'").fetchone():
                raise Hold('BACKUP_SCHEMA')
        temporary = directory / '.restore.tmp'
        shutil.copyfile(source, temporary)
        if destination.exists():
            shutil.copyfile(destination, directory / ('outbox-before-restore-' + str(time.time_ns()) + '.sqlite3'))
        with temporary.open('rb') as stream:
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
        sync_directory(directory)
    with Store(directory) as store:
        report = store.export()  # independent ledger replays uncertain intents
        store.backup()
    return {'restored_from': str(source), 'counts_after_intent_recovery': report['counts']}


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--state', type=Path, default=ROOT / 'state', help='Keep this directory, including its intent ledger, through recovery')
    p.add_argument('--config', type=Path, default=ROOT / 'profiles.json')
    sub = p.add_subparsers(dest='command', required=True)
    d = sub.add_parser('doctor', help='Read-only account/browser/transport check; never creates or navigates tabs')
    d.add_argument('--probe', action='store_true')
    b = sub.add_parser('bind', help='Explicitly reserve an existing background tab for one platform profile')
    b.add_argument('--profile', required=True)
    b.add_argument('--window', type=int, required=True)
    b.add_argument('--tab', type=int, required=True)
    i = sub.add_parser('inspect', help='Capture the public DOM of a reserved platform tab for workflow calibration')
    i.add_argument('--profile', required=True)
    for name in ['validate', 'enqueue']:
        s = sub.add_parser(name)
        s.add_argument('manifest', type=Path)
    r = sub.add_parser('run', help='Run due jobs once; uncertain submissions are reconciliation-only')
    r.add_argument('--job')
    r.add_argument('--prepare-only', action='store_true', help='Prepare the supplied manifest in reserved tabs without enqueueing or publishing')
    r.add_argument('--manifest', type=Path)
    r.add_argument('--tabs', type=Path)
    prepare = sub.add_parser('prepare', help='Prepare retained drafts only; accepts publish_authorized=false and never enqueues or publishes')
    prepare.add_argument('manifest', type=Path)
    prepare.add_argument('--tabs', type=Path, required=True, help='JSON mapping each profile/post_key to a separate reserved background tab')
    prepare.add_argument('--profile')
    prepare.add_argument('--post-key')
    w = sub.add_parser('watch', help='Explicit foreground-free worker; Ctrl-C stops it without losing intent state')
    w.add_argument('--cycles', type=int, default=0, help='0 runs until stopped')
    sub.add_parser('status')
    helper = sub.add_parser('helper-build', help='Prepare the reviewable Chrome photo helper; does not install it')
    helper.add_argument('--port', type=int, default=8768)
    sub.add_parser('helper-status', help='Read local helper health; never opens Chrome or starts publishing')
    sub.add_parser('helper-serve', help='Serve the authenticated upload queue on loopback; Ctrl-C stops it')
    h = sub.add_parser('import-history', help='Seed duplicate guards from verified historical batch receipts')
    h.add_argument('directory', type=Path)
    c = sub.add_parser('reconcile', help='Check the exact native post after an uncertain submission; never clicks Publish')
    c.add_argument('--job', required=True)
    c.add_argument('--url', required=True)
    correction=sub.add_parser('repair-google-link-validation',help='Correct one proven client-side Google link rejection without resetting its original intent')
    correction.add_argument('--job',required=True)
    correction.add_argument('--rejection-evidence',type=Path,required=True)
    unattempted=sub.add_parser('resume-google-unattempted',help='Finish a first Post only in its intact original upload document with no submission marker or native record')
    unattempted.add_argument('--job',required=True)
    public=sub.add_parser('reconcile-google-public',help='Read the exact Google public post and decode its native media; never submits')
    public.add_argument('--job',required=True)
    public.add_argument('--post-id',required=True)
    public.add_argument('--context',type=Path,required=True)
    public.add_argument('--evidence-state',type=Path,help='Original prepared media evidence directory, if separate from the outbox')
    for name in ['resume', 'adopt-profile-change']:
        s = sub.add_parser(name)
        s.add_argument('--job', required=True)
    rec = sub.add_parser('recover-db', help='Restore a verified SQLite backup while retaining and replaying the intent ledger')
    rec.add_argument('--backup', type=Path, required=True)
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    if args.command == 'run':
        if args.prepare_only and (not args.manifest or not args.tabs or args.job):
            raise Hold('PREPARATION_ARGUMENTS','Use run --prepare-only --manifest FILE --tabs FILE, or the prepare command')
        if not args.prepare_only and (args.manifest or args.tabs):
            raise Hold('PREPARATION_ARGUMENTS','--manifest and --tabs require --prepare-only')
    directory = args.state.expanduser().resolve()
    if args.command == 'helper-build':
        if not 1024 <= args.port <= 65535:
            raise Hold('UPLOAD_HELPER_PORT_INVALID')
        return build_helper(directory, args.port), 0
    if args.command == 'helper-status':
        client = UploadClient(directory)
        try:
            return {'health': client.health(), 'publish_clicks': 0}, 0
        except OSError:
            return {'status': 'LOCAL_BRIDGE_NOT_RUNNING', 'publish_clicks': 0}, 2
    if args.command == 'helper-serve':
        with UploadServer(directory) as server:
            print(canonical({'status': 'SERVING_UPLOAD_QUEUE', 'bind': '127.0.0.1', 'port': server.port, 'publish_actions': False}), flush=True)
            while True:
                time.sleep(1)
    settings = Settings(args.config)
    chrome = Chrome(settings, directory)
    if args.command == 'validate':
        jobs = settings.jobs(args.manifest)
        return {'valid': True, 'deliveries': len(jobs), 'publish_clicks': 0}, 0
    if args.command == 'recover-db':
        return restore(directory, args.backup), 0
    if args.command == 'watch':
        count = 0
        while True:
            settings = Settings(args.config)
            chrome = Chrome(settings, directory)
            with Store(directory) as store:
                report = Engine(store, Workflow(settings, chrome, directory), settings.policy).run()
                report_html(directory, report)
            print(canonical({'utc': utc(), 'counts': report['counts']}), flush=True)
            count += 1
            if (args.cycles and count >= args.cycles) or report['complete']:
                return concise(report), 0 if report['complete'] else 2
            time.sleep(min(60, max(1, settings.policy['watch_interval_seconds'])))
    # Commands share the same process lock, including binding and diagnostics.
    with Store(directory) as store:
        workflow = Workflow(settings, chrome, directory)
        if args.command == 'prepare' or (args.command == 'run' and args.prepare_only):
            from preparation import prepare_manifest
            result=prepare_manifest(settings,store,directory,args.manifest,args.tabs,
                                    profile=getattr(args,'profile',None),post_key=getattr(args,'post_key',None))
            return result,0 if result['complete'] else 2
        if args.command == 'doctor':
            result = doctor(settings, chrome, directory, args.probe)
            return result, 0 if result['chrome_running'] and (not args.probe or result['transport_probe_ok']) else 2
        if args.command == 'bind':
            return {'binding': chrome.bind(args.profile, args.window, args.tab), 'publish_clicks': 0}, 0
        if args.command == 'inspect':
            snapshot = chrome.call(args.profile, {'op': 'snapshot'})
            path = directory / 'evidence' / (args.profile + '-inspection-' + str(time.time_ns()) + '.json')
            atomic_json(path, snapshot)
            return {'snapshot': snapshot, 'evidence_path': str(path)}, 0
        if args.command == 'enqueue':
            jobs = settings.jobs(args.manifest)
            inserted = store.enqueue(jobs)
            store.export()
            store.backup()
            return {'new_deliveries': inserted, 'already_recorded': len(jobs) - inserted, 'publish_clicks': 0}, 0
        if args.command == 'import-history':
            result = history(settings, store, args.directory)
            report_html(directory, store.export())
            return result, 0
        if args.command == 'run':
            if args.job:
                store.get(args.job)
            result = Engine(store, workflow, settings.policy).run(args.job)
        elif args.command == 'reconcile':
            Engine(store, workflow, settings.policy).reconcile(args.job, args.url)
            result = store.export()
            store.backup()
        elif args.command == 'repair-google-link-validation':
            from google_business import GoogleBusinessProfile
            GoogleBusinessProfile(workflow).correct_link_validation(store,store.get(args.job),args.rejection_evidence)
            result=store.export()
        elif args.command == 'resume-google-unattempted':
            from google_business import GoogleBusinessProfile
            GoogleBusinessProfile(workflow).resume_unattempted(store,store.get(args.job))
            result=store.export()
        elif args.command == 'reconcile-google-public':
            from google_public import GooglePublicReadback
            evidence_directory=args.evidence_state.expanduser().resolve() if args.evidence_state else directory
            public=GooglePublicReadback(Workflow(settings,chrome,evidence_directory),args.context,args.post_id)
            Engine(store,public,settings.policy).reconcile(args.job)
            result=store.export();store.backup()
        elif args.command in {'resume', 'adopt-profile-change'}:
            job = store.get(args.job)
            if store.has_intent(args.job):
                raise Hold('INTENT_CANNOT_BE_RESET', 'An uncertain job can only be reconciled')
            if args.command == 'adopt-profile-change':
                current = settings.profile(job['payload']['profile_id'])
                if current['channel_key'] != job['channel_key']:
                    raise Hold('ACCOUNT_CHANGED', 'A different destination account requires a new profile and new delivery')
                payload = job['payload']
                if payload['profile_id'] in chrome.bindings:
                    chrome.adopt_profile(payload['profile_id'])
                payload.setdefault('previous_profile_hashes', []).append(payload['profile_hash'])
                payload['profile_hash'] = settings.fingerprint(payload['profile_id'])
                payload['profile_snapshot'] = current
                payload['workflow_snapshot'] = settings.workflow(current)
                with store.db:
                    store.db.execute('UPDATE jobs SET payload=? WHERE id=?', (canonical(payload), args.job))
            store.change(args.job, 'QUEUED')
            result = store.export()
            store.backup()
        else:
            result = store.export()
        report_html(directory, result)
        success=result['complete'] or args.command!='run'
        if args.command=='run' and args.job:
            requested=store.get(args.job)
            success=requested['state'] in {'PUBLISHED','HISTORICAL_VERIFIED'}
            result['requested_job']={'id':args.job,'state':requested['state'],'complete':success}
        return concise(result), 0 if success else 2


if __name__ == '__main__':
    try:
        result, code = main()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(code)
    except Hold as error:
        print(json.dumps({'status': 'HELD', 'code': error.code, 'detail': str(error)}, ensure_ascii=False, indent=2))
        sys.exit(2)
    except sqlite3.DatabaseError as error:
        print(json.dumps({'status': 'HELD', 'code': 'DB_INTEGRITY', 'detail': str(error), 'recovery': 'Preserve state/intent-ledger.jsonl and use recover-db with a verified backup'}))
        sys.exit(2)
    except KeyboardInterrupt:
        print('{"status":"STOPPED","recovery":"Run again with the same state directory; pending intents remain reconciliation-only"}')
        sys.exit(130)

