"""A foreign HTTP server must not be mistaken for an unused review port."""
from io import BytesIO
import errno
import http.client
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import launch


class LaunchTests(unittest.TestCase):
    def test_refused_connection_allows_start(self):
        with patch('launch.urllib.request.urlopen', side_effect=URLError(ConnectionRefusedError(errno.ECONNREFUSED, 'refused'))):
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

    def test_busy_or_reset_port_never_starts_a_second_server(self):
        with tempfile.TemporaryDirectory() as temporary:
            for error in (TimeoutError('busy catalogue'), URLError(TimeoutError('busy catalogue')),
                          ConnectionResetError('reset'), URLError('network failure')):
                with self.subTest(error=error), patch('launch.RUNTIME', Path(temporary)), \
                        patch('launch.urllib.request.urlopen', side_effect=error), \
                        patch('launch.subprocess.Popen') as start, patch('launch.webbrowser.open') as browser:
                    with self.assertRaisesRegex(RuntimeError, 'no second instance was started'):
                        launch.main()
                    start.assert_not_called()
                    browser.assert_not_called()
                    self.assertFalse((Path(temporary) / 'server.pid').exists())

    def test_truncated_http_health_response_is_an_occupied_port(self):
        with patch('launch.urllib.request.urlopen', side_effect=http.client.IncompleteRead(b'{')):
            with self.assertRaisesRegex(RuntimeError, 'health response is not Boldstone Review'):
                launch.running()

    def test_own_startup_keeps_waiting_through_a_transient_probe_timeout(self):
        with tempfile.TemporaryDirectory() as temporary:
            process = Mock(pid=12345)
            process.poll.return_value = None
            results = [URLError(ConnectionRefusedError(errno.ECONNREFUSED, 'refused')),
                       TimeoutError('starting'), BytesIO(b'{"application":"boldstone-review"}')]
            with patch('launch.RUNTIME', Path(temporary)), \
                    patch('launch.urllib.request.urlopen', side_effect=results), \
                    patch('launch.subprocess.Popen', return_value=process) as start, \
                    patch('launch.time.sleep'), patch('launch.webbrowser.open') as browser, \
                    patch('builtins.print'):
                launch.main()
            start.assert_called_once()
            browser.assert_called_once_with(launch.URL)
            self.assertEqual((Path(temporary) / 'server.pid').read_text(), '12345')
