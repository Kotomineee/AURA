"""Download the pinned, redistributable Portuguese offline speech model."""
import hashlib
import os
from pathlib import Path
import urllib.request
import zipfile

SHA256='6e1ce909032e1afa7a88e68a3d628ecafff302bdf195befab308826c395e93b7'


def prepare(destination):
    destination=Path(destination)
    destination.mkdir(parents=True,exist_ok=True)
    archive=Path(os.environ.get('AURA_VOICE_MODEL_ZIP',str(destination/'model.zip')))
    if not archive.exists():
        urllib.request.urlretrieve('https://alphacephei.com/vosk/models/vosk-model-small-pt-0.3.zip',archive)
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=SHA256:raise ValueError('Modelo de voz inválido')
    with zipfile.ZipFile(archive) as package:
        for item in package.infolist():
            if not (destination/item.filename).resolve().is_relative_to(destination.resolve()):raise ValueError('Caminho inválido no modelo')
        package.extractall(destination)
    return destination/'vosk-model-small-pt-0.3'
