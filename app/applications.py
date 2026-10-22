"""Per-user installed-app catalog. Only the unelevated desktop opens targets."""
import configparser
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import threading
import time
from urllib.parse import quote
from .voice_commands import normalize, process_names


def target_valid(kind,target):
    if not isinstance(target,str) or not target or '\x00' in target:return False
    if kind=='file':
        p=Path(target)
        return p.is_absolute() and p.suffix.lower() in ('.exe','.lnk') and p.is_file() and not str(p).startswith(('\\\\','//'))
    if kind=='steam':return bool(re.fullmatch(r'steam://rungameid/[0-9]{1,12}',target))
    if kind=='epic':return bool(re.fullmatch(r'com\.epicgames\.launcher://apps/[A-Za-z0-9%_.:-]+\?action=launch&silent=true',target))
    if kind=='store':return bool(re.fullmatch(r'[A-Za-z0-9._-]+![A-Za-z0-9._-]+',target))
    return False


def entry(name,kind,target,source,aliases=()):
    name=str(name).strip()[:160]
    if not name or normalize(name).startswith(('uninstall','unins','desinstal','remove ')) or re.search(r'\bredistributables?\b',normalize(name)) or not target_valid(kind,target):return None
    key=hashlib.sha256((kind+'\0'+os.path.normcase(target)).encode('utf-8')).hexdigest()
    names=(process_names({'name':name})|{normalize(x) for x in aliases if isinstance(x,str) and x.strip()})-{''}
    names={n[:160] for n in names}
    if not names:names={name.casefold()}
    return {'id':key,'name':name,'source':source,'aliases':sorted(names)[:16],'kind':kind,'target':target}


def public(row):return {k:row[k] for k in ('id','name','source','aliases')}


def match(rows,argument):
    """Exact catalog name first. Fuzzy results always need explicit selection."""
    from difflib import SequenceMatcher
    spoken=argument.get('spoken','') if isinstance(argument,dict) else argument
    english=normalize(argument.get('english','')) if isinstance(argument,dict) else ''
    spoken=normalize(spoken)
    exact=[r for r in rows if spoken in r['aliases']]
    if exact:return exact,True
    english_matches=[r for r in rows if any(len(n)>=3 and re.search(r'(?<!\w)'+re.escape(n)+r'(?!\w)',english) for n in r['aliases'])]
    if english_matches:return english_matches,False
    if len(spoken)<3:return [],False
    scores=[(max(SequenceMatcher(None,spoken.replace(' ',''),n.replace(' ','')).ratio() for n in r['aliases']),r) for r in rows]
    return [r for score,r in sorted(scores,key=lambda x:x[0],reverse=True) if score>=.58][:8],False


def known_folders():
    if os.name!='nt':return []
    result=[]
    for csidl in (2,23,16,25): # Programs, Common Programs, Desktop, Public Desktop
        buf=ctypes.create_unicode_buffer(32768)
        if ctypes.windll.shell32.SHGetFolderPathW(None,csidl,None,0,buf)==0 and buf.value:result.append(Path(buf.value))
    return result


def shortcut_entries(folders):
    inspected=0
    for folder in folders:
        if not folder.is_dir():continue
        for parent,dirs,files in os.walk(folder,followlinks=False):
            dirs[:]=[d for d in dirs if not Path(parent,d).is_symlink() and not Path(parent,d).is_junction() and len(Path(parent,d).relative_to(folder).parts)<10]
            for filename in files:
                inspected+=1
                if inspected>20000:return
                path=Path(parent,filename)
                if path.suffix.lower()=='.lnk':
                    row=entry(path.stem,'file',str(path),'Atalho do Windows')
                elif path.suffix.lower()=='.url':
                    try:
                        parser=configparser.ConfigParser(interpolation=None);parser.read(path,encoding='utf-8-sig')
                        target=parser.get('InternetShortcut','URL');row=entry(path.stem,'steam',target,'Steam')
                    except (OSError,ValueError,configparser.Error):continue
                else:continue
                if row:yield row


