"""A foreign HTTP server must not be mistaken for an unused review port."""
from io import BytesIO
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import launch


class LaunchTests(unittest.TestCase):
    def test_refused_connection_allows_start(self):
        with patch('launch.urllib.request.urlopen', side_effect=URLError('refused')):
            self.assertFalse(launch.running())

    def test_foreign_http_error_reports_the_occupied_port(self):
        with patch('launch.urllib.request.urlopen', side_effect=HTTPError(launch.URL, 404, 'missing', {}, None)):
            with self.assertRaisesRegex(RuntimeError, 'Another application'):
                launch.running()

    def test_non_json_and_non_object_health_responses_report_the_occupied_port(self):
        for body in (b'<html>Other app</html>', b'[]', b'{"application":"other"}'):
            with self.subTest(body=body), patch('launch.urllib.request.urlopen', return_value=BytesIO(body)):
                with self.assertRaisesRegex(RuntimeError, 'Another application'):
                    launch.running()

    def test_matching_health_response_reopens_existing_app(self):
        with patch('launch.urllib.request.urlopen', return_value=BytesIO(b'{"application":"boldstone-review"}')):
            self.assertTrue(launch.running())
