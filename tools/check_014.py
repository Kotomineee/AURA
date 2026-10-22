"""Catalog-based intent checks. No microphone or real process operations."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.voice_commands import parse,candidates,selected_reference
for phrase in ('desligar pc','desligar Windows','desligue o computador','pode desligar meu notebook por favor','quero que voce desligue o sistema'):
    assert parse(phrase)==('shutdown',None),phrase
for phrase in ('reiniciar Windows','reinicie o computador','pode reiniciar o pc'):
    assert parse(phrase)==('restart',None),phrase
assert parse('acorde meu computador')==('wake',None)
assert parse('desliga o windows daqui a vinte e cinco minutos')==('schedule',1500)
assert parse('pode encerrar o app Stove')==('terminate','stove')
assert selected_reference(parse('encerre esse app')[1])
assert parse('encerre o processo 123')==('terminate','processo 123')
for phrase in ('nao desligue windows','talvez reinicie o pc','desligar o pc se necessario','desligue em 999999999 horas','apagar arquivo'):
    assert parse(phrase) is None,phrase
rows=[{'name':'STOVEClient.exe','pid':123},{'name':'ZetaLauncher.exe','pid':124},{'name':'Browser.exe','pid':125}]
assert candidates(rows,{'spoken':'estou','english':'close stove'})==[rows[0]]
assert candidates(rows,{'spoken':'zeta','english':''})==[rows[1]]
assert candidates(rows,{'spoken':'nada','english':'anything'})==[]
assert candidates(rows,'processo 125')==[rows[2]]
print('PASS: Portuguese variations, negations, scheduling, deictic target, dynamic catalogs and English program names')
