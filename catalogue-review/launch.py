#!/usr/bin/env python3
"""Start (or reopen) the local review room without needing to keep Terminal open."""
from pathlib import Path
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


def running():
    try:
        with urllib.request.urlopen(URL + '/api/health', timeout=1) as response:
            data = json.load(response)
        if not isinstance(data, dict) or data.get('application') != 'boldstone-review':
            raise RuntimeError('Another application is using port 8767.')
        return True
    except (urllib.error.HTTPError, ValueError) as exc:
        raise RuntimeError('Another application is using port 8767; its health response is not Boldstone Review.') from exc
    except (urllib.error.URLError, TimeoutError, ConnectionError):
        return False


def main():
    RUNTIME.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not running():
        with (RUNTIME / 'server.log').open('a') as log:
            process = subprocess.Popen([sys.executable, str(HERE / 'server.py')], cwd=HERE,
                                       stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
        (RUNTIME / 'server.pid').write_text(str(process.pid))
        for attempt in range(60):
            if running():
                break
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
