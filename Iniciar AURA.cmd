@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\pythonw.exe (
  echo Execute Instalar AURA.cmd primeiro.
  pause
  exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" "launch_windows.py"
