"""Isolated icon/security checks. No windows, LAN, power or process termination."""
import base64
from concurrent.futures import Future
import io
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import Image
from app import process_icons as icons


def decode(encoded):
    data = base64.b64decode(encoded)
    assert data[:8] == b'\x89PNG\r\n\x1a\n'
    with Image.open(io.BytesIO(data)) as image:
        assert image.size == (32, 32) and image.mode == 'RGBA'
        return image.copy()


pixels = bytes([50, 120, 200, 128]) * (32*32)
assert decode(base64.b64encode(icons._png(pixels))).getpixel((0, 0)) == (50, 120, 200, 128)

# The actual native extraction path is exercised against this Python runtime,
# not against the user's app/process inventory. No UI is created.
if os.name == 'nt':
    import ctypes
    user = ctypes.WinDLL('user32')
    kernel = ctypes.WinDLL('kernel32')
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    user.GetGuiResources.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    process = kernel.GetCurrentProcess()
    warm = icons._extract_pe(sys.executable)
    assert warm, 'Python executable should contain an actual PE icon'
    assert decode(warm).getchannel('A').getextrema()[1] > 0
    before = user.GetGuiResources(process, 0)
    for _ in range(20):
        assert icons._extract_pe(sys.executable)
    assert user.GetGuiResources(process, 0) <= before + 1, 'GDI handle leak'

with tempfile.TemporaryDirectory() as folder:
    package = Path(folder) / 'package'
    assets = package / 'Assets'
    assets.mkdir(parents=True)
    executable = package / 'Example.exe'
    executable.write_bytes(b'fixture')
    manifest = package / 'AppxManifest.xml'
    def write_manifest(asset):
        manifest.write_text('<Package xmlns:uap="urn:visual"><Applications><Application Executable="Example.exe"><uap:VisualElements Square44x44Logo="' + asset + '"/></Application></Applications></Package>')
    Image.new('RGBA', (64, 64), (20, 210, 190, 255)).save(assets / 'Logo.targetsize-32_altform-unplated.png')
    write_manifest('Assets/Logo.png')
    assert decode(icons._package_icon(str(executable))).getpixel((16, 16)) == (20, 210, 190, 255)
    if os.name == 'nt':
        with patch.object(icons, '_package_icon', return_value='package-identity'), patch.object(icons, '_extract_pe') as pe:
            assert icons._extract(str(executable)) == 'package-identity'
            pe.assert_not_called()  # A host PE must not replace the installed package identity.
    Image.new('RGBA', (32, 32), (255, 0, 0, 255)).save(Path(folder) / 'private.png')
    write_manifest('../private.png')
    assert icons._package_icon(str(executable)) is None, 'Manifest traversal must fail closed'
    manifest.write_text('<broken>')
    assert icons._package_icon(str(executable)) is None

    row = {'pid': 12345, 'created_at': 12.5, 'name': 'Example.exe', 'ram_mb': 10.0}
    class Process:
        def __init__(self, pid): self.pid = pid
        def create_time(self): return 12.5
        def exe(self): return str(executable)
    icons._cache.clear()
    with patch.object(icons.psutil, 'Process', Process), patch.object(icons, '_extract', return_value=warm if os.name=='nt' else base64.b64encode(icons._png(pixels)).decode()):
        key = icons.register(row)
        assert key and len(key) == 64 and key == icons.register(row)
        assert icons.register(dict(row, created_at=13.0)) is None, 'PID reuse must not get the old icon'
        payload = icons.lookup(key)
        assert payload['state'] == 'ready' and decode(payload['png'])
        assert str(executable) not in json.dumps(payload)
        assert icons.lookup('0'*64) == {'state':'unavailable','png':None}
        with patch.object(icons.time, 'monotonic', return_value=icons._cache[key][0]+icons.TTL+1):
            assert icons.lookup(key)['state'] == 'unavailable'
        missing = Future(); missing.set_result(None)
        negative_time = icons.time.monotonic() - 30
        icons._cache[key] = (negative_time, missing)
        assert icons.register(row) == key
        assert icons._cache[key][0] == negative_time, 'Negative cache must expire even with frequent process refreshes'
        # Pending extraction never waits on the UI or exposes internal errors.
        pending = Future()
        icons._cache['a'*64] = (icons.time.monotonic(), pending)
        assert icons.lookup('a'*64)['state'] == 'pending'
        pending.set_exception(OSError('sensitive filesystem path'))
        assert icons.lookup('a'*64) == {'state':'unavailable','png':None}
        icons._cache.clear()
        # A full in-flight cache cannot grow or enqueue additional work.
        for n in range(icons.LIMIT):
            icons._cache[str(n)] = (icons.time.monotonic(), Future())
        assert icons.register(row) is None and len(icons._cache) == icons.LIMIT
        icons._cache.clear()

    os.environ['AURA_DATA_DIR'] = str(Path(folder) / 'agent')
    os.environ['DRY_RUN'] = 'true'
    from fastapi.testclient import TestClient
    from app import native_agent as agent
    headers = {'Authorization': 'Bearer ' + agent.settings['token']}
    with patch.object(agent.legacy, 'processes', return_value=[row]), patch.object(icons, 'register', return_value='b'*64), patch.object(agent.subprocess, 'run') as power:
        with TestClient(agent.app, client=('127.0.0.1',12345)) as client:
            assert client.get('/api/process-icons/'+'b'*64).status_code == 401
            assert client.get('/api/processes', headers=headers).json()[0]['icon_id'] == 'b'*64
            assert client.get('/api/process-icons/not-a-key',headers=headers).status_code == 404
            response = client.get('/api/process-icons/'+'b'*64,headers=headers)
            assert response.status_code == 200 and response.json()['state'] == 'unavailable'
            assert response.headers['cache-control'] == 'no-store'
            assert client.get('/api/process-icons/'+'b'*64+'?path=C:/private.txt',headers=headers).json() == response.json()
            assert 'exe' not in client.get('/api/processes',headers=headers).json()[0]
        power.assert_not_called()
    for handler in agent.logger.handlers[:]:
        handler.close(); agent.logger.removeHandler(handler)
icons._pool.shutdown(wait=True)
print('PASS: PNG, actual PE extraction/GDI cleanup, MSIX assets/traversal, identity, deduplication, TTL, negative/pending/bounded cache, auth and private API')
