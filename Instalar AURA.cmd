@echo off
cd /d "%~dp0"
py -3 -m venv .venv
if errorlevel 1 goto erro
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto erro
echo Instalacao concluida. Abra Iniciar AURA.cmd.
pause
exit /b 0
:erro
echo Instalacao interrompida. Confira a mensagem acima.
pause
exit /b 1
