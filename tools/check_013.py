"""Voice boundaries and protected install contract. No mic, UAC or real actions."""
import ast
import os
from pathlib import Path
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
with tempfile.TemporaryDirectory() as temporary:
    os.environ['AURA_DATA_DIR']=temporary
    from app.voice import WakeGate,parse,matches_process
    from app.admin import installation_script
    gate=WakeGate()
    assert gate.feed('desligar o pc',100) is None
    assert gate.feed('Ok Aura',100)==('awake',None)
    assert gate.feed('desligar em trinta minutos',105)==('command',('schedule',1800))
    assert gate.feed('reiniciar pc',106) is None
    assert gate.feed('Ok Aura',110)==('awake',None)
    assert gate.feed('desligar pc',121) is None
    assert gate.feed('Ok Aura encerrar Discord',122)==('command',('terminate','discord'))
    assert gate.feed('não desligue o pc',123) is None
    for phrase in ('não desligar pc','desligar em zero minutos','desligar em 999999999 horas','executar cmd','fechar','desligar pc agora talvez'):
        assert parse(phrase) is None,phrase
    assert parse('cancelar agendamento')==('cancel',None)
    assert parse('desligar em uma hora')==('schedule',3600)
    assert parse('encerrar o programa Discord')==('terminate','discord')
    row={'name':'Discord.exe','pid':123}
    assert matches_process(row,'discord') and matches_process(row,'processo 123')
    assert not matches_process(row,'disc') and not matches_process(row,'processo 124')
    script=installation_script(Path(temporary)/"payload'file.zip",'a'*64,'S-1-5-21-1-2-3-1001')
    assert "payload''file.zip" in script
    for required in ('GetFolderPath','Get-FileHash','Set-Acl','SetOwner','ReparsePoint','ReadAndExecute','-LogonType Interactive -RunLevel Highest',"-Argument '--agent'",'Copy-Item'):
        assert required in script,required
    assert script.index('Get-FileHash')<script.index('ExtractToDirectory')<script.index('Register-ScheduledTask')
    assert len(script.encode('utf-16-le'))*2<30000
    for path in ROOT.rglob('*.py'):
        if '__pycache__' not in path.parts:ast.parse(path.read_text(encoding='utf-8'))
print('PASS: wake phrase, timeout, command allowlist, program identity, protected administrator installation and Python syntax')