def registry_entries():
    if os.name!='nt':return
    import winreg
    for hive in (winreg.HKEY_CURRENT_USER,winreg.HKEY_LOCAL_MACHINE):
        for view in (winreg.KEY_WOW64_64KEY,winreg.KEY_WOW64_32KEY):
            try:
                with winreg.OpenKey(hive,r'Software\Microsoft\Windows\CurrentVersion\App Paths',0,winreg.KEY_READ|view) as key:
                    for index in range(winreg.QueryInfoKey(key)[0]):
                        try:
                            name=winreg.EnumKey(key,index)
                            with winreg.OpenKey(key,name) as app:target=os.path.expandvars(winreg.QueryValue(app,None)).strip().strip('"')
                            if re.search(r'unins|uninstall|setup|crash|updat|helper|service|report',Path(target).stem,re.I):continue
                            row=entry(Path(name).stem,'file',target,'Registro do Windows')
                            if row:yield row
                        except OSError:continue
            except OSError:continue


def steam_roots():
    roots=[]
    if os.name=='nt':
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r'Software\Valve\Steam') as key:roots.append(Path(winreg.QueryValueEx(key,'SteamPath')[0]))
        except OSError:pass
    for variable in ('PROGRAMFILES(X86)','PROGRAMFILES'):
        if os.getenv(variable):roots.append(Path(os.environ[variable])/'Steam')
    return roots


def registered_install_entries():
    """Use installer names only when a plausible interactive EXE is present."""
    if os.name!='nt':return
    import winreg
    for hive in (winreg.HKEY_CURRENT_USER,winreg.HKEY_LOCAL_MACHINE):
        for view in (winreg.KEY_WOW64_64KEY,winreg.KEY_WOW64_32KEY):
            try:
                with winreg.OpenKey(hive,r'Software\Microsoft\Windows\CurrentVersion\Uninstall',0,winreg.KEY_READ|view) as key:
                    for index in range(winreg.QueryInfoKey(key)[0]):
                        try:
                            with winreg.OpenKey(key,winreg.EnumKey(key,index)) as app:
                                name=winreg.QueryValueEx(app,'DisplayName')[0];location=winreg.QueryValueEx(app,'InstallLocation')[0]
                            if not isinstance(name,str) or not isinstance(location,str) or not location.strip():continue
                            folder=Path(os.path.expandvars(location.strip().strip('"')))
                            if not folder.is_absolute() or not folder.is_dir() or str(folder).startswith(('\\\\','//')):continue
                            choices=[p for p in folder.glob('*.exe') if not re.search(r'unins|uninstall|setup|repair|crash|updat|helper|service|report',p.stem,re.I)]
                            names=process_names({'name':name})
                            preferred=[p for p in choices if process_names({'name':p.stem})&names or normalize(p.stem) in ('launcher','start','client')]
                            for path in preferred or (choices if len(choices)==1 else []):
                                row=entry(name,'file',str(path),'Aplicativo instalado',process_names({'name':path.stem}))
                                if row:yield row
                        except OSError:continue
            except OSError:continue


def vdf_values(text):
    return {m[1]:m[2].replace('\\\\','\\').replace('\\"','"') for m in re.finditer(r'"([^"\n]+)"\s+"((?:\\.|[^"\\])*)"',text)}


def steam_entries(roots):
    libraries=set(roots)
    for root in roots:
        try:
            content=(root/'steamapps/libraryfolders.vdf').read_text(encoding='utf-8')
            for m in re.finditer(r'"path"\s+"((?:\\.|[^"\\])*)"',content):libraries.add(Path(m[1].replace('\\\\','\\')))
        except (OSError,UnicodeError):pass
    for root in libraries:
        for manifest in (root/'steamapps').glob('appmanifest_*.acf'):
            try:
                if manifest.stat().st_size>1048576:continue
                values=vdf_values(manifest.read_text(encoding='utf-8'))
                appid=values.get('appid','');install=values.get('installdir','')
                if not re.fullmatch('[0-9]{1,12}',appid) or not install or Path(install).name!=install or not (root/'steamapps/common'/install).is_dir():continue
                row=entry(values.get('name',install),'steam','steam://rungameid/'+appid,'Steam')
                if row:yield row
            except (OSError,UnicodeError):continue


