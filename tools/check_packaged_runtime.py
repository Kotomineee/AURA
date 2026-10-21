"""Headless TLS regression check of the actual packaged executable."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

exe = Path(sys.argv[1] if len(sys.argv) > 1 else 'dist/AURA/AURA.exe').resolve()
with tempfile.TemporaryDirectory(prefix='aura-package-check-') as folder:
    report_path = Path(folder) / 'report.json'
    identity_path = Path(folder) / 'identity'
    env = dict(os.environ, AURA_RUNTIME_CHECK_OUTPUT=str(report_path), AURA_DATA_DIR=str(identity_path))
    result = subprocess.run([str(exe), '--check-runtime'], env=env, timeout=60,
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW)
    assert result.returncode == 0, report_path.read_text() if report_path.exists() else result.returncode
    report = json.loads(report_path.read_text())
    assert report['result'] == 'PASS' and report['certificate_verification']
    assert report['windows_created'] == 0 and report['network_connections'] == 0
    assert not identity_path.exists(), 'Saved identity must not be touched'
    print(json.dumps(report, indent=2))
