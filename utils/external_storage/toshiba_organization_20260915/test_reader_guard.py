import unittest
from organize import retain_live_users


class ReaderLifetimeTests(unittest.TestCase):
    def test_closed_descriptor_does_not_release_live_reader(self):
        observed = [{'pid': 123, 'path': '/volume/prices/ABC.bin', 'access': 'r'}]
        prior = retain_live_users(observed, [], {123: 'start-1'})
        self.assertEqual(retain_live_users([], prior, {123: 'start-1'}), prior)

    def test_exited_process_and_reused_pid_release_prior_fence(self):
        previous = [{'pid': 123, 'path': '/volume/prices/ABC.bin', 'process_birth': 'start-1'}]
        self.assertEqual(retain_live_users([], previous, {}), [])
        self.assertEqual(retain_live_users([], previous, {123: 'start-2'}), [])


if __name__ == '__main__': unittest.main()
