"""Run AFTER both binaries are ready; attach the result to a draft Release."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.version import VERSION, BUILD

parser = argparse.ArgumentParser()
parser.add_argument('--windows', type=Path, required=True)
parser.add_argument('--android', type=Path, required=True)
parser.add_argument('--output', type=Path, default=Path('aura-update.json'))
args = parser.parse_args()
for file in (args.windows,args.android):
    if not file.is_file():raise SystemExit(f'Arquivo ausente: {file}')
def digest(file):
    value=hashlib.sha256()
    with file.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):value.update(block)
    return value.hexdigest()
manifest={'version':VERSION,'build':BUILD,
          'assets':{'windows':args.windows.name,'android':args.android.name},
          'sha256':{'windows':digest(args.windows),'android':digest(args.android)}}
args.output.write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
print(f'Manifesto {VERSION}/{BUILD} gerado com hashes dos dois arquivos.')
