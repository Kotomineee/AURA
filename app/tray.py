"""Tray callbacks only enqueue requests; Tk remains on its own thread."""
from pathlib import Path
import sys
import threading


class Tray:
    def __init__(self, dispatch, backend=None, image=None):
        self.dispatch=dispatch;self.ready=threading.Event();self.error=None;self.stopped=False
        self.icon=None
        try:
            if backend is None:
                import pystray as backend
                from PIL import Image
                base=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parents[1]/'tools'))
                image=Image.open(base/'aura.ico').copy()
            self.icon=backend.Icon('AURA',image,'AURA',backend.Menu(
                backend.MenuItem('Abrir AURA',lambda *_:self.dispatch('open'),default=True),
                backend.MenuItem('Encerrar AURA',lambda *_:self.dispatch('exit'))))
            self.icon.run_detached(self._setup)
        except Exception as exc:self.error=exc

    def _setup(self, icon):
        try:
            if self.stopped:
                icon.stop();return
            icon.visible=True;self.ready.set()
        except Exception as exc:self.error=exc

    def hide(self, withdraw):
        if self.stopped or not self.ready.is_set() or self.error:return False
        withdraw();return True

    def close(self):
        if self.stopped:return
        self.stopped=True;self.ready.clear()
        if self.icon:self.icon.stop()


def stop_agent(api, process_factory, own_pid):
    """Authenticated agent stops itself. Never terminate an arbitrary process."""
    import urllib.error
    import psutil
    try:agent=api('update/prepare',{'confirm':True})
    except urllib.error.URLError as exc:
        import errno
        reason=exc.reason
        if getattr(reason,'winerror',None)==10061 or getattr(reason,'errno',None) in (errno.ECONNREFUSED,10061):return
        raise
    pid=int(agent['pid']);created=float(agent['created_at'])
    if pid<=4 or pid==own_pid:raise ValueError('Identidade do agente inválida.')
    try:
        process=process_factory(pid)
        if abs(process.create_time()-created)>.01:return
        process.wait(timeout=12)
    except psutil.NoSuchProcess:pass
