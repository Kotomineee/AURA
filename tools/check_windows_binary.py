"""Smoke-check the packaged window and HTTPS agent without power operations."""
import json
import os
from pathlib import Path
import ssl
import subprocess
import tempfile
import time
import urllib.request
import urllib.error

exe = Path('dist/AURA/AURA.exe').resolve()
with tempfile.TemporaryDirectory() as folder:
    env = dict(os.environ, AURA_DATA_DIR=folder)
    subprocess.run([str(exe), '--check-ui'], env=env, check=True, timeout=30,
                   creationflags=subprocess.CREATE_NO_WINDOW)
    assert (Path(folder)/'ui-check.txt').read_text() == 'OK'
    settings = json.loads((Path(folder)/'identity.json').read_text())
    context = ssl.create_default_context(cafile=str(Path(folder)/'server.crt'))
    proc = subprocess.Popen([str(exe), '--agent'], env=env, creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        for _ in range(30):
            try:
                req = urllib.request.Request('https://127.0.0.1:8765/api/status',
                    headers={'Authorization':'Bearer '+settings['token']})
                with urllib.request.urlopen(req, context=context, timeout=2) as response:
                    assert json.load(response)['dry_run'] is True
                break
            except OSError:
                if proc.poll() is not None:
                    raise RuntimeError('Packaged agent exited before connecting')
                time.sleep(.5)
        else:
            raise RuntimeError('Packaged agent did not respond')
        try:
            urllib.request.urlopen('https://127.0.0.1:8765/api/status',context=context,timeout=2)
            raise AssertionError('Unauthenticated request accepted')
        except urllib.error.HTTPError as exc:
            assert exc.code == 401
    finally:
        proc.terminate()
        proc.wait(timeout=10)
print('PASS: packaged Windows UI, HTTPS agent, simulation default and authentication')