def epic_entries(folder):
    for manifest in folder.glob('*.item'):
        try:
            if manifest.stat().st_size>1048576:continue
            value=json.loads(manifest.read_text(encoding='utf-8-sig'))
            if value.get('bIsIncompleteInstall') or not Path(value['InstallLocation']).is_dir():continue
            launch=':'.join(value[k] for k in ('CatalogNamespace','CatalogItemId','AppName'))
            row=entry(value['DisplayName'],'epic','com.epicgames.launcher://apps/'+quote(launch,safe=':')+'?action=launch&silent=true','Epic Games')
            if row:yield row
        except (OSError,ValueError,KeyError,TypeError):continue


def store_entries():
    if os.name!='nt':return
    from .admin import system_directory
    # Constant script; never interpolate a spoken name or path into PowerShell.
    script="[Console]::OutputEncoding=[Text.UTF8Encoding]::new(); @(Get-StartApps | Select-Object Name,AppID) | ConvertTo-Json -Compress"
    try:
        result=subprocess.run([str(system_directory()/'WindowsPowerShell/v1.0/powershell.exe'),'-NoProfile','-NonInteractive','-Command',script],capture_output=True,timeout=25,creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode or len(result.stdout)>2097152:return
        values=json.loads(result.stdout.decode('utf-8-sig'))
        for value in values if isinstance(values,list) else [values]:
            row=entry(value.get('Name',''),'store',value.get('AppID',''),'Microsoft Store')
            if row:yield row
    except (OSError,ValueError,subprocess.SubprocessError):return


def shortcut_targets(rows):
    if os.name!='nt':return {}
    links=[r['target'] for r in rows if r['kind']=='file' and Path(r['target']).suffix.lower()=='.lnk']
    if not links:return {}
    from .admin import system_directory
    script="[Console]::OutputEncoding=[Text.UTF8Encoding]::new(); $w=New-Object -ComObject WScript.Shell; $paths=ConvertFrom-Json ([Console]::In.ReadToEnd()); @($paths | ForEach-Object {try {$s=$w.CreateShortcut($_); [pscustomobject]@{link=$_;target=$s.TargetPath;arguments=$s.Arguments}} catch {}}) | ConvertTo-Json -Compress"
    try:
        result=subprocess.run([str(system_directory()/'WindowsPowerShell/v1.0/powershell.exe'),'-NoProfile','-NonInteractive','-Command',script],input=json.dumps(links).encode('utf-8'),capture_output=True,timeout=25,creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode or len(result.stdout)>4194304:return {}
        values=json.loads(result.stdout.decode('utf-8-sig'));values=values if isinstance(values,list) else [values]
        return {v['link']:(v['target'],v.get('arguments','')) for v in values if isinstance(v,dict) and v.get('link') in links and isinstance(v.get('target'),str)}
    except (OSError,ValueError,subprocess.SubprocessError):return {}


def deduplicate(rows,targets):
    """Collapse duplicate registrations of the same target, preserving LNK args."""
    result={};seen={}
    ordered=sorted(rows.values(),key=lambda r:0 if r['source']=='Adicionado por você' else 1 if r['kind']=='file' and Path(r['target']).suffix.lower()=='.lnk' else 2)
    for row in ordered:
        resolved=targets.get(row['target']) if row['kind']=='file' else None
        if resolved:signature=('file',os.path.normcase(resolved[0]),resolved[1])
        elif row['kind']=='file' and Path(row['target']).suffix.lower()=='.exe':signature=('file',os.path.normcase(row['target']),'')
        else:signature=(row['kind'],os.path.normcase(row['target']),'')
        existing=next((r for r in seen.get(signature,[]) if set(r['aliases'])&set(row['aliases'])),None)
        if existing:existing['aliases']=sorted(set(existing['aliases'])|set(row['aliases']))[:16]
        else:seen.setdefault(signature,[]).append(row);result[row['id']]=row
    return result


class Catalog:
    def __init__(self,folder):self.folder=Path(folder);self.rows={};self.lock=threading.RLock()
    def preferences(self):
        try:
            value=json.loads((self.folder/'applications.json').read_text(encoding='utf-8'))
            return value if isinstance(value,dict) else {}
        except (OSError,ValueError):return {}
    def save(self,value):
        self.folder.mkdir(parents=True,exist_ok=True);temporary=self.folder/'applications.tmp'
        temporary.write_text(json.dumps(value,ensure_ascii=False),encoding='utf-8');temporary.replace(self.folder/'applications.json')
    def add(self,name,path,alias=''):
        row=entry(name,'file',str(Path(path).resolve()),'Adicionado por você',[alias])
        if not row:raise ValueError('Selecione um executável EXE ou atalho LNK existente neste PC.')
        with self.lock:
            prefs=self.preferences();manual=prefs.get('manual',[])
            prefs['manual']=[r for r in manual if r.get('id')!=row['id']]+[row];self.save(prefs)
        return row
    def alias(self,key,value):
        if not normalize(value) or len(value)>100:raise ValueError('Informe um nome de voz de até 100 caracteres.')
        with self.lock:
            if key not in self.rows:raise ValueError('Aplicativo indisponível; atualize a lista.')
            prefs=self.preferences();prefs.setdefault('aliases',{})[key]=normalize(value);self.save(prefs)
    def refresh(self,providers=None,resolver=None):
        native=providers is None
        providers=providers if providers is not None else [lambda:shortcut_entries(known_folders()),registry_entries,registered_install_entries,lambda:steam_entries(steam_roots()),lambda:epic_entries(Path(os.getenv('PROGRAMDATA','C:/ProgramData'))/'Epic/EpicGamesLauncher/Data/Manifests'),store_entries]
        rows={}
        for provider in providers:
            try:
                for row in provider():
                    if row and len(rows)<5000:rows.setdefault(row['id'],row)
            except (OSError,ValueError):continue
        with self.lock:
            prefs=self.preferences()
            for row in prefs.get('manual',[]):
                if isinstance(row,dict):
                    fresh=entry(row.get('name',''),'file',row.get('target',''),'Adicionado por você',row.get('aliases',[]))
                    if fresh:rows[fresh['id']]=fresh
            for key,alias in prefs.get('aliases',{}).items():
                if key in rows and isinstance(alias,str) and normalize(alias):rows[key]['aliases']=sorted(set(rows[key]['aliases'])|{normalize(alias)})[:16]
        # Resolving shell shortcuts may take seconds; never block opening or
        # heartbeat delivery while waiting for the Windows inventory helper.
        rows=deduplicate(rows,(resolver or shortcut_targets)(list(rows.values())) if native or resolver else {})
        with self.lock:
            self.rows=rows
            return [public(r) for r in sorted(rows.values(),key=lambda r:r['name'].casefold())]
    def public(self):
        with self.lock:return [public(r) for r in self.rows.values()]
    def launch(self,key,opener=None,is_elevated=None,deadline=None):
        if is_elevated is None:is_elevated=bool(ctypes.windll.shell32.IsUserAnAdmin()) if os.name=='nt' else False
        if is_elevated:raise OSError('Abra a interface da AURA sem “Executar como administrador” para abrir programas na sua sessão normal.')
        with self.lock:row=dict(self.rows.get(key,{}))
        if not row or not target_valid(row['kind'],row['target']):raise ValueError('O aplicativo não está mais disponível. Atualize a lista no Windows.')
        target='shell:AppsFolder\\'+row['target'] if row['kind']=='store' else row['target']
        if deadline is not None and time.monotonic()>=deadline:raise ValueError('A solicitação expirou; tente novamente.')
        (opener or os.startfile)(target)
        return 'Abertura solicitada ao Windows: '+row['name']+'.'
