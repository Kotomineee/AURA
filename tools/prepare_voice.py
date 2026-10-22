"""Download the pinned, redistributable Portuguese offline speech model."""
import hashlib
import os
from pathlib import Path
import urllib.request
import zipfile

SHA256='6e1ce909032e1afa7a88e68a3d628ecafff302bdf195befab308826c395e93b7'


def prepare(destination,english=False):
    destination=Path(destination)
    destination.mkdir(parents=True,exist_ok=True)
    name='vosk-model-small-en-us-0.15' if english else 'vosk-model-small-pt-0.3'
    expected='30f26242c4eb449f948e42cb302dd7a686cb29a3423a8367f99ff41780942498' if english else SHA256
    archive=Path(os.environ.get('AURA_VOICE_MODEL_EN_ZIP' if english else 'AURA_VOICE_MODEL_ZIP',str(destination/('model-en.zip' if english else 'model.zip'))))
    if not archive.exists():
        urllib.request.urlretrieve('https://alphacephei.com/vosk/models/'+name+'.zip',archive)
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=expected:raise ValueError('Modelo de voz inválido')
    with zipfile.ZipFile(archive) as package:
        for item in package.infolist():
            if not (destination/item.filename).resolve().is_relative_to(destination.resolve()):raise ValueError('Caminho inválido no modelo')
        package.extractall(destination)
    return destination/name
