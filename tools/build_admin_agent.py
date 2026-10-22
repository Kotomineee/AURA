"""Build a protected onedir agent payload, separate from the desktop onefile."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import ssl
import subprocess
import sys


def build(root, work):
    trust=Path(ssl.__file__).with_name('codex-rejected-cas.pem')
    args=[sys.executable,'-m','PyInstaller','--noconfirm','--windowed','--onedir','--name','AURA-Agent',
          '--distpath',str(work/'agent-dist'),'--workpath',str(work/'agent-build'),'--specpath',str(work),
          '--collect-all','uvicorn','--collect-all','fastapi','--collect-all','cryptography',
          '--hidden-import','PIL.PngImagePlugin','--exclude-module','numpy','--exclude-module','matplotlib',
          '--exclude-module','pandas','--exclude-module','scipy','--exclude-module','pytest']
    if trust.is_file():args+=['--add-data',str(trust)+':.']
    args+=[str(root/'launch_agent.py')]
    subprocess.run(args,cwd=root,check=True)
    archive=Path(shutil.make_archive(str(work/'admin-agent'),'zip',work/'agent-dist/AURA-Agent'))
    metadata=work/'admin-agent.json'
    metadata.write_text(json.dumps({'sha256':hashlib.sha256(archive.read_bytes()).hexdigest()}),encoding='utf-8')
    return archive,metadata
