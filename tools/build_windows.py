"""Build the native executable, including optional Python-runtime trust data."""
from pathlib import Path
import os
import ssl
import PyInstaller.__main__

root = Path(__file__).resolve().parents[1]
os.chdir(root)
from prepare_voice import prepare
from build_admin_agent import build
work=Path(os.environ.get('AURA_BUILD_DIR',str(root/'build'))).resolve()
work.mkdir(parents=True,exist_ok=True)
model=prepare(work/'voice-assets')
english_model=prepare(work/'voice-assets',english=True)
agent_archive,agent_metadata=build(root,work)
runtime_data = []
trust_resource = Path(ssl.__file__).with_name('codex-rejected-cas.pem')
if trust_resource.is_file():
    # ssl.SSLContext in this runtime accesses this file beside ssl.__file__.
    # Keep its trust policy intact when the module is frozen into the executable.
    runtime_data = ['--add-data', str(trust_resource) + ':.']
PyInstaller.__main__.run([
    '--noconfirm', '--windowed', '--onefile', '--name', 'AURA-Windows-0.1.4',
    '--distpath', os.environ.get('AURA_DIST_DIR', str(root / 'dist')),
    '--workpath', os.environ.get('AURA_BUILD_DIR', str(root / 'build')),
    '--specpath', os.environ.get('AURA_SPEC_DIR', str(root)),
    '--version-file', str(root / 'tools/windows-version.txt'),
    '--icon', str(root / 'tools/aura.ico'),
    '--collect-all', 'uvicorn', '--collect-all', 'fastapi', '--collect-all', 'cryptography',
    '--collect-all', 'vosk', '--collect-all', 'sounddevice', '--collect-all', '_sounddevice_data',
    '--add-data', str(model)+':voice-model',
    '--add-data', str(english_model)+':voice-model-en',
    '--add-data', str(agent_archive)+':.', '--add-data', str(agent_metadata)+':.',
    '--add-data', str(root/'licenses')+':licenses',
    '--hidden-import', 'app.native_agent', '--hidden-import', 'PIL.PngImagePlugin',
    '--exclude-module', 'numpy', '--exclude-module', 'matplotlib', '--exclude-module', 'pandas',
    '--exclude-module', 'scipy', '--exclude-module', 'IPython', '--exclude-module', 'pytest',
    *runtime_data, str(root / 'launch_windows.py'),
])
