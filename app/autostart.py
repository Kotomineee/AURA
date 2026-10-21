"""User-requested Windows logon startup; no administrator or login bypass."""
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import shutil
import subprocess
import sys
from .native_runtime import DATA

RUN_KEY = r'Software\Microsoft\Windows\CurrentVersion\Run'


def command():
    if getattr(sys, 'frozen', False):
        return [str(DATA / 'bin' / 'AURA.exe'), '--startup']
    executable = Path(sys.executable).with_name('pythonw.exe')
    return [str(executable if executable.exists() else sys.executable),
            str(Path(__file__).resolve().parents[1] / 'launch_windows.py'), '--startup']


def configure(enabled):
    if os.name != 'nt':
        raise OSError('Inicialização automática disponível somente no Windows.')
    import winreg
    if enabled and getattr(sys, 'frozen', False):
        source = Path(sys.executable).resolve()
        destination = DATA / 'bin' / 'AURA.exe'
        if source != destination.resolve():
            destination.parent.mkdir(parents=True, exist_ok=True)
            staged = destination.with_suffix('.tmp')
            shutil.copy2(source, staged)
            staged.replace(destination)
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        if enabled:
            winreg.SetValueEx(key, 'AURA', 0, winreg.REG_SZ, subprocess.list2cmdline(command()))
        else:
            try:
                winreg.DeleteValue(key, 'AURA')
            except FileNotFoundError:
                pass


def acquire_agent_lock():
    """A per-session mutex prevents competing agent processes on the same port."""
    if os.name != 'nt':
        return True
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
    kernel.CreateMutexW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.CreateMutexW(None, False, r'Local\AURA-Agent-8765')
    error = ctypes.get_last_error()
    if not handle:
        raise ctypes.WinError(error)
    if error == 183:
        kernel.CloseHandle(handle)
        return False
    # Keep the handle alive for the lifetime of the agent process.
    acquire_agent_lock.handle = handle
    return True
