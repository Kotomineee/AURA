"""Offline wake phrase and bounded Portuguese command vocabulary."""
import json
from pathlib import Path
import queue
import re
import sys
import threading
import time
import unicodedata
import math
import struct
from .voice_commands import parse, matches_process, normalize
from .wake_policy import WakePolicy
from collections import deque


class Listener:
    """No recordings persist; callbacks are delivered to the UI's event queue."""
    def __init__(self, callback):
        self.callback=callback
        self.stop=threading.Event()
        self.thread=threading.Thread(target=self.run,daemon=True,name='aura-voice')

    def start(self):self.thread.start()
    def close(self):self.stop.set()

    def run(self):
        try:
            import sounddevice as sd
            from vosk import Model, KaldiRecognizer, SetLogLevel
            SetLogLevel(-1)
            base=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parents[1]))
            model=Model(str(base/'voice-model'))
            english_model=Model(str(base/'voice-model-en'))
            wake=KaldiRecognizer(model,16000,json.dumps(['ok aura','[unk]']))
            wake.SetWords(True)
            verifier=KaldiRecognizer(model,16000);verifier.SetWords(True)
            recognizer=KaldiRecognizer(model,16000)
            english=KaldiRecognizer(english_model,16000)
            audio=queue.Queue(maxsize=32)
            def receive(data,frames,clock,status):
                try:audio.put_nowait(bytes(data))
                except queue.Full:pass
            policy=WakePolicy();history=deque(maxlen=60)
            last_level=0
            english_parts=[]
            def reset_audio():
                wake.Reset();verifier.Reset();recognizer.Reset();english.Reset();history.clear();english_parts.clear()
                while True:
                    try:audio.get_nowait()
                    except queue.Empty:break
            with sd.RawInputStream(samplerate=16000,blocksize=1280,dtype='int16',channels=1,callback=receive):
                self.callback(('state','Diga “Ok Aura”, aguarde o sinal e diga o comando.'))
                while not self.stop.is_set():
                    try:data=audio.get(timeout=.2)
                    except queue.Empty:continue
                    now=time.monotonic()
                    if now-last_level>=.08:
                        samples=struct.unpack('<'+'h'*(len(data)//2),data)
                        level=min(1.,math.sqrt(sum(v*v for v in samples)/max(1,len(samples)))/6000)
                        self.callback(('level',level));last_level=now
                    if policy.expire(now):
                        reset_audio();self.callback(('state','Aguardando “Ok Aura”.'));continue
                    if not policy.until:
                        if now<policy.cooldown:continue
                        history.append(data)
                        final=wake.AcceptWaveform(data)
                        if final:
                            proposal=json.loads(wake.Result())
                            if normalize(proposal.get('text',''))=='ok aura':
                                verifier.Reset()
                                segments=[]
                                for block in history:
                                    if verifier.AcceptWaveform(block):segments.append(json.loads(verifier.Result()))
                                segments.append(json.loads(verifier.FinalResult()))
                                verification={'text':' '.join(r.get('text','') for r in segments).strip(),
                                    'result':[w for r in segments for w in r.get('result',[])]}
                                if policy.arm(proposal,verification,time.monotonic()):
                                    reset_audio();self.callback(('awake',None));continue
                            wake.Reset();history.clear()
                        continue
                    if not policy.accepts_command(now):continue
                    if english.AcceptWaveform(data):english_parts.append(json.loads(english.Result()).get('text',''))
                    if recognizer.AcceptWaveform(data):
                        text=json.loads(recognizer.Result()).get('text','')
                        if normalize(text) in ('','ok','aura','ok aura'):continue
                        command=parse(text)
                        if command and command[0]=='terminate':
                            other=' '.join(english_parts+[json.loads(english.FinalResult()).get('text','')])
                            command=('terminate',{'spoken':command[1],'english':other})
                        if policy.accepts_command(time.monotonic()):self.callback(('command',command))
                        policy.finish(time.monotonic());reset_audio()
        except Exception:
            if not self.stop.is_set():self.callback(('error','Não foi possível acessar o microfone ou carregar o reconhecimento. Confira as permissões de microfone do Windows.'))
