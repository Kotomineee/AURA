"""Public GitHub Release discovery. Never sends local pairing credentials."""
import json
import hashlib
from pathlib import Path
import re
import urllib.error
import urllib.request
from .version import BUILD

DEFAULT_REPOSITORY = 'Kotomineee/AURA'


def repository(value):
    value = value.strip()
    if not re.fullmatch(r'[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+', value):
        raise ValueError('Informe o repositório público no formato dono/repositorio.')
    return value


def get_json(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'AURA-update-check', 'Accept': 'application/json'})
    with urllib.request.urlopen(request, timeout=12) as response:
        if not response.url.startswith('https://'):
            raise ValueError('Fonte de atualização insegura.')
        raw = response.read(262145)
        if len(raw) > 262144:
            raise ValueError('Resposta de atualização excedeu o limite.')
        return json.loads(raw)


def parse_release(release, manifest, repo, platform='windows', current_build=BUILD):
    repository(repo)
    if release.get('draft') or release.get('prerelease') or not release.get('published_at'):
        raise ValueError('A versão ainda não é estável.')
    build = manifest.get('build')
    version = manifest.get('version', '')
    if type(build) is not int or build < 1 or not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise ValueError('Manifesto de atualização inválido.')
    if release.get('tag_name') != 'v' + version:
        raise ValueError('Versão do manifesto não corresponde à Release.')
    for kind, ending in (('windows','.exe'),('android','.apk')):
        filename = manifest.get('assets',{}).get(kind)
        digest_value = manifest.get('sha256',{}).get(kind,'')
        if not isinstance(filename,str) or not filename.endswith(ending) or not isinstance(digest_value,str) or not re.fullmatch(r'[0-9a-fA-F]{64}',digest_value):
            raise ValueError('A Release ainda não contém os dois aplicativos prontos e verificados.')
        if not any(a.get('name')==filename and a.get('browser_download_url','').startswith(f'https://github.com/{repo}/releases/download/') for a in release.get('assets',[])):
            raise ValueError('A Release ainda não contém os dois aplicativos prontos e verificados.')
    name = manifest.get('assets', {}).get(platform)
    suffix = '.exe' if platform == 'windows' else '.apk'
    asset = next((a for a in release.get('assets', []) if a.get('name') == name), None)
    prefix = f'https://github.com/{repo}/releases/download/'
    if not isinstance(name, str) or not name.endswith(suffix) or not asset or not asset.get('browser_download_url', '').startswith(prefix):
        raise ValueError('Arquivo da plataforma ausente ou inválido.')
    digest = manifest.get('sha256', {}).get(platform, '')
    if not isinstance(digest, str) or not re.fullmatch(r'[0-9a-fA-F]{64}', digest):
        raise ValueError('A Release não contém o SHA-256 válido da atualização.')
    return {'available': build > current_build, 'version': version, 'build': build,
            'url': asset['browser_download_url'], 'sha256': digest.lower()}


def verify_file(path, expected):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            digest.update(block)
    if digest.hexdigest() != expected:
        raise ValueError('A atualização está incompleta ou corrompida. Tente novamente.')


def download(result, destination):
    if not result['available'] or result['build'] <= BUILD:
        raise ValueError('A atualização precisa ser mais recente que a instalada.')
    if not result['url'].startswith(f'https://github.com/{DEFAULT_REPOSITORY}/releases/download/'):
        raise ValueError('Fonte de download inválida.')
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix('.part')
    try:
        request = urllib.request.Request(result['url'], headers={'User-Agent':'AURA-update-download'})
        with urllib.request.urlopen(request, timeout=30) as response, partial.open('wb') as output:
            if not response.url.startswith('https://'):
                raise ValueError('Download inseguro.')
            size = 0
            for block in iter(lambda: response.read(256*1024), b''):
                size += len(block)
                if size > 250*1024*1024:
                    raise ValueError('Atualização excedeu o limite de tamanho.')
                output.write(block)
        verify_file(partial, result['sha256'])
        with partial.open('rb') as stream:
            if stream.read(2) != b'MZ':
                raise ValueError('O arquivo baixado não é um executável Windows.')
        partial.replace(destination)
        return destination
    finally:
        partial.unlink(missing_ok=True)


def check(repo):
    repo = repository(repo)
    try:
        release = get_json(f'https://api.github.com/repos/{repo}/releases/latest')
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise ValueError('Repositório privado, inexistente ou sem Release pública.') from None
        if exc.code in (403, 429):
            raise ValueError('Limite de consultas do GitHub atingido. Tente mais tarde.') from None
        raise
    asset = next((a for a in release.get('assets', []) if a.get('name') == 'aura-update.json'), None)
    prefix = f'https://github.com/{repo}/releases/download/'
    if not asset or not asset.get('browser_download_url', '').startswith(prefix):
        raise ValueError('A Release não contém aura-update.json.')
    return parse_release(release, get_json(asset['browser_download_url']), repo)
