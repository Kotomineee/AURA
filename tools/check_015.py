"""Grouping, partial termination, conditional updates and truncated downloads."""
import hashlib,io,json,sys,urllib.error,tempfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import process_groups as groups,updates
rows=[{'pid':1,'name':'chrome.exe','created_at':1.,'ram_mb':10.,'icon_id':'a'*64},
      {'pid':2,'name':'chrome.exe','created_at':2.,'ram_mb':20.,'icon_id':'a'*64},
      {'pid':3,'name':'chrome.exe','created_at':3.,'ram_mb':40.,'icon_id':'b'*64},
      {'pid':4,'name':'unknown.exe','created_at':4.,'ram_mb':2.,'icon_id':None},
      {'pid':5,'name':'unknown.exe','created_at':5.,'ram_mb':3.,'icon_id':None}]
result=groups.group(rows)
assert len(result)==4
chrome=next(r for r in result if r['pid']==1)
assert chrome['ram_mb']==30 and chrome['process_count']==2
assert groups.contains(chrome,'2') and groups.contains(chrome,'CHROME')
assert groups.group(result)==result and groups.group(rows+rows)==result
sent=[]
def sender(payload):
    sent.append(payload)
    if payload['pid']==1:raise RuntimeError('PID changed')
    return {'message':'SIMULAÇÃO: encerraria processo'}
report=groups.terminate_snapshot(chrome,sender)
assert report['sent']==1 and report['failed']==1
assert sent==[{k:row[k] for k in ('pid','name','created_at')} for row in reversed(rows[:2])]
assert all('members' not in payload for payload in sent)
class Response(io.BytesIO):
    url='https://api.github.com/repos/example/repo/releases/latest'
    headers={'ETag':'"version-1"'}
url=Response.url
updates._json_cache.clear()
with patch.object(updates.urllib.request,'urlopen',return_value=Response(b'{"id":1}')):
    assert updates.get_json(url)=={'id':1}
with patch.object(updates.urllib.request,'urlopen',side_effect=urllib.error.HTTPError(url,304,'Not modified',{},None)) as get:
    assert updates.get_json(url)=={'id':1}
    assert get.call_args.args[0].get_header('If-none-match')=='"version-1"'
with patch.object(updates.urllib.request,'urlopen',side_effect=[urllib.error.URLError('temporary'),Response(b'{"id":2}')]),patch.object(updates.time,'sleep'):
    assert updates.get_json(url)=={'id':2}
with tempfile.TemporaryDirectory() as folder:
    payload=b'MZ'+b'x'*100
    result={'available':True,'build':999,'url':'https://github.com/Kotomineee/AURA/releases/download/v9.9.9/a.exe','sha256':hashlib.sha256(payload).hexdigest(),'size':len(payload)}
    target=Path(folder)/'payload.exe';target.write_bytes(b'old')
    progress=[]
    with patch.object(updates.urllib.request,'urlopen',return_value=Response(payload)):
        updates.download(result,target,progress=lambda done,total:progress.append((done,total)))
    assert progress[-1]==(len(payload),len(payload))
    with patch.object(updates.urllib.request,'urlopen',return_value=Response(payload[:-1])):
        try:updates.download(result,target)
        except ValueError:pass
        else:raise AssertionError('Truncated download accepted')
    assert target.read_bytes()==payload and not target.with_suffix('.part').exists()
print('PASS: executable grouping, distinct installs, unknown identity isolation, memory totals, exact member snapshots, partial results, HTTP 304, retry, progress and truncated download cleanup')
