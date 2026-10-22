"""Exercise the real listener with fake PCM/decoders. Never opens a microphone."""
import copy
import json
from pathlib import Path
import sys
import threading
import types
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.wake_policy import WakePolicy,confirmed_phrase
from app.voice import Listener
from app.tray import Tray,stop_agent
import psutil

def phrase(text='ok aura',confidence=.95):
    return {'text':text,'result':[{'word':'ok','conf':confidence,'start':.1,'end':.4},{'word':'aura','conf':confidence,'start':.45,'end':.9}]}

p=phrase();gate=WakePolicy()
assert not gate.accepts_command(100)
for invalid in ({'partial':'ok aura'},phrase('desligar pc'),phrase('ok aura desligar pc'),phrase(confidence=.6),{},dict(p,result=[])):
    assert not gate.arm(invalid,p,100)
    assert not gate.arm(p,invalid,100)
for field,value in (('conf',float('nan')),('start',-1),('end',20)):
    invalid=copy.deepcopy(p);invalid['result'][0][field]=value;assert not confirmed_phrase(invalid)
assert gate.arm(p,p,100)
assert not gate.accepts_command(100.1) and gate.accepts_command(100.3)
assert not gate.arm(p,p,101)
gate.finish(101);assert not gate.accepts_command(102) and not gate.arm(p,p,101.5)
assert gate.arm(p,p,102) and gate.expire(112)
assert not gate.accepts_command(112) and not gate.arm(p,p,112.5)

def listener_case(candidate,verification,expected,partial=False,expired=False,verification_endpoint=False):
    events=[];recognizers=[];clock=[100.]
    listener=Listener(lambda event:events.append(event))
    # A synthetic clock advances on PCM, independent of machine speed.
    class Recognizer:
        def __init__(self,*args):self.index=len(recognizers);recognizers.append(self);self.count=0
        def SetWords(self,value):assert value
        def Reset(self):pass
        def AcceptWaveform(self,data):
            self.count+=1
            if self.index==0:return not partial
            if self.index==1:return verification_endpoint
            return self.index>=2
        def Result(self):return json.dumps(candidate if self.index==0 else verification if self.index==1 else {'text':'status'})
        def PartialResult(self):raise AssertionError('A partial result must never activate commands')
        def FinalResult(self):return json.dumps(verification if self.index==1 and not verification_endpoint else {'text':''})
    class Stream:
        def __init__(self,**kwargs):self.receive=kwargs['callback']
        def __enter__(self):return self
        def __exit__(self,*args):pass
    class AudioQueue:
        def __init__(self,**kwargs):self.count=0
        def put_nowait(self,data):pass
        def get_nowait(self):raise __import__('queue').Empty
        def get(self,timeout):
            self.count+=1;clock[0]+=11 if expired and self.count==2 else .4
            if self.count>=4:listener.stop.set()
            return bytes(2560)
    fake_vosk=types.SimpleNamespace(Model=lambda *_:object(),KaldiRecognizer=Recognizer,SetLogLevel=lambda *_:None)
    with patch.dict(sys.modules,{'vosk':fake_vosk,'sounddevice':types.SimpleNamespace(RawInputStream=Stream)}),patch('app.voice.queue.Queue',AudioQueue),patch('app.voice.time.monotonic',lambda:clock[0]):listener.run()
    assert not [e for e in events if e[0]=='error'],events
    commands=[e for e in events if e[0]=='command'];awake=[e for e in events if e[0]=='awake']
    assert bool(commands)==expected,(events,expected)
    if expected:assert len(commands)==1 and commands[0][1]==('status',None)
    else:assert recognizers[2].count==0 and recognizers[3].count==0
    return awake

assert not listener_case(phrase('desligar pc'),p,False)
assert not listener_case(p,phrase('aqui agora'),False)
assert not listener_case(p,phrase(confidence=.5),False)
assert not listener_case(p,p,False,partial=True)
assert listener_case(p,p,True)
assert listener_case(p,p,True,verification_endpoint=True)
assert listener_case(p,p,False,expired=True)

class Item:
    def __init__(self,title,action,**kwargs):self.title=title;self.action=action;self.default=kwargs.get('default',False)
class Icon:
    def __init__(self,*args):self.menu=args[-1];self.visible=False;self.stops=0
    def run_detached(self,setup):self.setup=setup
    def stop(self):self.stops+=1
backend=types.SimpleNamespace(Icon=Icon,MenuItem=Item,Menu=lambda *items:items)
requests=[];hidden=[];tray=Tray(requests.append,backend,object())
assert not tray.hide(lambda:hidden.append(True)) and not hidden
tray.icon.setup(tray.icon);assert tray.icon.visible
assert tray.hide(lambda:hidden.append(True))
assert tray.hide(lambda:hidden.append(True))
assert [i.title for i in tray.icon.menu]==['Abrir AURA','Encerrar AURA'] and tray.icon.menu[0].default
thread=threading.Thread(target=lambda:[i.action() for i in tray.icon.menu]);thread.start();thread.join()
assert requests==['open','exit'] # UI consumes these requests on its event queue.
tray.close();tray.close();assert tray.icon.stops==1 and not tray.hide(lambda:hidden.append(True))
early=Tray(requests.append,backend,object());early.close();early.icon.setup(early.icon)
assert early.icon.stops==2 and not early.icon.visible and not early.ready.is_set()
class Broken(Icon):
    def run_detached(self,setup):raise OSError('No tray')
assert not Tray(requests.append,types.SimpleNamespace(Icon=Broken,MenuItem=Item,Menu=backend.Menu),object()).hide(lambda:hidden.append(True))

calls=[]
class Process:
    def create_time(self):return 10.
    def wait(self,timeout):calls.append(('wait',timeout))
def api(path,body):calls.append((path,body));return {'pid':345,'created_at':10.}
stop_agent(api,lambda pid:Process(),999)
assert calls==[('update/prepare',{'confirm':True}),('wait',12)]
calls.clear();stop_agent(lambda *_:{'pid':345,'created_at':11},lambda _:Process(),999);assert not calls
try:stop_agent(lambda *_:{'pid':999,'created_at':10},lambda _:Process(),999);raise AssertionError('Own GUI identity accepted')
except ValueError:pass
print('PASS: final wake confirmation, ambient/partial rejection, real listener gating, timeout, single command, tray readiness/menu/cleanup, authenticated agent exit')
