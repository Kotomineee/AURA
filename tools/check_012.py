"""Regression checks in temporary data; never enables startup or real actions."""
import base64
from concurrent.futures import Future
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
with tempfile.TemporaryDirectory() as folder:
    os.environ['AURA_DATA_DIR'] = folder
    os.environ['DRY_RUN'] = 'true'
    from app import updates, preferences, autostart
    from app.version import VERSION, BUILD
    assert VERSION == '0.1.7' and BUILD == 409
    release = {'tag_name':'v0.1.7', 'published_at':'2026-10-21T00:00:00Z', 'assets':[
        {'name':'AURA-Windows-0.1.7.exe','browser_download_url':'https://github.com/Kotomineee/AURA/releases/download/v0.1.7/AURA-Windows-0.1.7.exe'},
        {'name':'AURA-Android-0.1.7.apk','browser_download_url':'https://github.com/Kotomineee/AURA/releases/download/v0.1.7/AURA-Android-0.1.7.apk'}]}
    manifest = {'version':VERSION, 'build':BUILD,'assets':{'windows':'AURA-Windows-0.1.7.exe','android':'AURA-Android-0.1.7.apk'},'sha256':{'windows':'a'*64,'android':'b'*64}}
    assert updates.parse_release(release, manifest, 'Kotomineee/AURA', current_build=402)['available']
    assert not updates.parse_release(release, manifest, 'Kotomineee/AURA')['available']
    assert updates.parse_release(release, manifest, 'Kotomineee/AURA', current_build=404)['available']
    for bad in (dict(release,prerelease=True),dict(release,draft=True),dict(release,published_at=None),dict(release,tag_name='v0.1.99'),dict(release,assets=[])):
        try:updates.parse_release(bad,manifest,'Kotomineee/AURA')
        except ValueError:pass
        else:raise AssertionError('Invalid release accepted')
    discovery = dict(release,assets=release['assets']+[{'name':'aura-update.json','browser_download_url':'https://github.com/Kotomineee/AURA/releases/download/v0.1.7/aura-update.json'}])
    with patch.object(updates,'get_json',side_effect=[discovery,manifest]):
        assert not updates.check('Kotomineee/AURA')['available']
    preferences.save(autostart=False)
    preferences.save(example=1)
    assert preferences.read()=={'autostart':False,'example':1}
    import types
    fake=types.SimpleNamespace(HKEY_CURRENT_USER=1, REG_SZ=1)
    from unittest.mock import MagicMock
    fake.CreateKey=MagicMock();fake.SetValueEx=MagicMock();fake.DeleteValue=MagicMock()
    with patch.dict(sys.modules,winreg=fake),patch.object(autostart.sys,'frozen',False,create=True):
        autostart.configure(True);autostart.configure(False)
    assert fake.SetValueEx.call_count==1 and '--startup' in fake.SetValueEx.call_args.args[-1]
    assert fake.DeleteValue.call_count==1
    from fastapi.testclient import TestClient
    from app import native_agent as agent
    from app import process_icons as icons
    headers={'Authorization':'Bearer '+agent.settings['token']}
    future=Future();future.set_result(base64.b64encode(icons._png(bytes([0,200,150,255])*1024)).decode())
    import time
    with patch.object(icons,'_cache',{'a'*64:(time.monotonic(),future)}):
        with TestClient(agent.app) as client:
            assert client.post('/api/process-icons',json={'ids':['a'*64]}).status_code==401
            response=client.post('/api/process-icons',json={'ids':['a'*64]},headers=headers)
            assert response.status_code==200 and response.json()['icons']['a'*64]['state']=='ready'
            assert response.headers['cache-control']=='no-store'
            assert client.post('/api/process-icons',json={'ids':['../private']},headers=headers).status_code==400
            assert client.post('/api/process-icons',json={'ids':['a'*64]*17},headers=headers).status_code==422
    # Remote clients cannot stop the agent for a Windows update.
    with TestClient(agent.app,client=('192.0.2.1',1234)) as client:
        assert client.post('/api/update/prepare',json={'confirm':True},headers=headers).status_code==403
    pending_server=types.SimpleNamespace(should_exit=False)
    with patch.object(agent,'server',pending_server),patch.object(agent.threading,'Timer') as timer:
        with TestClient(agent.app,client=('127.0.0.1',1234)) as client:
            assert client.post('/api/update/prepare',json={'confirm':False},headers=headers).status_code==403
            assert client.post('/api/update/prepare',json={'confirm':True},headers=headers).status_code==200
            timer.assert_called_once()
            timer.call_args.args[1]()
            assert pending_server.should_exit
    assert 'token' in json.loads((Path(folder)/'identity.json').read_text())
    import logging
    logging.shutdown()
print('PASS: version migration, Release validation, startup configuration, icon batch/authentication')
