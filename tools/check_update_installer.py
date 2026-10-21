"""Download, validation and atomic swap tests. No real process/registry changes."""
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
with tempfile.TemporaryDirectory() as temporary:
    os.environ['AURA_DATA_DIR'] = temporary
    from app import updates, update_installer as installer
    from app.version import BUILD
    data = Path(temporary)
    payload = b'MZ' + b'new binary fixture' * 10
    digest = hashlib.sha256(payload).hexdigest()
    result = {'available':True,'build':BUILD+1,'sha256':digest,
              'url':'https://github.com/Kotomineee/AURA/releases/download/v0.1.3/AURA-Windows-0.1.3.exe'}
    class Response(io.BytesIO):
        url = 'https://release-assets.githubusercontent.com/fixture'
    destination = data/'updates/payload.exe'
    with patch.object(updates.urllib.request, 'urlopen', return_value=Response(payload)):
        assert updates.download(result,destination).read_bytes() == payload
    with patch.object(updates.urllib.request, 'urlopen', return_value=Response(b'broken')):
        try:updates.download(result,destination)
        except ValueError:pass
        else:raise AssertionError('Corrupt download accepted')
    assert destination.read_bytes()==payload and not destination.with_suffix('.part').exists()
    target = data/'AURA.exe'
    target.write_bytes(b'original app')
    identity = data/'identity.json';identity.write_text('private identity fixture')
    job_path = data/'updates/job-test.json'
    job = {'target':str(target),'sha256':digest,'build':BUILD+1,'parent_pid':1,'parent_created':1,
           'agent':{'pid':2,'created_at':2}}
    job_path.write_text(json.dumps(job))
    waits = MagicMock()
    def ready(args):
        Path(args[2]).write_text(json.dumps({'build':BUILD+1}))
        return SimpleNamespace(poll=lambda:None)
    assert installer.apply(job_path,wait=waits,start=ready,retries=1)=='installed'
    assert target.read_bytes()==payload and waits.call_count==2
    assert identity.read_text()=='private identity fixture'
    assert not target.with_name('AURA.exe.previous').exists()
    # Installation failure before restart restores the previous executable.
    destination.write_bytes(payload);target.write_bytes(b'old again')
    job_path.with_suffix('.ready.json').unlink(missing_ok=True)
    start = MagicMock(side_effect=[OSError('fixture'),SimpleNamespace(poll=lambda:None)])
    try:installer.apply(job_path,wait=MagicMock(),start=start,retries=1)
    except OSError:pass
    else:raise AssertionError('Restart failure must be reported')
    assert target.read_bytes()==b'old again' and start.call_count==2
    # If Windows keeps the target locked, the old app is reopened unchanged.
    destination.write_bytes(payload)
    recover=MagicMock()
    with patch.object(installer.os,'replace',side_effect=PermissionError('locked fixture')):
        try:installer.apply(job_path,wait=MagicMock(),start=recover,retries=1)
        except PermissionError:pass
        else:raise AssertionError('Locked executable must report failure')
    recover.assert_called_once_with([str(target)])
    assert target.read_bytes()==b'old again'
    # A downloaded file changed after verification is rejected before app exit.
    destination.write_bytes(b'corrupted')
    never_start = MagicMock();never_wait=MagicMock()
    try:installer.apply(job_path,wait=never_wait,start=never_start,retries=1)
    except ValueError:pass
    else:raise AssertionError('Changed payload accepted')
    never_start.assert_not_called();never_wait.assert_not_called()
    assert identity.read_text()=='private identity fixture'
print('PASS: internal download, SHA-256, partial cleanup, swap/restart, rollback, identity preservation')
