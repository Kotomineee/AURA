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


class WakeGate:
    def __init__(self):self.deadline=0

    def feed(self, text, now=None):
        now = time.monotonic() if now is None else now
        text = normalize(text)
        match = re.match(r'^(?:ok|okay|oquei) aura(?: |$)',text)
        if match:
            self.deadline=now+10
            remainder=text[match.end():].strip()
            if not remainder:return ('awake',None)
            text=remainder
        elif now >= self.deadline:return None
        if not text:return None
        self.deadline=0
        return ('command',parse(text))


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
            recognizer=KaldiRecognizer(model,16000)
            english=KaldiRecognizer(english_model,16000)
            audio=queue.Queue(maxsize=32)
            def receive(data,frames,clock,status):
                try:audio.put_nowait(bytes(data))
                except queue.Full:pass
            deadline=0
            last_level=0
            english_parts=[]
            with sd.RawInputStream(samplerate=16000,blocksize=1280,dtype='int16',channels=1,callback=receive):
                self.callback(('state','Diga “Ok Aura” e depois o comando.'))
                while not self.stop.is_set():
                    try:data=audio.get(timeout=.2)
                    except queue.Empty:continue
                    now=time.monotonic()
                    if now-last_level>=.08:
                        samples=struct.unpack('<'+'h'*(len(data)//2),data)
                        level=min(1.,math.sqrt(sum(v*v for v in samples)/max(1,len(samples)))/6000)
                        self.callback(('level',level));last_level=now
                    if deadline and now>=deadline:
                        deadline=0;wake.Reset();self.callback(('state','Diga “Ok Aura”.'))
                    if not deadline:
                        final=wake.AcceptWaveform(data)
                        hypothesis=json.loads(wake.Result() if final else wake.PartialResult()).get('text' if final else 'partial','')
                        if normalize(hypothesis)=='ok aura':
                            deadline=now+10;recognizer.Reset();english.Reset();english_parts.clear();self.callback(('awake',None))
                        continue
                    if english.AcceptWaveform(data):english_parts.append(json.loads(english.Result()).get('text',''))
                    if recognizer.AcceptWaveform(data):
                        text=json.loads(recognizer.Result()).get('text','')
                        if normalize(text) in ('','ok','aura','ok aura'):continue
                        command=parse(text)
                        if command and command[0]=='terminate':
                            other=' '.join(english_parts+[json.loads(english.FinalResult()).get('text','')])
                            command=('terminate',{'spoken':command[1],'english':other})
                        self.callback(('command',command));deadline=0;wake.Reset()
        except Exception:
            if not self.stop.is_set():self.callback(('error','Não foi possível acessar o microfone ou carregar o reconhecimento. Confira as permissões de microfone do Windows.'))
