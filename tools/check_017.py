"""Catalog, voice, remote queue and medium-user launch tests. No apps opened."""
import json,os,threading,time
from pathlib import Path
import sys,tempfile,uuid
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app import applications as apps
from app.voice_commands import parse
from app.launch_queue import LaunchQueue

for text,name in [('abrir Black Desert','black desert'),('abra a Steam','steam'),('pode abrir o aplicativo Discord por favor','discord'),('inicie o launcher Stove','stove'),('open arbitrary studio','arbitrary studio'),('abrir Calculadora','calculadora')]:assert parse(text)==('launch',name),(text,parse(text))
for text in ('nao abra steam','talvez abrir discord','se abrir steam','abrir','clicar em iniciar jogo'):assert parse(text) is None
with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as folder:
    root=Path(folder);os.environ['AURA_DATA_DIR']=str(root/'isolated-agent')
    shortcut=root/'Discord.lnk';shortcut.write_bytes(b'fixture')
    executable=root/'Discord.exe';executable.write_bytes(b'MZfixture')
    steam=root/'library';(steam/'steamapps/common/Black Desert').mkdir(parents=True)
    (steam/'steamapps/appmanifest_12345.acf').write_text('"AppState" { "appid" "12345" "name" "Black Desert" "installdir" "Black Desert" }',encoding='utf-8')
    (root/'Steam.url').write_text('[InternetShortcut]\nURL=steam://rungameid/12345\n',encoding='utf-8')
    (root/'Website.url').write_text('[InternetShortcut]\nURL=https://example.com\n',encoding='utf-8')
    link=apps.entry('Discord','file',str(shortcut),'Atalho do Windows');exe=apps.entry('Discord','file',str(executable),'Registro do Windows')
    found=list(apps.shortcut_entries([root]));assert any(r['name']=='Discord' for r in found) and not any(r['name']=='Website' for r in found)
    games=list(apps.steam_entries([steam]));assert games[0]['target']=='steam://rungameid/12345'
    assert not apps.entry('Unknown','steam','steam://run/12345//-command evil','Steam')
    assert not apps.entry('Unknown','file',str(root/'missing.exe'),'Windows')
    assert not apps.entry('Uninstall Discord','file',str(executable),'Windows')
    assert not apps.target_valid('store','App!Id; calc') and not apps.target_valid('epic','https://example.com')
    catalog=apps.Catalog(root/'settings')
    rows=catalog.refresh([lambda:[link,exe]+games],lambda _: {str(shortcut):(str(executable),'')})
    assert len(rows)==2 and all('target' not in r and 'kind' not in r for r in rows)
    matches,exact=apps.match(rows,{'spoken':'discord','english':''});assert exact and len(matches)==1
    matches,exact=apps.match(rows,{'spoken':'outro','english':'open black desert'});assert len(matches)==1 and not exact
    assert apps.match(rows,'nada desse nome')[0]==[]
    catalog.alias(link['id'],'discórdia');rows=catalog.refresh([lambda:[link]+games]);assert apps.match(rows,'discordia')[1]
    catalog.add('Portable Studio',str(executable),'meu editor');rows=catalog.refresh([lambda:[]]);assert apps.match(rows,'meu editor')[1]
    opened=[];catalog.launch(rows[0]['id'],opened.append,is_elevated=False);assert opened==[str(executable)]
    try:catalog.launch(rows[0]['id'],opened.append,is_elevated=False,deadline=0);raise AssertionError('Expired request launched')
    except ValueError:pass
    try:catalog.launch(rows[0]['id'],opened.append,is_elevated=True);raise AssertionError('Elevated launch allowed')
    except OSError:pass
    assert len(opened)==1
    store=apps.entry('Calculator','store','Microsoft.Calculator_hash!App','Microsoft Store')
    other=apps.Catalog(root/'other');other.refresh([lambda:games+[store]])
    opened_other=[]
    for value in games+[store]:other.launch(value['id'],opened_other.append,is_elevated=False)
    assert opened_other==['steam://rungameid/12345','shell:AppsFolder\\Microsoft.Calculator_hash!App']
    entered=threading.Event();release=threading.Event()
    def slow_resolver(_):entered.set();release.wait(2);return {}
    refresh_thread=threading.Thread(target=lambda:catalog.refresh([lambda:[]],resolver=slow_resolver));refresh_thread.start()
    try:
        assert entered.wait(1)
        started=time.monotonic();catalog.launch(rows[0]['id'],lambda _:None,is_elevated=False)
        assert time.monotonic()-started<.5,'Discovery must not block opening or heartbeat delivery'
    finally:release.set();refresh_thread.join(3)
    executable.unlink()
    try:catalog.launch(rows[0]['id'],opened.append,is_elevated=False);raise AssertionError('Missing executable launched')
    except ValueError:pass
    assert len(opened)==1

    now=[100.];q=LaunchQueue(lambda:now[0]);worker=str(uuid.uuid4());key=link['id'];q.worker(worker,[apps.public(link)])
    request=str(uuid.uuid4());assert q.request(request,key)['state']=='pending'
    job=q.worker(worker);assert job['app_id']==key and job['expires_at']==120
    assert q.worker(worker) is None and q.request(request,key)['state']=='dispatch'
    q.worker(worker,results=[{'request_id':request,'ok':True,'message':'Opened fixture'}]);assert q.status(request)['state']=='opened'
    assert q.request(request,key)['state']=='opened' # Same request can never open twice.
    stale=str(uuid.uuid4());q.request(stale,key);now[0]=121;assert q.status(stale)['state']=='failed'
    try:q.request(str(uuid.uuid4()),key);raise AssertionError('Offline request queued')
    except ValueError:pass
    q.worker(worker);pending=str(uuid.uuid4());q.request(pending,key);q.worker(worker,[]);assert q.status(pending)['state']=='failed'

    from fastapi.testclient import TestClient
    from app import native_agent as agent
    headers={'Authorization':'Bearer '+agent.settings['token']}
    agent.launches=LaunchQueue()
    with patch.object(os,'startfile',side_effect=AssertionError('Agent must never launch anything')):
        with TestClient(agent.app,client=('127.0.0.1',1234)) as local:
            assert local.get('/api/applications').status_code==401
            assert local.post('/api/applications/worker',headers=headers,json={'worker_id':worker}).json()['catalog_required']
            assert local.post('/api/applications/worker',headers=headers,json={'worker_id':worker,'rows':[apps.public(link)]}).status_code==200
            assert not local.post('/api/applications/worker',headers=headers,json={'worker_id':worker}).json()['catalog_required']
            inventory=local.get('/api/applications',headers=headers).json();assert inventory['applications']==[apps.public(link)]
            assert 'target' not in json.dumps(inventory) and str(root) not in json.dumps(inventory)
            assert local.post('/api/applications/open',headers=headers,json={'app_id':key,'request_id':str(uuid.uuid4()),'path':'calc.exe'}).status_code==422
            request=str(uuid.uuid4());result=local.post('/api/applications/open',headers=headers,json={'app_id':key,'request_id':request});assert result.json()['state']=='pending'
            job=local.post('/api/applications/worker',headers=headers,json={'worker_id':worker}).json()['job'];assert job['app_id']==key
            assert local.post('/api/applications/worker',headers=headers,json={'worker_id':worker}).json()['job'] is None
            result=local.post('/api/applications/worker',headers=headers,json={'worker_id':worker,'results':[{'request_id':request,'ok':True,'message':'Windows accepted'}]});assert result.status_code==200
            assert local.get('/api/applications/requests/'+request,headers=headers).json()['state']=='opened'
        with TestClient(agent.app,client=('192.0.2.10',1234)) as mobile:
            assert mobile.post('/api/applications/worker',headers=headers,json={'worker_id':worker}).status_code==403
            assert mobile.post('/api/applications/open',headers=headers,json={'app_id':key,'request_id':str(uuid.uuid4())}).json()['state']=='pending'
            assert mobile.post('/api/applications/open',headers=headers,json={'app_id':'a'*64,'request_id':str(uuid.uuid4())}).status_code==404
    from app import admin,native_runtime
    import zipfile,hashlib
    resources=root/'resources';resources.mkdir();payload=resources/'admin-agent.zip';payload.write_bytes(b'fixture only')
    (resources/'admin-agent.json').write_text(json.dumps({'sha256':hashlib.sha256(payload.read_bytes()).hexdigest()}))
    original_script=admin.installation_script;staged=[]
    def inspect_archive(archive,digest,sid,identity_archive,identity_digest):
        assert hashlib.sha256(identity_archive.read_bytes()).hexdigest()==identity_digest
        with zipfile.ZipFile(identity_archive) as package:
            assert {'identity.json','server.crt','server.key','settings.env','state.sqlite','actions.log'}<=set(package.namelist())
            assert package.read('state.sqlite')==(native_runtime.DATA/'state.sqlite').read_bytes()
        staged.append(True)
        return original_script(archive,digest,sid,identity_archive,identity_digest)
    with patch.object(sys,'frozen',True,create=True),patch.object(sys,'_MEIPASS',str(resources),create=True),patch.object(admin,'sid',return_value='S-1-5-21-1-2-3-1001'),patch.object(admin,'system_directory',return_value=root/'Windows'),patch.object(admin,'run_elevated',return_value=0),patch.object(admin,'installation_script',side_effect=inspect_archive):admin.install()
    assert staged and json.loads((native_runtime.DATA/'admin.json').read_text())['build']==409
    import logging
    logging.shutdown()
print('PASS: general voice opening, installed shortcuts and Steam games, deduplication, manual apps and voice aliases, no elevated launch, stale targets, authenticated Android-to-Windows queue, no replay or arbitrary paths')
