"""Headless packaged-runtime regression check; no Tk root, agent or LAN access."""
import io
import json
import os
from pathlib import Path
import ssl
import tempfile


def run():
    from . import native_runtime
    original_data = native_runtime.DATA
    try:
        with tempfile.TemporaryDirectory(prefix='aura-runtime-check-') as folder:
            native_runtime.DATA = Path(folder)
            settings = native_runtime.identity()
            client = ssl.create_default_context(cafile=settings['cert'])
            assert client.verify_mode == ssl.CERT_REQUIRED and client.check_hostname
            server = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            server.load_cert_chain(settings['cert'], settings['key'])

            # Exercise a real TLS exchange entirely in memory: no listener,
            # loopback connection or access to the user's saved AURA identity.
            client_in, client_out = ssl.MemoryBIO(), ssl.MemoryBIO()
            server_in, server_out = ssl.MemoryBIO(), ssl.MemoryBIO()
            c = client.wrap_bio(client_in, client_out, server_hostname='localhost')
            s = server.wrap_bio(server_in, server_out, server_side=True)
            client_done = server_done = False
            for _ in range(12):
                for endpoint, side in ((c, 'client'), (s, 'server')):
                    try:
                        endpoint.do_handshake()
                        if side == 'client': client_done = True
                        else: server_done = True
                    except ssl.SSLWantReadError:
                        pass
                data = client_out.read()
                if data: server_in.write(data)
                data = server_out.read()
                if data: client_in.write(data)
                if client_done and server_done: break
            assert client_done and server_done, 'TLS handshake did not complete'
            c.write(b'AURA runtime OK')
            server_in.write(client_out.read())
            assert s.read(64) == b'AURA runtime OK'
            from PIL import Image
            image = Image.new('RGBA', (32, 32), (49, 208, 195, 255))
            stream = io.BytesIO()
            image.save(stream, format='PNG')
            stream.seek(0)
            assert Image.open(stream).size == (32, 32)
            import tkinter  # Import only: deliberately never construct Tk().
            import psutil
            from . import process_icons, updates, update_installer, autostart, preferences
            from .version import VERSION, BUILD
            import sys
            import base64
            extracted = process_icons._extract(sys.executable)
            assert extracted, 'The packaged executable must expose its actual icon'
            assert Image.open(io.BytesIO(base64.b64decode(extracted))).size == (32,32)
            assert VERSION == '0.1.3' and BUILD == 405
            import sounddevice  # Import only: never open an input device here.
            from vosk import Model, KaldiRecognizer, SetLogLevel
            from . import voice, admin
            SetLogLevel(-1)
            resources=Path(sys._MEIPASS)
            model=Model(str(resources/'voice-model'))
            recognizer=KaldiRecognizer(model,16000)
            recognizer.AcceptWaveform(bytes(32000))
            assert json.loads(recognizer.FinalResult()).get('text')==''
            assert model.vosk_model_find_word('aura')>=0 and model.vosk_model_find_word('ok')>=0
            import hashlib
            metadata=json.loads((resources/'admin-agent.json').read_text(encoding='utf-8'))
            assert hashlib.sha256((resources/'admin-agent.zip').read_bytes()).hexdigest()==metadata['sha256']
            assert updates.DEFAULT_REPOSITORY == 'Kotomineee/AURA'
            report = {'result': 'PASS', 'tls': c.version(), 'certificate_verification': True,
                      'png': True, 'tkinter_import': True, 'psutil_import': True,
                      'actual_executable_icon': True, 'version': VERSION, 'build': BUILD,
                      'voice_model': True, 'voice_wake_vocabulary': True, 'microphone_opened': False,
                      'protected_agent_payload': True, 'windows_created': 0, 'network_connections': 0}
            destination = os.environ.get('AURA_RUNTIME_CHECK_OUTPUT')
            if destination:
                Path(destination).write_text(json.dumps(report, indent=2), encoding='utf-8')
    finally:
        native_runtime.DATA = original_data
