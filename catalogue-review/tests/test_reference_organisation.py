"""External reference tagging must not create impossible Dropbox moves."""
import unittest

import test_background_jobs as fixtures
from test_deletions import TARGET
from organisation import plan, NeedsChoice


OUTSIDE = '/BOLDSTONE MASTER/Products/Workshop and Moulding/Seaweed Ripple/photo.JPG'
OLD_MESSAGE = 'Automatic organisation is limited to the Wall Sculptures folders. This reference stays in its current location.'


class ReferenceOrganisationTests(unittest.TestCase):
    setUp = fixtures.BackgroundJobTests.setUp
    tearDown = fixtures.BackgroundJobTests.tearDown
    organisation_fixture = fixtures.BackgroundJobTests.organisation_fixture
    type_save = fixtures.BackgroundJobTests.type_save

    def external(self):
        self.organisation_fixture()
        self.cat.assets[TARGET]['provenance']['path'] = OUTSIDE

    def test_external_reference_tags_save_without_enqueuing_a_move(self):
        self.external()
        self.type_save(['workshop', 'in_situ'])
        self.assertEqual(self.store.get('asset', '', TARGET)['data']['types'], ['workshop', 'in_situ'])
        self.assertEqual(self.jobs.snapshot()['jobs'], [])
        self.assertFalse(self.jobs.step())
        self.assertEqual(self.native.moves, [])

    def test_external_component_assignment_saves_without_a_move(self):
        self.external()
        self.store.assign([{'product_id': 'L1', 'asset_id': TARGET, 'version': 0,
                           'data': {'state': 'attached'}, 'original': {}}],
                          self.cat.source['register_sha256'], 'Add reference')
        self.assertEqual(self.store.get('assignment', 'L1', TARGET)['data']['state'], 'attached')
        self.assertEqual(self.jobs.snapshot()['jobs'], [])

    def test_external_reference_explains_why_tags_do_not_move_the_file(self):
        self.external()
        self.assertIn('stays', self.app.projection().asset(TARGET).get('organisation_notice', ''))

    def test_old_unsubmitted_external_job_is_not_a_failure_but_keeps_its_receipt(self):
        self.external()
        with self.store.connect() as db:
            self.jobs.insert(db, 'legacy-reference', 'organise', {'asset_id': TARGET})
        self.jobs.mark('legacy-reference', 'needs_review', {'message': OLD_MESSAGE})
        before = self.store.snapshot()
        job = self.jobs.get('legacy-reference')
        self.assertEqual(job['state'], 'not_required')
        self.assertIn('stays', job['message'])
        self.assertTrue(job['can_dismiss'])
        self.assertEqual(self.store.snapshot(), before)
        self.assertEqual(self.jobs.clear_finished()['cleared'], 1)

    def test_possible_native_move_never_becomes_a_harmless_reference(self):
        self.external()
        for state, message, intent in [('uncertain', OLD_MESSAGE, False),
                                       ('needs_review', OLD_MESSAGE, True),
                                       ('needs_review', 'Changed content', False)]:
            with self.subTest(state=state, intent=intent):
                ident = state + str(intent) + str(len(message))
                with self.store.connect() as db:
                    self.jobs.insert(db, ident, 'organise', {'asset_id': TARGET})
                self.jobs.mark(ident, state, {'message': message})
                if intent:
                    path = self.jobs.root / ident / 'move-intent.json'
                    path.parent.mkdir(); path.write_text('{}')
                self.assertEqual(self.jobs.get(ident)['state'], state)

    def test_missing_path_still_requires_attention(self):
        self.organisation_fixture()
        self.cat.assets[TARGET]['provenance']['path'] = ''
        self.type_save(['in_situ'])
        self.jobs.step()
        self.assertEqual(self.jobs.snapshot()['jobs'][0]['state'], 'needs_review')

    def test_unknown_namespace_is_not_silently_treated_as_an_external_reference(self):
        self.organisation_fixture()
        self.cat.assets[TARGET]['provenance']['path'] = 'ns:999999/unknown/photo.JPG'
        self.type_save(['in_situ'])
        self.jobs.step()
        self.assertEqual(self.jobs.snapshot()['jobs'][0]['state'], 'needs_review')

    def test_a_reference_moved_into_wall_sculptures_can_be_organised(self):
        self.external()
        self.type_save(['workshop'])
        self.organisation_fixture()
        self.type_save(['in_situ'], 1)
        self.jobs.step()
        self.assertEqual(self.jobs.snapshot()['jobs'][0]['state'], 'completed')
        self.assertEqual(len(self.native.moves), 1)

    def test_external_sibling_with_root_name_prefix_never_gets_a_move(self):
        self.external()
        self.cat.assets[TARGET]['provenance']['path'] = '/BOLDSTONE MASTER/Products/01 Wall Sculptures Archive/photo.JPG'
        self.type_save(['in_situ'])
        self.assertEqual(self.jobs.snapshot()['jobs'], [])
        with self.assertRaises(NeedsChoice):
            plan(self.app.projection(), TARGET)

    def test_namespaced_wall_path_still_queues_and_plans_the_exact_original(self):
        self.organisation_fixture()
        path = self.cat.assets[TARGET]['provenance']['path']
        for prefix in ['ns:202238505', 'ns:202238505/']:
            self.cat.assets[TARGET]['provenance']['path'] = prefix + path
            with self.subTest(prefix=prefix):
                result = plan(self.app.projection(), TARGET)
                self.assertEqual(result['binding']['path'], path)
                self.assertEqual(result['binding']['id'], TARGET)
        self.type_save(['in_situ'])
        self.assertEqual(self.jobs.snapshot()['jobs'][0]['state'], 'queued')

    def test_explicit_outside_plan_is_still_blocked(self):
        self.external()
        with self.assertRaises(NeedsChoice):
            plan(self.app.projection(), TARGET)
        self.assertEqual(self.native.moves, [])


if __name__ == '__main__':
    unittest.main()
