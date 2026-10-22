"""Dedicated agent entry point. Never imports the desktop or microphone."""
import os
import sys
from pathlib import Path
if getattr(sys,'frozen',False):
    # All administrator writes stay inside the protected installation.
    os.environ['AURA_DATA_DIR']=str(Path(sys.executable).parent/'state')
from app.autostart import acquire_agent_lock
if __name__ == '__main__' and acquire_agent_lock():
    from app.native_agent import run
    run()
