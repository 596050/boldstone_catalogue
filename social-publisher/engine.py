"""Submission state machine. Retriable preparation and reconciliation are separate."""
import time
from pathlib import Path

from common import Hold, utc
from journal import PENDING_INTENT


class Engine:
    def __init__(self, store, adapter, policy, now=time.time):
        self.store, self.adapter, self.policy, self.now = store, adapter, policy, now

    def reconcile(self, job_id, native_url=None):
        job = self.store.get(job_id)
        if job['state'] in {'PUBLISHED', 'HISTORICAL_VERIFIED'}:
            return job['receipt']
        if not self.store.has_intent(job_id):
            raise Hold('MISSING_INTENT', 'Only a recorded submission can be reconciled')
        attempts = self.store.verification_attempt(job_id)
        try:
            receipt = self.adapter.verify(job, native_url=native_url)
            self.store.published(job_id, receipt)
            return receipt
        except Exception as error:
            delay = min(self.policy['retry_max_seconds'], self.policy['retry_base_seconds'] * (2 ** min(attempts - 1, 10)))
            self.store.change(job_id, 'OUTCOME_UNKNOWN', str(error), next_attempt=self.now() + delay)
            raise

    def one(self, job):
        job_id = job['id']
        if job['state'] in {'PUBLISHED', 'HISTORICAL_VERIFIED', 'BLOCKED'}:
            return
        if self.store.has_intent(job_id) or job['state'] in PENDING_INTENT:
            if job['next_attempt'] > self.now() or job['verify_attempts'] >= self.policy.get('max_reconcile_attempts', 8):
                return
            try:
                self.reconcile(job_id)
            except Exception:
                pass
            return
        if job['next_attempt'] > self.now():
            return
        self.store.change(job_id, 'PREPARING', increment=True)
        try:
            self.adapter.prepare(self.store.get(job_id))
            self.store.change(job_id, 'READY')
        except Exception as error:
            attempts = self.store.get(job_id)['attempts']
            retryable = isinstance(error, Hold) and error.retryable
            retryable = retryable and attempts < self.policy['max_prepare_attempts']
            delay = min(self.policy['retry_max_seconds'], self.policy['retry_base_seconds'] * (2 ** (attempts - 1)))
            self.store.change(job_id, 'RETRY_WAIT' if retryable else 'BLOCKED', str(error),
                              next_attempt=self.now() + delay if retryable else 0)
            return
        # From here, any exception (including death before the click) leaves an
        # intent. Neither this run nor a restarted process may submit it again.
        self.store.intent(job_id)
        try:
            self.adapter.submit(self.store.get(job_id))
            self.store.change(job_id, 'VERIFYING')
        except Exception as error:
            self.store.change(job_id, 'OUTCOME_UNKNOWN', str(error))
            return
        try:
            self.reconcile(job_id)
        except Exception:
            pass

    def run(self, job_id=None):
        try:
            return self._run(job_id)
        finally:
            close = getattr(self.adapter, 'close', None)
            if close is not None:
                close()

    def _run(self, job_id=None):
        before = {j['id']: j['state'] for j in self.store.jobs()}
        intents_before = len([e for e in self.store.ledger if e['kind'] == 'PUBLISH_INTENT'])
        for job in self.store.jobs():
            if job_id is None or job['id'] == job_id:
                self.one(job)
        report = self.store.export()
        report['run_results'] = {'publish_intents_written': len([e for e in self.store.ledger if e['kind'] == 'PUBLISH_INTENT']) - intents_before,
                                 'deliveries_confirmed': len([j for j in report['jobs'] if j['state'] == 'PUBLISHED' and before.get(j['id']) != 'PUBLISHED']),
                                 'historical_deliveries': report['counts'].get('HISTORICAL_VERIFIED', 0)}
        self.store.backup()
        return report

