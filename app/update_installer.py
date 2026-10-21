"""Separate updater process. Only swaps the verified app, never user data."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid
import psutil
from .native_runtime import DATA
from .updates import verify_file
from .version import BUILD


def wait_process(pid, created_at, timeout=60):
    try:
        process = psutil.Process(pid)
        if abs(process.create_time() - created_at) > .01:
            return
        process.wait(timeout=timeout)
    except psutil.NoSuchProcess:
        pass


def launch(args):
    return subprocess.Popen(args, cwd=DATA, stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS)


def prepare(result, agent):
    if not getattr(sys, 'frozen', False):
        raise ValueError('A atualização automática requer o aplicativo EXE instalado.')
    folder = DATA / 'updates'
    staged = folder / 'payload.exe'
    verify_file(staged, result['sha256'])
    for old_helper in folder.glob('helper-*.exe'):
        try:
            old_helper.unlink()
        except OSError:
            pass
    identifier = uuid.uuid4().hex
    helper = folder / ('helper-' + identifier + '.exe')
    shutil.copy2(sys.executable, helper)
    job_path = folder / ('job-' + identifier + '.json')
    job = {'target':str(Path(sys.executable).resolve()), 'sha256':result['sha256'],
           'build':result['build'], 'parent_pid':os.getpid(),
           'parent_created':psutil.Process().create_time(), 'agent':agent}
    job_path.write_text(json.dumps(job), encoding='utf-8')
    return helper, job_path


def apply(job_path, wait=wait_process, start=launch, retries=60):
    folder = (DATA / 'updates').resolve()
    job_path = Path(job_path).resolve()
    if job_path.parent != folder or not job_path.name.startswith('job-') or job_path.suffix != '.json':
        raise ValueError('Trabalho de atualização inválido.')
    job = json.loads(job_path.read_text(encoding='utf-8'))
    staged = folder / 'payload.exe'
    target = Path(job['target']).resolve()
    if target.suffix.lower() != '.exe' or target.is_relative_to(folder) or job['build'] <= BUILD:
        raise ValueError('Destino ou versão de atualização inválidos.')
    verify_file(staged, job['sha256'])
    backup = target.with_name(target.name + '.previous')
    pending = target.with_name(target.name + '.new')
    report = folder / 'result.json'
    ready = job_path.with_suffix('.ready.json')
    waits_done = False
    recovered = False
    child = None
    try:
        wait(job['parent_pid'], job['parent_created'])
        if job.get('agent'):
            wait(job['agent']['pid'], job['agent']['created_at'])
        waits_done = True
        # The onefile bootloader can hold the EXE briefly after its child exits.
        for attempt in range(retries):
            try:
                shutil.copy2(staged, pending)
                verify_file(pending, job['sha256'])
                os.replace(target, backup)
                try:
                    os.replace(pending, target)
                except OSError:
                    os.replace(backup, target)
                    raise
                break
            except PermissionError:
                if attempt + 1 == retries:
                    raise
                time.sleep(1)
        try:
            child = start([str(target), '--update-ready', str(ready)])
        except OSError:
            os.replace(backup, target)
            start([str(target)])
            recovered = True
            raise
        for _ in range(60):
            try:
                value = json.loads(ready.read_text(encoding='utf-8'))
                if value.get('build') == job['build']:
                    report.write_text(json.dumps({'state':'installed','build':job['build']}), encoding='utf-8')
                    try:
                        backup.unlink(missing_ok=True)
                        staged.unlink(missing_ok=True)
                    except OSError:
                        pass
                    return 'installed'
            except (OSError, ValueError):
                pass
            if child.poll() is not None:
                os.replace(backup, target)
                start([str(target)])
                recovered = True
                raise RuntimeError('A nova versão não iniciou. A versão anterior foi restaurada.')
            time.sleep(1)
        # Do not kill a running application on a slow machine. Preserve recovery.
        report.write_text(json.dumps({'state':'awaiting_health','build':job['build'],'backup':str(backup)}), encoding='utf-8')
        return 'awaiting_health'
    except Exception:
        if waits_done and child is None and not recovered:
            try:
                if not target.exists() and backup.exists():
                    os.replace(backup, target)
                if target.exists():
                    start([str(target)])
            except OSError:
                pass
        report.write_text(json.dumps({'state':'failed','backup':str(backup)}), encoding='utf-8')
        raise
    finally:
        pending.unlink(missing_ok=True)


def mark_ready(path):
    path = Path(path).resolve()
    if path.parent == (DATA / 'updates').resolve() and path.name.endswith('.ready.json'):
        path.write_text(json.dumps({'build':BUILD}), encoding='utf-8')
