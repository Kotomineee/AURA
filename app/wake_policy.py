"""Only a complete, independently confirmed wake phrase can arm commands."""
import math
from .voice_commands import normalize


def confirmed_phrase(result):
    if not isinstance(result,dict) or normalize(result.get('text',''))!='ok aura':return False
    words=result.get('result',[])
    if not isinstance(words,list) or len(words)!=2:return False
    try:
        if [normalize(w['word']) for w in words]!=['ok','aura']:return False
        values=[float(w[field]) for w in words for field in ('conf','start','end')]
        if not all(math.isfinite(v) for v in values):return False
        if any(float(w['conf'])<.8 or float(w['conf'])>1 or float(w['start'])<0 or not .06<=float(w['end'])-float(w['start'])<=1.8 for w in words):return False
        if sum(float(w['conf']) for w in words)/2<.85:return False
        return 0<=float(words[1]['start'])-float(words[0]['end'])<=.9 and .25<=float(words[1]['end'])-float(words[0]['start'])<=3
    except (KeyError,TypeError,ValueError):return False


class WakePolicy:
    def __init__(self):self.until=0.;self.ready=0.;self.cooldown=0.
    def arm(self,proposal,verification,now):
        if self.until or now<self.cooldown or not confirmed_phrase(proposal) or not confirmed_phrase(verification):return False
        self.until=now+10;self.ready=now+.25;return True
    def accepts_command(self,now):return self.ready<=now<self.until
    def finish(self,now):self.until=0.;self.ready=0.;self.cooldown=now+.9
    def expire(self,now):
        if self.until and now>=self.until:self.finish(now);return True
        return False
