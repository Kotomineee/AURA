import os
import subprocess
from typing import Literal
import getpass
import threading
import time
from pathlib import Path

import psutil
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

load_dotenv()
ROOT = Path(__file__).resolve().parent
TOKEN = os.getenv("ASSISTANT_TOKEN", "")
DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"
app = FastAPI(title="AURA", docs_url=None, redoc_url=None)
shutdown_timer = None
shutdown_at = None
lock = threading.Lock()


def authorize(authorization: str | None):
    if not TOKEN or TOKEN == "troque-por-um-token-longo-e-aleatorio":
        raise HTTPException(503, "Configure ASSISTANT_TOKEN no arquivo .env")
    import secrets
    if not authorization or not secrets.compare_digest(authorization, f"Bearer {TOKEN}"):
        raise HTTPException(401, "Não autorizado")


class ProcessRequest(BaseModel):
    pid: int = Field(gt=0)
    name: str = Field(min_length=1)
    created_at: float | None = None


class ShutdownRequest(BaseModel):
    confirm: bool
    delay_seconds: int = Field(ge=0, le=604800)


@app.get("/")
def index():
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/api/status")
def status(authorization: str | None = Header(default=None)):
    authorize(authorization)
    mem = psutil.virtual_memory()
    return {
        "cpu": psutil.cpu_percent(interval=0.1),
        "ram": mem.percent,
        "ram_used_gb": round(mem.used / 1024**3, 2),
        "ram_total_gb": round(mem.total / 1024**3, 2),
        "dry_run": DRY_RUN,
        "hostname": os.getenv("COMPUTERNAME", "PC"),
        "shutdown_at": shutdown_at,
    }


# Política conservadora: só permitir aplicativos do usuário fora da pasta Windows.
# A lista de nomes é uma camada extra, não a única verificação.
PROTECTED_NAMES = {
    "system", "system idle process", "registry", "secure system", "memory compression",
    "smss.exe", "csrss.exe", "wininit.exe", "services.exe", "lsass.exe",
    "lsaiso.exe", "winlogon.exe", "svchost.exe", "explorer.exe", "dwm.exe",
    "fontdrvhost.exe", "sihost.exe", "taskhostw.exe", "spoolsv.exe",
    "audiodg.exe", "searchindexer.exe", "searchhost.exe", "startmenuexperiencehost.exe",
    "runtimebroker.exe", "shellexperiencehost.exe", "ctfmon.exe", "conhost.exe",
    "dllhost.exe", "wudfhost.exe", "wmiprvse.exe", "securityhealthservice.exe",
    "msmpeng.exe", "msmpsvc.exe", "trustedinstaller.exe", "tiworker.exe",
    "python.exe", "pythonw.exe", "powershell.exe", "pwsh.exe", "cmd.exe",
}


def protected_process(p: psutil.Process) -> bool:
    # Se a identidade não puder ser confirmada, não permitir encerrar.
    try:
        if p.pid <= 4 or p.pid == os.getpid():
            return True
        name = p.name().casefold()
        if name in PROTECTED_NAMES:
            return True
        # Preserva a árvore de processos que iniciou a AURA.
        parent = psutil.Process(os.getpid())
        while parent is not None:
            if p.pid == parent.pid:
                return True
            parent = parent.parent()
        if os.name != "nt":
            return True  # O gerenciamento de processos deste protótipo é para Windows.
        exe = p.exe()
        owner = p.username()
        if not exe or not owner:
            return True
        windows_dir = Path(os.environ.get("WINDIR", r"C:\Windows"))
        try:
            if Path(exe).resolve().is_relative_to(windows_dir.resolve()):
                return True
        except (OSError, ValueError):
            return True
        current_user = getpass.getuser().casefold()
        process_user = owner.rsplit("\\", 1)[-1].casefold()
        if process_user != current_user:
            return True
        return False
    except (psutil.Error, OSError, ValueError):
        return True


