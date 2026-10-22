"""HTTPS agent used by both native clients. Run in the interactive user session."""
import json
import logging
from logging.handlers import RotatingFileHandler
import os
import secrets
import sqlite3
import subprocess
import threading
import time
from contextlib import asynccontextmanager, contextmanager
from collections import defaultdict, deque
from typing import Literal

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from .native_runtime import DATA, PORT, identity
from . import process_icons
from .version import VERSION, BUILD

settings = identity()
from dotenv import dotenv_values
os.environ['AURA_NATIVE']='1'
from . import main as legacy
legacy.TOKEN = settings['token']
DRY_RUN = str(dotenv_values(DATA / 'settings.env').get('DRY_RUN','true')).lower() == 'true'
legacy.DRY_RUN = DRY_RUN
mutex = threading.RLock()
stop = threading.Event()
logger = logging.getLogger('aura.actions')
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = RotatingFileHandler(DATA / 'actions.log', maxBytes=256000, backupCount=3, encoding='utf-8')
    handler.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
    logger.addHandler(handler)


@contextmanager
def db():
    conn = sqlite3.connect(DATA / 'state.sqlite')
    conn.execute('CREATE TABLE IF NOT EXISTS schedule (id INTEGER PRIMARY KEY, at REAL, simulation INTEGER)')
    conn.execute('CREATE TABLE IF NOT EXISTS commands (id TEXT PRIMARY KEY, result TEXT, created REAL)')
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def power(action, simulation):
    if simulation:
        return 'SIMULAÇÃO: ' + action + ' solicitado; nenhuma ação executada.'
    if os.name != 'nt':
        raise HTTPException(400, 'Ação real requer Windows')
    # /t 0 avoids Windows implicitly forcing applications closed for nonzero timeouts.
    try:
        from .admin import system_directory
        subprocess.run([str(system_directory()/'shutdown.exe'), '/s' if action == 'shutdown' else '/r', '/t', '0'],
                       check=True, capture_output=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        raise HTTPException(500, 'O Windows não aceitou a ação')
    return 'Comando enviado ao Windows.'


def worker():
    while not stop.wait(1):
        with mutex, db() as conn:
            row = conn.execute('SELECT at,simulation FROM schedule WHERE id=1').fetchone()
            if row and row[0] <= time.time():
                conn.execute('DELETE FROM schedule WHERE id=1')
                conn.commit()  # Do not replay a power action after a crash.
                try:
                    power('shutdown', bool(row[1]) or DRY_RUN)
                    logger.info('schedule executed simulation=%s', bool(row[1]) or DRY_RUN)
                except HTTPException:
                    logger.error('schedule failed; not retried')


@asynccontextmanager
async def lifespan(app):
    # Missed deadlines are cancelled on restart, never unexpectedly executed at login.
    with db() as conn:
        removed = conn.execute('DELETE FROM schedule WHERE at<=?', (time.time(),)).rowcount
        if removed:
            logger.info('expired schedule cancelled on startup')
    stop.clear()
    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    yield
    stop.set()
    thread.join(timeout=12)


app = FastAPI(title='AURA Native', version=VERSION, docs_url=None,
              redoc_url=None, openapi_url=None, lifespan=lifespan)
attempts = defaultdict(deque)


@app.middleware('http')
async def security(request: Request, call_next):
    address = request.client.host if request.client else 'unknown'
    now = time.monotonic()
    for key in list(attempts):
        while attempts[key] and attempts[key][0] < now - 60:
            attempts[key].popleft()
        if not attempts[key]:
            del attempts[key]
    if len(attempts.get(address, [])) >= 20:
        return JSONResponse({'detail': 'Muitas tentativas. Aguarde um minuto.'}, status_code=429)
    supplied = request.headers.get('authorization', '')
    if not secrets.compare_digest(supplied, 'Bearer ' + settings['token']):
        attempts[address].append(now)
        return JSONResponse({'detail': 'Dispositivo não autorizado'}, status_code=401)
    response = await call_next(request)
    if request.method == 'POST':
        logger.info('action=%s status=%s origin=%s', request.url.path, response.status_code, address)
    return response


@app.get('/api/status')
def status():
    result = legacy.status('Bearer ' + settings['token'])
    with db() as conn:
        row = conn.execute('SELECT at FROM schedule WHERE id=1').fetchone()
    import ctypes
    result.update(shutdown_at=row[0] if row else None, version=VERSION, build=BUILD, api_protocol=1,
                  administrator=bool(ctypes.windll.shell32.IsUserAnAdmin()) if os.name=='nt' else False)
    return result


@app.get('/api/network')
def network():
    return legacy.network_info('Bearer ' + settings['token'])


class Mode(BaseModel):
    dry_run: bool


@app.post('/api/mode')
def mode(req: Mode, request: Request):
    global DRY_RUN
    if not request.client or request.client.host not in ('127.0.0.1', '::1'):
        raise HTTPException(403, 'Altere o modo no aplicativo Windows')
    with mutex:
        (DATA / 'settings.env').write_text('DRY_RUN=' + str(req.dry_run).lower() + '\n', encoding='utf-8')
        DRY_RUN = req.dry_run
        legacy.DRY_RUN = req.dry_run
    return {'message': 'Simulação ativada' if req.dry_run else 'Modo real ativado'}


@app.get('/api/processes')
def processes():
    rows = legacy.processes('Bearer ' + settings['token'])
    for row in rows:
        row['icon_id'] = process_icons.register(row)
    return rows


@app.get('/api/process-icons/{icon_id}')
def process_icon(icon_id: str):
    # Only opaque IDs already registered by process enumeration are accepted.
    if len(icon_id) != 64 or any(c not in '0123456789abcdef' for c in icon_id):
        raise HTTPException(404, 'Ícone indisponível')
    return JSONResponse(process_icons.lookup(icon_id), headers={'Cache-Control': 'no-store'})


class IconBatch(BaseModel):
    ids: list[str] = Field(min_length=1, max_length=16)


@app.post('/api/process-icons')
def process_icon_batch(req: IconBatch):
    if any(len(key) != 64 or any(c not in '0123456789abcdef' for c in key) for key in req.ids):
        raise HTTPException(400, 'Identificador de ícone inválido')
    return JSONResponse({'icons': {key: process_icons.lookup(key) for key in dict.fromkeys(req.ids)}},
                        headers={'Cache-Control': 'no-store'})


class Action(BaseModel):
    action: Literal['shutdown', 'restart']
    confirm: bool = False


class Schedule(BaseModel):
    confirm: bool = False
    delay_seconds: int = Field(ge=1, le=604800)


def once(command_id, operation):
    import uuid
    try:
        uuid.UUID(command_id or '')
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(400, 'Identificador de comando inválido')
    with mutex, db() as conn:
        row = conn.execute('SELECT result FROM commands WHERE id=?', (command_id,)).fetchone()
        if row:
            return json.loads(row[0])
        pending = {'message': 'Comando já recebido; consulte o estado antes de repetir.'}
        conn.execute('INSERT INTO commands VALUES (?,?,?)', (command_id, json.dumps(pending), time.time()))
        conn.execute('DELETE FROM commands WHERE created<?', (time.time()-7*86400,))
        conn.commit()
        result = operation()
        conn.execute('UPDATE commands SET result=? WHERE id=?', (json.dumps(result), command_id))
        return result


@app.post('/api/power')
def do_power(req: Action, x_command_id: str | None = Header(default=None)):
    if req.action == 'shutdown' and not req.confirm:
        raise HTTPException(400, 'Confirme o desligamento')
    return once(x_command_id, lambda: {'message': power(req.action, DRY_RUN)})


@app.post('/api/shutdown')
def schedule(req: Schedule, x_command_id: str | None = Header(default=None)):
    if not req.confirm:
        raise HTTPException(400, 'Confirme o agendamento')
    def apply():
        at = time.time() + req.delay_seconds
        with db() as conn:
            conn.execute('INSERT OR REPLACE INTO schedule VALUES (1,?,?)', (at, int(DRY_RUN)))
        return {'message': 'Desligamento agendado' + (' (simulação)' if DRY_RUN else ''), 'at': at}
    return once(x_command_id, apply)


@app.post('/api/shutdown/cancel')
def cancel(x_command_id: str | None = Header(default=None)):
    def apply():
        with db() as conn:
            conn.execute('DELETE FROM schedule')
        return {'message': 'Agendamento cancelado'}
    return once(x_command_id, apply)


@app.post('/api/processes/terminate')
def terminate(req: legacy.ProcessRequest, x_command_id: str | None = Header(default=None)):
    return once(x_command_id, lambda: legacy.terminate(req, 'Bearer ' + settings['token']))


@app.get('/api/logs')
def logs():
    lines = (DATA / 'actions.log').read_text(encoding='utf-8').splitlines()
    return {'lines': lines[-100:]}


server = None


class UpdatePreparation(BaseModel):
    confirm: bool


@app.post('/api/update/prepare')
def prepare_update(request: Request, action: UpdatePreparation):
    if not action.confirm or not request.client or request.client.host not in ('127.0.0.1', '::1'):
        raise HTTPException(403, 'A atualização deve ser iniciada pela AURA neste PC.')
    if server is None:
        raise HTTPException(503, 'Agente indisponível para atualização.')
    import psutil
    current = server
    def stop_for_update():
        current.should_exit = True
    threading.Timer(.5, stop_for_update).start()
    return {'pid':os.getpid(), 'created_at':psutil.Process().create_time()}


def run():
    global server
    import uvicorn
    config = uvicorn.Config(app, host='0.0.0.0', port=PORT, ssl_certfile=settings['cert'],
                           ssl_keyfile=settings['key'], access_log=False, log_config=None)
    server = uvicorn.Server(config)
    server.run()


if __name__ == '__main__':
    run()
