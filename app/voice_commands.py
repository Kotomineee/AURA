"""Intent parsing and resolution against the current process catalog."""
import re
import unicodedata
from difflib import SequenceMatcher


def normalize(value):
    value=''.join(c for c in unicodedata.normalize('NFD',value.lower()) if unicodedata.category(c)!='Mn')
    return re.sub(r'\s+',' ',re.sub(r'[^a-z0-9 ]',' ',value)).strip()


NUMBERS={'um':1,'uma':1,'dois':2,'duas':2,'tres':3,'quatro':4,'cinco':5,'seis':6,'sete':7,'oito':8,'nove':9,'dez':10,'onze':11,'doze':12,'treze':13,'quatorze':14,'catorze':14,'quinze':15,'dezesseis':16,'dezessete':17,'dezoito':18,'dezenove':19,'vinte':20,'trinta':30,'quarenta':40,'cinquenta':50,'sessenta':60,'setenta':70,'oitenta':80,'noventa':90,'cem':100,'cento':100}
TARGET=r'(?:o |meu |o meu )?(?:pc|computador|windows|sistema|notebook|desktop)'


def parse(value):
    text=normalize(value)
    # Never turn a negated or hypothetical sentence into an action.
    if re.search(r'\b(?:nao|nunca|talvez|se|sem)\b',text):return None
    text=re.sub(r'^(?:aura |por favor |pode |poderia |voce pode |quero que voce |quero |preciso que voce )+','',text)
    text=re.sub(r'(?: por favor| pra mim| para mim| agora)$','',text)
    if re.fullmatch(r'(?:cancelar|cancele|cancela|remover|remova|desmarcar|desmarque)(?: o)? (?:desligamento|agendamento|desligamento agendado)',text):return ('cancel',None)
    if re.fullmatch(r'(?:estado|status|atualizar estado|atualize o estado|como esta (?:o )?(?:pc|computador)|qual o estado do pc|uso (?:de|da) memoria|uso de cpu|mostre (?:o )?(?:estado|status|uso de memoria))',text):return ('status',None)
    power=re.fullmatch(r'(desligar|desligue|desliga|apagar|apague|reiniciar|reinicie|reinicia|reinicializar|ligar|ligue|liga|acordar|acorde)(?: '+TARGET+r')?(?: (?:em|daqui a) (.+?) (minuto|minutos|hora|horas|segundo|segundos))?',text)
    if power:
        verb,amount,unit=power.groups()
        action='restart' if verb.startswith('reini') else 'wake' if verb.startswith(('lig','acord')) else 'shutdown'
        if amount:
            if action!='shutdown':return None
            words=amount.split()
            count=int(amount) if amount.isdigit() else sum(NUMBERS.get(w,0) for w in words) if all(w in NUMBERS or w=='e' for w in words) else 0
            seconds=count*(3600 if unit.startswith('hora') else 60 if unit.startswith('minuto') else 1)
            return ('schedule',seconds) if 1<=seconds<=604800 else None
        return (action,None)
    opening=re.fullmatch(r'(?:abrir|abra|abre|iniciar|inicie|inicia|executar|execute|rodar|rode|open|launch|start) (?:(?:o |a )?(?:app|aplicativo|programa|jogo|plataforma|launcher) |o |a )?(.+)',text)
    if opening:return ('launch',opening[1])
    match=re.fullmatch(r'(?:encerrar|encerre|encerra|fechar|feche|fecha|finalizar|finalize|finaliza|terminar|termine) (?:(?:o |a )?(?:app|aplicativo|programa|processo) |o |a )?(.+)',text)
    if match:
        pid=re.search(r'\b(?:processo|pid) (\d+)$',text)
        return ('terminate','processo '+pid[1] if pid else match[1])
    return None


def process_names(row):
    base=re.sub(r'\.exe$','',row['name'],flags=re.I)
    split=re.sub(r'(?<=[a-z])(?=[A-Z])',' ',base)
    split=re.sub(r'(?<=[A-Z])(?=[A-Z][a-z])',' ',split)
    names={normalize(base),normalize(split)}
    suffix=re.sub(r'(?:client|launcher|helper|application|app|host|service|x64|x86)$','',base,flags=re.I)
    if len(suffix)>=3:names.add(normalize(suffix))
    # A launcher may expose AppNameClient.exe or AppName-Helper.exe.
    core=re.sub(r'\b(?:client|launcher|helper|application|app|host|service|x64|x86)\b','',normalize(split))
    if core.strip():names.add(normalize(core))
    return names


def matches_process(row,argument):
    spoken=argument.get('spoken','') if isinstance(argument,dict) else argument
    english=normalize(argument.get('english','')) if isinstance(argument,dict) else ''
    pid=re.fullmatch(r'(?:processo|pid) (\d+)',spoken)
    if pid:return row['pid']==int(pid[1])
    names=process_names(row)
    return normalize(spoken) in names or any(len(n)>=3 and re.search(r'(?<!\w)'+re.escape(n)+r'(?!\w)',english) for n in names)


def candidates(rows,argument):
    exact=[row for row in rows if matches_process(row,argument)]
    if exact:return exact
    # Approximate matches are suggestions only: the UI always asks for selection
    # and confirmation with the real name and PID before termination.
    spoken=argument.get('spoken','') if isinstance(argument,dict) else argument
    spoken=normalize(spoken).replace(' ','')
    if len(spoken)<4:return []
    ranked=[(max(SequenceMatcher(None,spoken,n.replace(' ','')).ratio() for n in process_names(row)),row) for row in rows]
    return [row for score,row in sorted(ranked,key=lambda item:item[0],reverse=True) if score>=.68][:8]


def selected_reference(argument):
    value=argument.get('spoken','') if isinstance(argument,dict) else argument
    return value in ('esse','este','isso','esse app','este app','esse aplicativo','este aplicativo','esse programa','este programa','esse processo','este processo','selecionado','app selecionado','aplicativo selecionado','programa selecionado')