@app.get("/api/processes")
def processes(authorization: str | None = Header(default=None)):
    authorize(authorization)
    result = []
    for p in psutil.process_iter(["pid", "name", "memory_info"]):
        try:
            if protected_process(p):
                continue
            d = p.info
            result.append({
                "pid": d["pid"],
                "name": d["name"],
                "ram_mb": round(d["memory_info"].rss / 1024**2, 1)
                if d["memory_info"] else 0,
                "created_at": p.create_time(),
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return sorted(result, key=lambda x: x["ram_mb"], reverse=True)[:150]


@app.post("/api/processes/terminate")
def terminate(req: ProcessRequest, authorization: str | None = Header(default=None)):
    authorize(authorization)
    try:
        p = psutil.Process(req.pid)
        name = p.name()
    except psutil.NoSuchProcess:
        raise HTTPException(404, "Processo não encontrado")
    except psutil.AccessDenied:
        raise HTTPException(403, "Sem permissão para consultar processo")
    if name.lower() != req.name.lower():
        raise HTTPException(409, "O processo mudou; atualize a lista")
    if protected_process(p):
        raise HTTPException(403, "Processo protegido ou identidade não verificável")
    if req.created_at is None or abs(p.create_time() - req.created_at) > 0.01:
        raise HTTPException(409, "O PID foi reutilizado ou a lista está desatualizada")
    if DRY_RUN:
        return {"message": f"SIMULAÇÃO: encerraria {name} (PID {p.pid})"}
    try:
        p.terminate()
    except (psutil.AccessDenied, psutil.NoSuchProcess):
        raise HTTPException(403, "Não foi possível encerrar o processo")
    return {"message": f"Solicitado encerramento de {name} (PID {p.pid})"}


def shutdown():
    global shutdown_timer, shutdown_at
    with lock:
        shutdown_timer = None
        shutdown_at = None
    if not DRY_RUN and os.name == "nt":
        import ctypes
        ctypes.windll.user32.ExitWindowsEx(0x00000008, 0)


@app.post("/api/shutdown")
def schedule_shutdown(req: ShutdownRequest, authorization: str | None = Header(default=None)):
    global shutdown_timer, shutdown_at
    authorize(authorization)
    if not req.confirm:
        raise HTTPException(400, "Confirmação obrigatória")
    if os.name != "nt" and not DRY_RUN:
        raise HTTPException(400, "Desligamento real requer Windows")
    with lock:
        if shutdown_timer:
            shutdown_timer.cancel()
        shutdown_at = int(time.time() + req.delay_seconds)
        shutdown_timer = threading.Timer(req.delay_seconds, shutdown)
        shutdown_timer.daemon = True
        shutdown_timer.start()
    return {
        "message": "Desligamento simulado agendado" if DRY_RUN else "Desligamento agendado",
        "at": shutdown_at,
    }


@app.post("/api/shutdown/cancel")
def cancel_shutdown(authorization: str | None = Header(default=None)):
    global shutdown_timer, shutdown_at
    authorize(authorization)
    with lock:
        if shutdown_timer:
            shutdown_timer.cancel()
        shutdown_timer = None
        shutdown_at = None
    return {"message": "Agendamento cancelado"}


class PowerRequest(BaseModel):
    action: Literal["shutdown", "restart"]
    confirm: bool


@app.post("/api/power")
def power_action(req: PowerRequest, authorization: str | None = Header(default=None)):
    authorize(authorization)
    if not req.confirm:
        raise HTTPException(400, "Confirmação obrigatória")
    if DRY_RUN:
        verb = "desligaria" if req.action == "shutdown" else "reiniciaria"
        return {"message": f"SIMULAÇÃO: {verb} o computador"}
    if os.name != "nt":
        raise HTTPException(400, "Controle de energia real requer Windows")
    # /t 15 oferece uma janela para cancelar com shutdown /a.
    args = ["shutdown", "/s" if req.action == "shutdown" else "/r", "/t", "15"]
    try:
        subprocess.run(args, check=True, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        raise HTTPException(500, "O Windows não aceitou o comando de energia")
    return {"message": "Comando enviado ao Windows. Ação em 15 segundos."}