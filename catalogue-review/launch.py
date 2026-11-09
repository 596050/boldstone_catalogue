#!/usr/bin/env python3
"""Start (or reopen) the local review room without needing to keep Terminal open."""
from pathlib import Path
import errno
import http.client
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser

HERE = Path(__file__).resolve().parent
RUNTIME = Path.home() / 'Library/Application Support/BoldstoneReview'
URL = 'http://127.0.0.1:8767'


class HealthUnavailable(RuntimeError):
    """A connected/busy port is not evidence that another server may start."""


def running():
    try:
        with urllib.request.urlopen(URL + '/api/health', timeout=1) as response:
            data = json.load(response)
        if not isinstance(data, dict) or data.get('application') != 'boldstone-review':
            raise RuntimeError('Another application is using port 8767.')
        return True
    except (urllib.error.HTTPError, http.client.HTTPException, ValueError) as exc:
        raise RuntimeError('Another application is using port 8767; its health response is not Boldstone Review.') from exc
    except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
        reason = exc.reason if isinstance(exc, urllib.error.URLError) else exc
        if isinstance(reason, ConnectionRefusedError) or getattr(reason, 'errno', None) == errno.ECONNREFUSED:
            return False
        # A busy catalogue can delay its own health handler. A timeout/reset
        # does not prove that the port is free: starting again can initialize
        # a second app against the same saved runtime before binding fails.
        raise HealthUnavailable('Port 8767 did not provide a health response. The review app may still be running; no second instance was started. Retry when it responds.') from exc


def main():
    RUNTIME.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not running():
        with (RUNTIME / 'server.log').open('a') as log:
            process = subprocess.Popen([sys.executable, str(HERE / 'server.py')], cwd=HERE,
                                       stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
        (RUNTIME / 'server.pid').write_text(str(process.pid))
        for attempt in range(60):
            try:
                if running():
                    break
            except HealthUnavailable:
                # This process is already ours. Keep its readiness wait without
                # restarting it or assuming a timeout means it exited.
                pass
            if process.poll() is not None:
                raise RuntimeError('The app could not start. See ' + str(RUNTIME / 'server.log'))
            time.sleep(.5)
        else:
            raise RuntimeError('Still starting. See ' + str(RUNTIME / 'server.log'))
    webbrowser.open(URL)
    print('Boldstone review room: ' + URL)
    print('Your decisions are saved in ' + str(RUNTIME))


if __name__ == '__main__':
    main()
