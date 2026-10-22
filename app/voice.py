"""Offline wake phrase and bounded Portuguese command vocabulary."""
import json
from pathlib import Path
import queue
import re
import sys
import threading
import time
import unicodedata


def normalize(value):
    return re.sub(r'[^a-z0-9 ]', '', ''.join(c for c in unicodedata.normalize('NFD', value.lower()) if unicodedata.category(c) != 'Mn')).strip()


NUMBERS = {'um':1,'uma':1,'dois':2,'duas':2,'tres':3,'quatro':4,'cinco':5,'seis':6,'sete':7,'oito':8,'nove':9,'dez':10,'onze':11,'doze':12,'quinze':15,'vinte':20,'trinta':30,'quarenta':40,'cinquenta':50,'sessenta':60}


def parse(text):
    text = normalize(text)
    if text in ('cancelar desligamento','cancele o desligamento','cancelar agendamento','cancele o agendamento'):
        return ('cancel', None)
    if text in ('estado','status','atualizar estado','qual o estado do pc','uso de memoria','uso da memoria','uso de cpu'):
        return ('status', None)
    if text in ('ligar pc','ligar o pc','ligue o computador','ligar computador'):
        return ('wake', None)
    match = re.fullmatch(r'(?:desligar|desligue|agendar desligamento)(?: o)?(?: pc| computador)? em (.+) (minuto|minutos|hora|horas)', text)
    if match:
        amount = match[1]
        value = int(amount) if amount.isdigit() else sum(NUMBERS.get(w, 0) for w in amount.split() if w != 'e') if all(w in NUMBERS or w == 'e' for w in amount.split()) else 0
        seconds = value * (3600 if match[2].startswith('hora') else 60)
        if 60 <= seconds <= 604800:return ('schedule', seconds)
        return None
    if text in ('desligar pc','desligar o pc','desligue o computador','desligar computador'):
        return ('shutdown', None)
    if text in ('reiniciar pc','reiniciar o pc','reinicie o computador','reiniciar computador'):
        return ('restart', None)
    match = re.fullmatch(r'(?:fechar|feche|encerrar|encerre) (?:(?:o |a )?programa |o |a )?(.+)',text)
    if match:return ('terminate',match[1])
    return None


def matches_process(row, argument):
    pid=re.fullmatch(r'(?:processo|pid) (\d+)',argument)
    if pid:return row['pid']==int(pid[1])
    aliases={'discord':'discord','discordia':'discord','disco':'discord','cromo':'chrome','bloco de notas':'notepad','calculadora':'calculator'}
    return normalize(row['name'].lower().removesuffix('.exe'))==aliases.get(argument,argument)


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
            recognizer=KaldiRecognizer(model,16000)
            audio=queue.Queue(maxsize=32)
            def receive(data,frames,clock,status):
                try:audio.put_nowait(bytes(data))
                except queue.Full:pass
            gate=WakeGate()
            with sd.RawInputStream(samplerate=16000,blocksize=4000,dtype='int16',channels=1,callback=receive):
                self.callback(('state','Diga “Ok Aura” e depois o comando.'))
                while not self.stop.is_set():
                    try:data=audio.get(timeout=.2)
                    except queue.Empty:continue
                    if recognizer.AcceptWaveform(data):
                        result=gate.feed(json.loads(recognizer.Result()).get('text',''))
                        if result:self.callback(result)
        except Exception:
            if not self.stop.is_set():self.callback(('error','Não foi possível acessar o microfone ou carregar o reconhecimento. Confira as permissões de microfone do Windows.'))
