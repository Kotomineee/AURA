"""Integration checks with isolated data and mocked power commands; no real actions."""
import os
from pathlib import Path
import sys
import tempfile
import time
import uuid
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
with tempfile.TemporaryDirectory() as folder:
    os.environ['AURA_DATA_DIR'] = folder
    os.environ['DRY_RUN'] = 'true'
    from fastapi.testclient import TestClient
    from app import native_agent as agent
    from app.native_runtime import pairing
    import base64
    import json
    headers = {'Authorization':'Bearer ' + agent.settings['token']}
    def post(client, path, data, command_id=None):
        return client.post('/api/' + path, json=data,
            headers={**headers, 'X-Command-ID':command_id or str(uuid.uuid4())})
    with patch.object(agent.subprocess, 'run') as run:
        with TestClient(agent.app, client=('127.0.0.1', 12345)) as client:
            assert client.get('/api/status').status_code == 401
            assert client.get('/api/status', headers=headers).status_code == 200
            assert post(client,'power',{'action':'shutdown'}).status_code == 400
            assert post(client,'power',{'action':'format'}).status_code == 422
            key = str(uuid.uuid4())
            a = post(client,'shutdown',{'confirm':True,'delay_seconds':180},key)
            b = post(client,'shutdown',{'confirm':True,'delay_seconds':180},key)
            assert a.status_code == 200 and a.json()==b.json()
            deadline = a.json()['at']
            run.assert_not_called()
        with TestClient(agent.app, client=('127.0.0.1', 12345)) as client:
            assert client.get('/api/status',headers=headers).json()['shutdown_at']==deadline
            assert post(client,'shutdown/cancel',{}).status_code==200
            assert client.get('/api/status',headers=headers).json()['shutdown_at'] is None
            post(client,'shutdown',{'confirm':True,'delay_seconds':1})
            time.sleep(2)
            assert client.get('/api/status',headers=headers).json()['shutdown_at'] is None
            run.assert_not_called()
            assert post(client,'power',{'action':'restart'}).status_code==200
            run.assert_not_called()
            assert client.get('/api/logs',headers=headers).status_code==200
        code = json.loads(base64.urlsafe_b64decode(pairing('192.0.2.2','02:00:00:00:00:02','192.0.2.255')))
        assert code['token']==agent.settings['token'] and len(code['fingerprint'])==64
        with TestClient(agent.app, client=('192.0.2.5',12345)) as client:
            assert post(client,'mode',{'dry_run':False}).status_code==403
        run.assert_not_called()
    # Close file handlers so Windows can remove the isolated directory.
    for handler in agent.logger.handlers[:]:
        handler.close()
        agent.logger.removeHandler(handler)
print('PASS: authentication, validation, idempotency, persistent scheduling, cancellation, simulation, pairing and remote mode restriction')
