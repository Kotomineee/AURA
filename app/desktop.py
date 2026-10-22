"""Native AURA desktop. All network work is marshalled back onto the Tk thread."""
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import ipaddress
import json
import os
from pathlib import Path
import queue
import socket
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from .native_runtime import PORT, identity, pairing
from .version import VERSION, BUILD
from . import process_groups


def main():
    if '--apply-update' in sys.argv:
        from .update_installer import apply
        apply(sys.argv[sys.argv.index('--apply-update') + 1])
        return
    if '--check-runtime' in sys.argv:
        try:
            from .runtime_check import run
            run()
        except Exception as exc:
            destination=os.environ.get('AURA_RUNTIME_CHECK_OUTPUT')
            if destination:
                Path(destination).write_text(json.dumps({'result':'FAIL','error_type':type(exc).__name__,'message':str(exc)}),encoding='utf-8')
            raise SystemExit(1) from None
        return
    if '--agent' in sys.argv:
        from .autostart import acquire_agent_lock
        if not acquire_agent_lock():
            return
        from .native_agent import run
        run()
        return
    import tkinter as tk
    import tkinter.font as tkfont
    from tkinter import ttk, messagebox
    import psutil
    from .visuals import BG, PANEL, SIDEBAR, LINE, TEXT, MUTED, TEAL, SELECT, Button, Metric, icon, rounded

    root = tk.Tk()
    if '--check-ui' in sys.argv: root.withdraw()
    root.title('AURA • '+VERSION); root.geometry('1240x850'); root.minsize(1040,760); root.configure(bg=BG)
    root.option_add('*Font',('Segoe UI',11))
    style=ttk.Style(root); style.theme_use('clam')
    style.configure('TCombobox',fieldbackground=PANEL,background=PANEL,foreground=TEXT,padding=10)
    style.map('TCombobox',fieldbackground=[('readonly',PANEL)],foreground=[('readonly',TEXT)])
    style.configure('Vertical.TScrollbar',background=LINE,troughcolor=BG,borderwidth=0,arrowsize=12)
    settings=identity(); context=ssl.create_default_context(cafile=settings['cert'])
    launch_pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='aura-launch')
    pool=ThreadPoolExecutor(max_workers=4,thread_name_prefix='aura-client')
    icon_pool=ThreadPoolExecutor(max_workers=2,thread_name_prefix='aura-icons-client')
    events=queue.Queue(); pending=set(); closed=False; connected=False;quitting=False;tray=None
    rows=[]; visible=[]; selected=None; generation=0; images=OrderedDict(); redraw_scheduled=False
    agent_build=0;process_list_limited=False
    banner=tk.StringVar(value='Inicie o agente na Visão geral para conectar seu computador.')
    connection_text=tk.StringVar(value='PC desconectado'); hostname=tk.StringVar(value='Aguardando conexão')
    mode_text=tk.StringVar(value='Estado ainda não consultado')
    schedule_text=tk.StringVar(value='Consulte o estado para ver o agendamento.')

    def label(parent,text='',size=11,color=TEXT,bold=False,variable=None):
        return tk.Label(parent,text=text,textvariable=variable,bg=parent.cget('bg'),fg=color,
            font=('Segoe UI',size,'bold' if bold else 'normal'),anchor='w',justify='left')
    def card(parent,padx=20,pady=18):
        return tk.Frame(parent,bg=PANEL,highlightbackground=LINE,highlightthickness=1,padx=padx,pady=pady)
    def api(path,body=None):
        payload=json.dumps(body).encode() if body is not None else None
        req=urllib.request.Request(f'https://127.0.0.1:{PORT}/api/{path}',data=payload,
            headers={'Authorization':'Bearer '+settings['token'],'Content-Type':'application/json','X-Command-ID':str(uuid.uuid4())},
            method='POST' if body is not None else 'GET')
        try:
            with urllib.request.urlopen(req,context=context,timeout=10) as response:return json.load(response)
        except urllib.error.HTTPError as exc:
            try:detail=json.load(exc).get('detail','Falha no comando')
            except (ValueError,OSError):detail='Falha no comando'
            raise RuntimeError(str(detail)) from None
    def task(key,fn,callback,quiet=False,executor=None):
        if closed or (quitting and key!="quit") or key in pending:return
        pending.add(key)
        if not quiet:banner.set('Carregando…')
        def work():
            try:events.put((key,callback,fn(),None,quiet))
            except Exception as exc:events.put((key,callback,None,str(exc),quiet))
        (executor or pool).submit(work)
    def drain():
        nonlocal connected
        if closed:return
        for _ in range(100):
            try:key,callback,result,error,quiet=events.get_nowait()
            except queue.Empty:break
            pending.discard(key)
            if quitting and key not in ('quit','tray-event'):continue
            if error:
                if not quiet:banner.set('Não foi possível concluir: '+error)
                if key in ('status','start'):
                    connected=False; connection_text.set('PC desconectado'); status_dot.configure(fg='#748596')
                    hostname.set('Conexão indisponível')
                    for metric in metrics:
                        metric.value=None; metric.used=None; metric.total=None; metric.samples=[]; metric.draw()
            else:callback(result)
        root.after(60,drain)

    sidebar=tk.Frame(root,bg=SIDEBAR,width=234,highlightthickness=1,highlightbackground=LINE)
    sidebar.pack(side='left',fill='y'); sidebar.pack_propagate(False)
    label(sidebar,'AURA',30,bold=True).pack(anchor='w',padx=28,pady=(30,4))
    label(sidebar,'SEU ESPAÇO DE CONTROLE',8,MUTED).pack(anchor='w',padx=28,pady=(0,26))
    nav_buttons={}
    main_area=tk.Frame(root,bg=BG,padx=30,pady=26); main_area.pack(side='left',fill='both',expand=True)
    title=tk.StringVar(); subtitle=tk.StringVar()
    label(main_area,variable=title,size=25,bold=True).pack(fill='x')
    label(main_area,variable=subtitle,color=MUTED).pack(fill='x',pady=(6,16))
    metric_row=tk.Frame(main_area,bg=BG); metric_row.pack(fill='x',pady=(0,12))
    metric_row.columnconfigure((0,1),weight=1,uniform='metric')
    metrics=[Metric(metric_row,kind) for kind in ('cpu','ram')]
    for i,metric in enumerate(metrics):metric.grid(row=0,column=i,sticky='ew',padx=(0,8) if i==0 else (8,0))
    page_area=tk.Frame(main_area,bg=BG); page_area.pack(fill='both',expand=True)
    page_area.columnconfigure(0,weight=1); page_area.rowconfigure(0,weight=1)
    pages={}; page_hosts={}; scrollable={}; current_page='home'
    for key in ('home','processes','power','calendar','connection','updates','history'):
        host=tk.Frame(page_area,bg=BG); host.grid(row=0,column=0,sticky='nsew'); page_hosts[key]=host
        if key in ('processes','history'):
            pages[key]=host
            continue
        bar=ttk.Scrollbar(host,orient='vertical'); bar.pack(side='right',fill='y')
        canvas=tk.Canvas(host,bg=BG,highlightthickness=0,yscrollcommand=bar.set)
        canvas.pack(side='left',fill='both',expand=True); bar.configure(command=canvas.yview)
        inner=tk.Frame(canvas,bg=BG); window=canvas.create_window(0,0,window=inner,anchor='nw')
        canvas.bind('<Configure>',lambda e,c=canvas,w=window:c.itemconfigure(w,width=e.width))
        inner.bind('<Configure>',lambda _,c=canvas:c.configure(scrollregion=c.bbox('all')))
        pages[key]=inner; scrollable[key]=canvas
    root.bind('<MouseWheel>',lambda e:scrollable[current_page].yview_scroll(-int(e.delta/120),'units') if current_page in scrollable else None)
    statusbar=label(main_area,variable=banner,size=10,color=MUTED); statusbar.pack(fill='x',pady=(12,0))
    statusbar.bind('<Configure>',lambda e:statusbar.configure(wraplength=max(200,e.width)))
    page_names={'home':('Visão geral','Seu computador, conectado a você.'),
        'processes':('Aplicativos','Processos agrupados e memória total por aplicativo.'),
        'power':('Energia','Controle o computador com clareza e segurança.'),
        'calendar':('Agendamentos','Escolha quando encerrar o dia.'),
        'connection':('Configurações','Conexão com o celular e preferências do Windows.'),
        'updates':('Atualizações','Sua AURA sempre em dia.'),
        'history':('Histórico','Acompanhe as ações registradas pelo agente.')}
    def navigate(key):
        nonlocal current_page
        current_page=key
        page_hosts[key].tkraise(); title.set(page_names[key][0]); subtitle.set(page_names[key][1])
        metric_row.pack_forget()
        if key in ('home','power'):metric_row.pack(fill='x',pady=(0,16),before=page_area)
        for name,button in nav_buttons.items():button.active=name==key; button.draw()
        if key=='processes' and connected:refresh_processes()
        elif key=='history' and connected:refresh_logs()
    for key in ('home','processes','power','calendar','updates','history','connection'):
        button=Button(sidebar,page_names[key][0],lambda k=key:navigate(k),kind=key,nav=True)
        button.pack(fill='x',padx=12,pady=5); nav_buttons[key]=button
    foot=tk.Frame(sidebar,bg=SIDEBAR); foot.pack(side='bottom',fill='x',padx=22,pady=24)
    tk.Frame(foot,bg=LINE,height=1).pack(fill='x',pady=(0,20))
    status_dot=label(foot,'●',20,color='#748596'); status_dot.pack(side='left',padx=(0,8))
    connection_labels=tk.Frame(foot,bg=SIDEBAR); connection_labels.pack(side='left',fill='x')
    label(connection_labels,variable=connection_text,color=TEAL).pack(anchor='w')
    host_label=label(connection_labels,variable=hostname,color=MUTED,size=9)
    host_label.configure(wraplength=148); host_label.pack(anchor='w',pady=(4,0))

    def show_status(data):
        nonlocal connected,agent_build
        agent_build=data.get('build',0)
        connected=True; connection_text.set('PC conectado'); hostname.set(data['hostname']); status_dot.configure(fg='#37DA8B')
        mode_text.set('Simulação ativa • nenhuma ação de energia será executada' if data['dry_run'] else 'Modo real ativo • ações enviadas ao Windows')
        for metric in metrics:metric.update_value(data)
        schedule_text.set('Nenhum desligamento agendado.' if not data['shutdown_at'] else
            'Desligamento em '+datetime.fromtimestamp(data['shutdown_at']).strftime('%d/%m às %H:%M:%S'))
        banner.set('Conectado • '+('Simulação' if data['dry_run'] else 'Modo real'))
        if data.get('build') != BUILD and data.get('api_protocol') != 1:
            banner.set('Agente de uma versão anterior em execução. Reinicie o Windows para carregar a versão '+VERSION+'.')
        elif '--update-ready' in sys.argv:
            from .update_installer import mark_ready
            mark_ready(sys.argv[sys.argv.index('--update-ready') + 1])
        if agent_build<409:
            banner.set('Atualize o agente nos Ajustes para receber pedidos de abertura do Android.')
            if '--startup' not in sys.argv and not preferences.read().get('agent_017_prompted'):
                preferences.save(agent_017_prompted=True)
                root.after(400,offer_agent_upgrade)
    def offer_agent_upgrade():
        if closed or quitting or installing_update or agent_build>=409:return
        restore()
        if messagebox.askyesno('Atualizar agente do Windows','A abertura pelo Android precisa do novo agente. Atualizar agora? O Windows pode pedir uma autorização de administrador. Sua conexão será preservada.',parent=root):setup_admin()
    def refresh():task('status',lambda:api('status'),show_status)
    def start_agent():
        def start():
            try:
                running=api('status')
                if running.get('build',0)>=409 or running.get('administrator'):return running
                from .tray import stop_agent
                stop_agent(api,psutil.Process,os.getpid())
            except (OSError,RuntimeError):pass
            from . import admin
            if admin.configured():
                admin.start()
                for _ in range(30):
                    time.sleep(.5)
                    try:return api('status')
                    except (OSError,RuntimeError):continue
                raise RuntimeError('O agente administrador não iniciou. Reconfigure em Conexão.')
            if getattr(sys,'frozen',False):args=[sys.executable,'--agent']
            else:
                executable=Path(sys.executable).with_name('pythonw.exe')
                args=[str(executable if executable.exists() else sys.executable),'-m','app.desktop','--agent']
            flags=(subprocess.CREATE_NO_WINDOW|subprocess.DETACHED_PROCESS) if os.name=='nt' else 0
            subprocess.Popen(args,cwd=Path(__file__).resolve().parents[1],creationflags=flags,
                stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            for _ in range(20):
                time.sleep(.5)
                try:return api('status')
                except (OSError,RuntimeError):continue
            raise RuntimeError('O agente não iniciou. Consulte o diagnóstico no README.')
        task('start',start,show_status)
    def action(path,body):
        def complete(data):
            banner.set(data['message'])
            if path=='processes/terminate':refresh_processes()
            else:task('status',lambda:api('status'),lambda s:(show_status(s),banner.set(data['message'])),quiet=True)
        task('action',lambda:api(path,body),complete)

    home_dashboard=tk.Frame(pages['home'],bg=BG);home_dashboard.pack(fill='x',pady=(0,16))
    home_dashboard.columnconfigure((0,1),weight=1,uniform='dashboard')
    state=card(home_dashboard); state.grid(row=0,column=0,sticky='nsew',padx=(0,8))
    label(state,'SEU COMPUTADOR',10,MUTED).pack(anchor='w')
    home_host=label(state,variable=hostname,size=20,bold=True);home_host.configure(wraplength=320);home_host.pack(anchor='w',pady=(8,4))
    home_mode=label(state,variable=mode_text,size=10,color=MUTED);home_mode.configure(wraplength=320);home_mode.pack(anchor='w')
    row=tk.Frame(state,bg=PANEL); row.pack(fill='x',pady=(18,0))
    Button(row,'Conectar',start_agent,kind='connection',accent=True,width=140).pack(side='left',fill='x',expand=True,padx=(0,10))
    Button(row,'Atualizar',refresh,kind='refresh',width=140).pack(side='left',fill='x',expand=True)
    next_card=card(home_dashboard); next_card.grid(row=0,column=1,sticky='nsew',padx=(8,0))
    label(next_card,'PRÓXIMO AGENDAMENTO',10,MUTED).pack(anchor='w')
    home_schedule=label(next_card,variable=schedule_text,size=13);home_schedule.configure(wraplength=320);home_schedule.pack(anchor='w',pady=(10,14))
    Button(next_card,'Ver agendamentos',lambda:navigate('calendar'),kind='calendar').pack(fill='x')
    Button(pages['home'],'Abrir aplicativos em execução',lambda:navigate('processes'),kind='processes').pack(fill='x')
    from . import preferences, updates, autostart
    prefs = preferences.read()
    startup_enabled = tk.BooleanVar(value=prefs.get('autostart', True))
    startup_state = tk.StringVar(value='O agente conecta automaticamente ao abrir a AURA.')
    startup_card = card(pages['connection']); startup_card.pack(fill='x',pady=(0,14))
    label(startup_card,'Inicialização do Windows',17,bold=True).pack(anchor='w')
    def configure_startup():
        try:
            autostart.configure(startup_enabled.get())
            preferences.save(autostart=startup_enabled.get())
            startup_state.set('Ativado: AURA e agente iniciam após entrar no Windows.' if startup_enabled.get() else 'Inicialização com o Windows desativada.')
        except OSError:
            startup_state.set('Não foi possível configurar. Tente novamente pelo botão abaixo.')
    tk.Checkbutton(startup_card,text='Iniciar AURA com o Windows',variable=startup_enabled,
        command=configure_startup,bg=PANEL,fg=TEXT,selectcolor=BG,activebackground=PANEL,activeforeground=TEXT).pack(anchor='w',pady=10)
    label(startup_card,variable=startup_state,size=10,color=MUTED).pack(anchor='w')
    Button(startup_card,'Aplicar inicialização',configure_startup).pack(fill='x',pady=(8,0))
    from . import admin
    admin_card=card(pages['connection']); admin_card.pack(fill='x',pady=(0,14))
    label(admin_card,'Administrador automático',17,bold=True).pack(anchor='w')
    admin_text=tk.StringVar(value='Configurado para iniciar após entrar no Windows.' if admin.configured() else 'Autorize uma vez para iniciar o agente com administrador nos próximos logins.')
    label(admin_card,variable=admin_text,size=10,color=MUTED).pack(anchor='w',pady=10)
    def setup_admin():
        def configure():
            try:
                previous=api('status')
                from .native_runtime import DATA
                (DATA/'settings.env').write_text('DRY_RUN='+str(previous['dry_run']).lower()+'\n',encoding='utf-8')
            except (OSError,RuntimeError):pass
            from .tray import stop_agent
            stop_agent(api,psutil.Process,os.getpid())
            try:admin.install()
            except Exception:
                events.put(('admin-recover',lambda _:start_agent(),None,None,True))
                raise
            admin.start()
            for _ in range(30):
                time.sleep(.5)
                try:
                    result=api('status')
                    if result.get('administrator'):return result
                except (OSError,RuntimeError):pass
            raise RuntimeError('Configurado. Reinicie o Windows para iniciar o agente administrador.')
        def complete(result):
            show_status(result); admin_text.set('Agente administrador ativo. Inicialização automática configurada.')
        task('admin-setup',configure,complete)
    Button(admin_card,'Configurar administrador automático',setup_admin,kind='settings').pack(fill='x')
    from .voice import Listener
    from .voice_commands import candidates,selected_reference
    from .visuals import VoiceMeter
    listener=None
    voice_card=card(pages['home']); voice_card.pack(fill='x',pady=(0,16),before=home_dashboard)
    label(voice_card,'ASSISTENTE AURA',10,MUTED).pack(anchor='w')
    label(voice_card,'Diga “Ok Aura”.',24,bold=True).pack(anchor='w',pady=(8,0))
    voice_text=tk.StringVar(value='Preparando escuta automática • reconhecimento local.')
    voice_label=label(voice_card,variable=voice_text,size=10,color=MUTED); voice_label.configure(wraplength=670); voice_label.pack(fill='x',pady=8)
    voice_meter=VoiceMeter(voice_card);voice_meter.pack(fill='x',pady=(4,12))
    label(voice_card,'Exemplos: “abrir Steam”, “encerrar Discord”, “desligar em trinta minutos”.',10,MUTED).pack(anchor='w')
    def receive_voice(event):
        nonlocal listener
        if quitting:return
        kind,value=event
        if kind=='level':voice_meter.set_level(value);return
        if kind in ('state','error'):
            voice_text.set(value)
            if kind=='error':
                listener=None;voice_meter.set_level(0)
                root.after(15000,start_voice)
        elif kind=='awake':
            restore();navigate('home')
            voice_text.set('Estou ouvindo. Diga o comando em até 10 segundos.')
            if os.name=='nt':
                import winsound
                winsound.MessageBeep()
            root.after(10000,lambda:voice_text.set('Diga “Ok Aura”, aguarde o sinal e diga o comando.') if listener else None)
        elif kind=='command':
            voice_text.set('Diga “Ok Aura” para outro comando.')
            if not value:voice_text.set('Comando não reconhecido. Diga “Ok Aura” e tente novamente.');return
            command,argument=value
            if command=='status':refresh()
            elif command=='cancel':action('shutdown/cancel',{})
            elif command in ('shutdown','restart'):power(command)
            elif command=='schedule':
                if messagebox.askyesno('Agendar por voz',f'Confirmar desligamento em {argument//60} minutos?',parent=root):action('shutdown',{'confirm':True,'delay_seconds':argument})
            elif command=='wake':voice_text.set('Ligar o PC por voz está disponível no Android.')
            elif command=='launch':launch_voice(argument)
            elif command=='terminate':
                def choose(data):
                    nonlocal selected
                    if selected_reference(argument):
                        matches=[r for r in process_groups.group(data) if selected and process_groups.key(r)==process_groups.key(selected)]
                        if not matches:
                            navigate('processes');display_processes(data);voice_text.set('Selecione o aplicativo na aba Processos e repita o comando.');return
                    else:matches=process_groups.group(candidates(data,argument))
                    if len(matches)==1:
                        selected=matches[0]; terminate()
                    elif matches:
                        display_processes(matches); navigate('processes'); search.set('')
                        voice_text.set('Há vários processos com esse nome. Selecione o PID na aba Processos.')
                    else:voice_text.set('Nenhum programa elegível com esse nome. Confira a aba Processos.')
                task('voice-processes',lambda:api('processes'),choose)
    def start_voice():
        nonlocal listener
        if closed or quitting or listener:return
        voice_text.set('Preparando reconhecimento local…')
        listener=Listener(lambda event:events.put(('voice-event',receive_voice,event,None,True)))
        listener.start()
    from .applications import Catalog,match as match_application
    from .native_runtime import DATA
    catalog=Catalog(DATA);bridge_owner=str(uuid.uuid4());bridge_results=[];bridge_catalog_dirty=True;catalog_generation=0
    apps_card=card(pages['home']);apps_card.pack(fill='x',pady=(0,16))
    label(apps_card,'PROGRAMAS INSTALADOS',10,MUTED).pack(anchor='w')
    apps_text=tk.StringVar(value='Preparando catálogo do Windows…')
    label(apps_card,variable=apps_text,size=11).pack(anchor='w',pady=8)
    label(apps_card,'Abra por voz, confira nomes ou adicione um programa portátil. O pedido do celular também é atendido com a AURA na bandeja.',10,MUTED).pack(anchor='w')
    def discover_apps():
        if closed or quitting:return
        if 'app-catalog' in pending:root.after(200,discover_apps);return
        def complete(rows):
            nonlocal bridge_catalog_dirty,catalog_generation
            catalog_generation+=1;bridge_catalog_dirty=True
            apps_text.set(str(len(rows))+' aplicativos encontrados • diga “Ok Aura”, aguarde o sinal e peça para abrir.')
        task('app-catalog',catalog.refresh,complete,quiet=True)
    def open_installed(row):
        def opened(message):voice_text.set(message);banner.set(message)
        task('open-app',lambda:catalog.launch(row['id']),opened)
    def launch_voice(argument):
        matches,exact=match_application(catalog.public(),argument)
        if exact and len(matches)==1:open_installed(matches[0])
        else:show_installed(argument,matches)
    def show_installed(argument=None,suggestions=None):
        from tkinter import filedialog,simpledialog
        restore()
        dialog=tk.Toplevel(root);dialog.title('Programas instalados');dialog.geometry('760x620');dialog.configure(bg=BG)
        label(dialog,'Abrir um aplicativo',22,bold=True).pack(fill='x',padx=20,pady=(20,8))
        label(dialog,'Escolha o destino correto. Use “Nome de voz” se a pronúncia precisar de ajuste.',10,MUTED).pack(fill='x',padx=20)
        query=tk.StringVar();field=tk.Entry(dialog,textvariable=query,bg=PANEL,fg=TEXT,insertbackground=TEAL,relief='flat');field.pack(fill='x',padx=20,pady=14,ipady=10)
        listing=tk.Listbox(dialog,bg=PANEL,fg=TEXT,selectbackground=SELECT,selectforeground=TEXT,relief='flat',activestyle='none',exportselection=False,font=('Segoe UI',11));listing.pack(fill='both',expand=True,padx=20)
        displayed=[]
        def draw(*_):
            nonlocal displayed
            from .voice_commands import normalize
            term=normalize(query.get());rows=catalog.public()
            displayed=sorted([r for r in rows if not term or any(term in a for a in r['aliases'])],key=lambda r:r['name'].casefold())
            if suggestions and not term:displayed=suggestions+[r for r in displayed if r['id'] not in {v['id'] for v in suggestions}]
            listing.delete(0,'end')
            for row in displayed:listing.insert('end',row['name']+'  •  '+row['source'])
        query.trace_add('write',draw);draw()
        def selected_app():
            chosen=listing.curselection();return displayed[chosen[0]] if chosen else None
        def launch():
            row=selected_app()
            if row:open_installed(row);dialog.destroy()
        def add():
            path=filedialog.askopenfilename(parent=dialog,title='Selecionar aplicativo',filetypes=[('Aplicativo ou atalho','*.exe *.lnk')])
            if not path:return
            name=simpledialog.askstring('Nome do aplicativo','Como este aplicativo deve aparecer?',initialvalue=Path(path).stem,parent=dialog)
            if not name:return
            try:catalog.add(name,path);discover_apps();dialog.destroy()
            except (OSError,ValueError) as exc:messagebox.showerror('Adicionar aplicativo',str(exc),parent=dialog)
        def alias():
            row=selected_app()
            if not row:return
            value=simpledialog.askstring('Nome de voz','Como você costuma pronunciar '+row['name']+'?',parent=dialog)
            if not value:return
            try:catalog.alias(row['id'],value);discover_apps();dialog.destroy()
            except (OSError,ValueError) as exc:messagebox.showerror('Nome de voz',str(exc),parent=dialog)
        actions=tk.Frame(dialog,bg=BG);actions.pack(fill='x',padx=20,pady=16)
        Button(actions,'Abrir',launch,accent=True,width=110).pack(side='left',padx=(0,8))
        Button(actions,'Adicionar',add,width=125).pack(side='left',padx=(0,8))
        Button(actions,'Nome de voz',alias,width=150).pack(side='left',padx=(0,8))
        Button(actions,'Atualizar',lambda:(discover_apps(),dialog.destroy()),width=125).pack(side='left')
        listing.bind('<Double-1>',lambda _:launch());field.focus_set()
        if argument and not suggestions:voice_text.set('Não encontrei esse nome. Confira o catálogo, adicione o aplicativo ou ajuste o nome de voz.')
    Button(apps_card,'Ver programas instalados',show_installed,kind='processes').pack(fill='x')
    Button(apps_card,'Atualizar lista do Windows',discover_apps,kind='refresh').pack(fill='x',pady=(8,0))
    def bridge_poll():
        if closed or quitting:return
        if connected and agent_build>=409 and not installing_update:
            revision=catalog_generation;sent=list(bridge_results)
            packet={'worker_id':bridge_owner,'results':sent}
            if bridge_catalog_dirty:packet['rows']=catalog.public()
            def work_bridge():
                response=api('applications/worker',packet);job=response.get('job');ack=None
                if job:
                    try:
                        if time.monotonic()>=job['expires_at']:raise ValueError('A solicitação expirou; tente novamente.')
                        message=catalog.launch(job['app_id'],deadline=job['expires_at']);ack={'request_id':job['request_id'],'ok':True,'message':message[:240]}
                    except (OSError,ValueError) as exc:ack={'request_id':job['request_id'],'ok':False,'message':str(exc)[:240]}
                return response,ack
            def complete_bridge(value):
                nonlocal bridge_catalog_dirty
                response,ack=value
                for result in sent:
                    if result in bridge_results:bridge_results.remove(result)
                if 'rows' in packet and revision==catalog_generation:bridge_catalog_dirty=False
                if response.get('catalog_required'):bridge_catalog_dirty=True
                if ack:bridge_results.append(ack);banner.set(ack['message'])
                if response.get('refresh'):discover_apps()
            task('launch-worker',work_bridge,complete_bridge,quiet=True,executor=launch_pool)
        root.after(900,bridge_poll)
    def periodic_catalog():
        if closed or quitting:return
        discover_apps();root.after(5*60*1000,periodic_catalog)
    update_card = card(pages['updates']); update_card.pack(fill='x',pady=(0,16))
    label(update_card,'Atualizações • AURA '+VERSION,16,bold=True).pack(anchor='w')
    update_text = tk.StringVar(value='Consultando as Releases públicas do GitHub…')
    last_update_notified = 0
    available_update=None; update_busy=False;installing_update=False
    label(update_card,variable=update_text,size=10,color=MUTED).pack(anchor='w',pady=8)
    def show_update(result,manual=False):
        nonlocal last_update_notified,available_update
        available_update=result if result['available'] else None
        install_button.set_enabled(available_update is not None)
        stamp=datetime.now().strftime('%H:%M')
        update_text.set(('Nova versão disponível: '+result['version'] if result['available'] else 'Você está na versão mais recente publicada.')+' • Verificado às '+stamp)
        if result['available'] and (manual or last_update_notified != result['build']):
            last_update_notified = result['build']
            if messagebox.askyesno('Atualização disponível',
                    'AURA '+result['version']+' está pronta. Atualizar agora?\nA AURA vai baixar, instalar e reabrir automaticamente. O controle do PC ficará indisponível por alguns instantes.',parent=root):
                install_update(result)
    def install_update(result):
        nonlocal installing_update
        if installing_update:return
        installing_update=True;install_button.set_enabled(False);check_button.set_enabled(False)
        from . import update_installer
        from .native_runtime import DATA
        update_text.set('Baixando e verificando a atualização… Aguarde.')
        def prepare():
            def progress(done,total):
                events.put(('update-progress',lambda value:update_text.set(value),('Baixando atualização • '+str(min(99,int(done*100/total)))+'%' if total else f'Baixando atualização • {done/1048576:.1f} MB'),None,True))
            updates.download(result, DATA / 'updates' / 'payload.exe',progress=progress)
            events.put(('update-progress',lambda value:update_text.set(value),'Arquivo verificado • preparando instalação…',None,True))
            helper, job_path = update_installer.prepare(result, None)
            try:
                api('status')
            except OSError:
                agent = None
            else:
                agent = api('update/prepare', {'confirm':True})
            job = json.loads(job_path.read_text(encoding='utf-8'))
            job['agent'] = agent
            job_path.write_text(json.dumps(job), encoding='utf-8')
            return helper, job_path
        def ready(value):
            nonlocal installing_update
            if isinstance(value,dict) and 'error' in value:
                installing_update=False;install_button.set_enabled(True);check_button.set_enabled(True)
                update_text.set(value['error'])
                banner.set(value['error'])
                start_agent()
                return
            helper, job_path = value
            try:
                update_installer.launch([str(helper),'--apply-update',str(job_path)])
            except OSError:
                installing_update=False;install_button.set_enabled(True);check_button.set_enabled(True)
                update_text.set('Não foi possível abrir o instalador. Tente novamente.')
                start_agent()
                return
            close()
        def attempt():
            try:return prepare()
            except Exception as error:
                return {'error':str(error) if isinstance(error,ValueError) else 'Não foi possível concluir a atualização. Sua instalação foi preservada; tente novamente.'}
        task('install-update', attempt, ready)
    def check_updates(manual=False):
        nonlocal update_busy
        if quitting or update_busy or installing_update:return
        update_busy=True;check_button.set_enabled(False);update_text.set('Consultando a versão publicada no GitHub…')
        def check():
            try:return updates.check(updates.DEFAULT_REPOSITORY)
            except Exception as exc:
                return {'error':str(exc) if isinstance(exc,ValueError) else 'Sem acesso ao GitHub. Tente novamente mais tarde.'}
        def receive(result):
            nonlocal update_busy
            update_busy=False;check_button.set_enabled(True)
            if 'error' in result:update_text.set(result['error'])
            else:show_update(result,manual)
        task('updates',check,receive,quiet=True)
    check_button=Button(update_card,'Verificar agora',lambda:check_updates(True),kind='refresh');check_button.pack(fill='x',pady=(6,10))
    install_button=Button(update_card,'Instalar atualização disponível',lambda:install_update(available_update) if available_update else None,kind='refresh',accent=True)
    install_button.pack(fill='x');install_button.set_enabled(False)
    label(update_card,'Apenas versões publicadas e estáveis são oferecidas. O download é conferido antes de instalar.',10,MUTED).pack(anchor='w',pady=(16,0))
    def periodic_updates():
        check_updates()
        root.after(15*60*1000,periodic_updates)
    mode=card(pages['power']); mode.pack(fill='x',pady=(2,14))
    label(mode,'Modo de operação',16,bold=True).pack(anchor='w')
    label(mode,variable=mode_text,size=10,color=MUTED).pack(anchor='w',pady=(8,16))
    mode_row=tk.Frame(mode,bg=PANEL); mode_row.pack(fill='x')
    Button(mode_row,'Ativar simulação',lambda:action('mode',{'dry_run':True})).pack(side='left',fill='x',expand=True,padx=(0,10))
    def real_mode():
        if messagebox.askyesno('Modo real','Habilitar ações reais no Windows para os dispositivos conectados?',parent=root):action('mode',{'dry_run':False})
    Button(mode_row,'Ativar modo real',real_mode).pack(side='left',fill='x',expand=True)
    power_card=card(pages['power']); power_card.pack(fill='x')
    label(power_card,'Energia do computador',16,bold=True).pack(anchor='w')
    label(power_card,'Salve seus arquivos antes de desligar ou reiniciar.',11,MUTED).pack(anchor='w',pady=(8,18))
    def power(kind):
        text='Desligar' if kind=='shutdown' else 'Reiniciar'
        if messagebox.askyesno(text+' PC',text+' este computador? Salve seus arquivos antes.',parent=root):action('power',{'action':kind,'confirm':True})
    Button(power_card,'Desligar PC',lambda:power('shutdown'),kind='power',danger=True).pack(fill='x',pady=(0,10))
    Button(power_card,'Reiniciar PC',lambda:power('restart'),kind='refresh').pack(fill='x')
    schedule_card=card(pages['calendar']); schedule_card.pack(fill='x',pady=(2,14))
    label(schedule_card,'Desligamento programado',16,bold=True).pack(anchor='w')
    label(schedule_card,variable=schedule_text,size=11,color=TEAL).pack(anchor='w',pady=(10,22))
    label(schedule_card,'Minutos até desligar',11,MUTED).pack(anchor='w')
    minutes=tk.Entry(schedule_card,bg=BG,fg=TEXT,insertbackground=TEAL,relief='flat',highlightthickness=1,highlightbackground=LINE,highlightcolor=TEAL,font=('Segoe UI',16))
    minutes.insert(0,'30'); minutes.pack(fill='x',ipady=12,pady=(8,8))
    label(schedule_card,'De 1 minuto a 7 dias (10080 minutos).',10,MUTED).pack(anchor='w',pady=(0,18))
    def schedule():
        try:
            value=int(minutes.get())
            if not 1<=value<=10080:raise ValueError()
        except ValueError:banner.set('Informe de 1 a 10080 minutos.');return
        if messagebox.askyesno('Agendar desligamento',f'Confirmar desligamento em {value} minutos?',parent=root):action('shutdown',{'delay_seconds':value*60,'confirm':True})
    Button(schedule_card,'Agendar desligamento',schedule,kind='calendar',accent=True).pack(fill='x',pady=(0,10))
    Button(schedule_card,'Cancelar agendamento',lambda:action('shutdown/cancel',{})).pack(fill='x')

    procs=pages['processes']
    search_frame=card(procs,padx=12,pady=8); search_frame.pack(fill='x',pady=(0,12))
    search_icon=tk.Canvas(search_frame,bg=PANEL,width=28,height=28,highlightthickness=0)
    search_icon.pack(side='left',padx=(0,8)); icon(search_icon,'search',2,2,22)
    search=tk.StringVar()
    entry=tk.Entry(search_frame,textvariable=search,bg=PANEL,fg=TEXT,insertbackground=TEAL,relief='flat')
    entry.pack(side='left',fill='x',expand=True,ipady=4)
    entry_label=label(search_frame,'Buscar aplicativo ou PID',10,MUTED)
    entry_label.place(x=40,y=4); entry_label.bind('<Button-1>',lambda _:entry.focus_set())
    table_frame=tk.Frame(procs,bg=BG,highlightbackground=LINE,highlightthickness=1); table_frame.pack(fill='both',expand=True)
    header=tk.Canvas(table_frame,height=38,bg=PANEL,highlightthickness=0); header.pack(fill='x')
    body=tk.Frame(table_frame,bg=BG); body.pack(fill='both',expand=True)
    scroll=ttk.Scrollbar(body,orient='vertical'); scroll.pack(side='right',fill='y')
    table=tk.Canvas(body,bg=BG,highlightthickness=0,takefocus=True,yscrollcommand=scroll.set)
    table.pack(side='left',fill='both',expand=True); scroll.configure(command=table.yview)
    details=card(procs,padx=16,pady=14); details.pack(fill='x',pady=(12,0))
    detail_icon=tk.Canvas(details,bg=PANEL,width=44,height=44,highlightthickness=0); detail_icon.pack(side='left',padx=(0,14))
    detail_copy=tk.Frame(details,bg=PANEL); detail_copy.pack(side='left',fill='x',expand=True)
    detail_name=tk.StringVar(value='Selecione um aplicativo'); detail_meta=tk.StringVar(value='Confira nome e PID antes de encerrar.')
    label(detail_copy,variable=detail_name,size=12,bold=True).pack(anchor='w')
    label(detail_copy,variable=detail_meta,size=10,color=MUTED).pack(anchor='w',pady=(5,0))
    def terminate():
        if selected is None:return
        row=selected
        children=process_groups.members(row)
        pid_summary=', '.join(str(c['pid']) for c in children[:12])+(' …' if len(children)>12 else '')
        if messagebox.askyesno('Encerrar aplicativo',f"Encerrar {row['name']} e seus {len(children)} processos listados?\nPIDs: "+pid_summary+"\nAlterações não salvas podem ser perdidas.",parent=root):
            def finish(result):
                refresh_processes();banner.set(result['message'])
                if result['failed']:messagebox.showwarning('Encerramento parcial',result['message'],parent=root)
            task('terminate-group',lambda:process_groups.terminate_snapshot(row,lambda payload:api('processes/terminate',payload)),finish)
    end_button=Button(details,'Encerrar aplicativo',terminate,kind='trash',danger=True,width=210)
    end_button.pack(side='right',padx=(10,0)); end_button.set_enabled(False)
    def group_details():
        if not selected:return
        dialog=tk.Toplevel(root);dialog.title('Detalhes • '+selected['name']);dialog.geometry('640x480');dialog.configure(bg=BG)
        label(dialog,selected['name'],18,bold=True).pack(anchor='w',padx=20,pady=20)
        view=tk.Frame(dialog,bg=BG);view.pack(fill='both',expand=True,padx=20,pady=(0,12))
        scrollbar=ttk.Scrollbar(view);scrollbar.pack(side='right',fill='y')
        copy=tk.Text(view,bg=PANEL,fg=TEXT,relief='flat',padx=14,pady=14,wrap='word',yscrollcommand=scrollbar.set,font=('Consolas',10));copy.pack(fill='both',expand=True);scrollbar.configure(command=copy.yview)
        copy.insert('1.0','\n'.join(f"PID {r['pid']}  •  {r['ram_mb']:g} MB  •  {r['name']}" for r in process_groups.members(selected)));copy.configure(state='disabled')
        Button(dialog,'Fechar detalhes',dialog.destroy).pack(fill='x',padx=20,pady=(0,20))
    Button(details,'Detalhes',group_details,width=115).pack(side='right',padx=(8,0))
    process_bar=tk.Frame(procs,bg=BG); process_bar.pack(fill='x',pady=(8,0))
    count=tk.StringVar(value='Atualize para carregar os aplicativos.')
    label(process_bar,variable=count,size=10,color=MUTED).pack(side='left')
    Button(process_bar,'Atualizar',lambda:refresh_processes(),kind='refresh',width=150).pack(side='right')
    name_font=tkfont.Font(root=root,family='Segoe UI',size=11)
    def draw_header(_=None):
        header.delete('all'); w=table.winfo_width()
        for x,text in ((20,'Aplicativo'),(w*.60,'Processos'),(w*.78,'Memória total')):header.create_text(x,19,text=text,anchor='w',fill=MUTED,font=('Segoe UI',10))
    header.bind('<Configure>',draw_header)
    def fallback(canvas,x,y,name,size=32):
        rounded(canvas,x,y,x+size,y+size,8,fill='#263746',outline=LINE)
        canvas.create_text(x+size/2,y+size/2,text=(name[:1] or '?').upper(),fill=MUTED,font=('Segoe UI',12,'bold'))
    def update_detail():
        detail_icon.delete('all')
        if selected:
            detail_name.set(selected['name']); detail_meta.set(f"{len(process_groups.members(selected))} processos   •   {selected['ram_mb']:g} MB no total")
            image=images.get(selected.get('icon_id'))
            if image:detail_icon.create_image(22,22,image=image)
            else:fallback(detail_icon,6,6,selected['name'])
        else:detail_name.set('Selecione um aplicativo'); detail_meta.set('Confira nome e PID antes de encerrar.')
        end_button.set_enabled(selected is not None)
    def draw_rows(_=None):
        table.delete('all'); w=table.winfo_width(); draw_header()
        for i,row in enumerate(visible):
            y=i*64; active=selected and process_groups.key(row)==process_groups.key(selected)
            if active:
                table.create_rectangle(0,y,w,y+64,fill=SELECT,outline=''); table.create_line(2,y+4,2,y+60,fill=TEAL,width=3)
            table.create_line(0,y+64,w,y+64,fill='#23313D')
            image=images.get(row.get('icon_id'))
            if image:table.create_image(40,y+32,image=image)
            else:fallback(table,24,y+16,row['name'])
            name=Path(row['name']).stem; max_width=max(60,w*.60-90)
            while name_font.measure(name)>max_width and len(name)>1:name=name[:-2]+'…'
            table.create_text(76,y+24,text=name,anchor='w',fill=TEXT,font=('Segoe UI',11))
            executable=row['name']
            while name_font.measure(executable)>max_width and len(executable)>1:executable=executable[:-2]+'…'
            table.create_text(76,y+44,text=executable,anchor='w',fill=MUTED,font=('Segoe UI',9))
            table.create_text(w*.60,y+32,text=str(len(process_groups.members(row))),anchor='w',fill=MUTED,font=('Segoe UI',10))
            table.create_text(w*.78,y+32,text=f"{row['ram_mb']:g} MB",anchor='w',fill=MUTED,font=('Segoe UI',10))
        if not visible:table.create_text(w/2,65,text='Nenhum resultado para esta busca.' if rows else 'Nenhum aplicativo carregado. Use Atualizar.',fill=MUTED,font=('Segoe UI',11))
        table.configure(scrollregion=(0,0,w,max(120,len(visible)*64))); update_detail()
    table.bind('<Configure>',draw_rows)
    def filter_rows(*_):
        nonlocal visible,selected
        term=search.get().strip().casefold(); visible=[r for r in rows if process_groups.contains(r,term)]
        if selected and not any(process_groups.key(r)==process_groups.key(selected) for r in visible):selected=None
        entry_label.place_forget()
        if not search.get() and entry.focus_get()!=entry:entry_label.place(x=40,y=4)
        count.set(f'{len(visible)} aplicativos • {sum(len(process_groups.members(r)) for r in visible)} processos • maior memória primeiro')
        table.yview_moveto(0); draw_rows()
    search.trace_add('write',filter_rows)
    entry.bind('<FocusIn>',lambda _:entry_label.place_forget())
    entry.bind('<FocusOut>',lambda _:entry_label.place(x=40,y=4) if not search.get() else None)
    def select_at(event):
        nonlocal selected
        index=int(table.canvasy(event.y)//64)
        if 0<=index<len(visible):selected=visible[index]; table.focus_set(); draw_rows()
    table.bind('<Button-1>',select_at)
    def key_select(delta):
        nonlocal selected
        if not visible:return
        index=next((i for i,r in enumerate(visible) if selected and r['pid']==selected['pid']),-1)
        index=max(0,min(len(visible)-1,index+delta)); selected=visible[index]
        table.yview_moveto(max(0,(index*64-table.winfo_height()/2)/max(1,len(visible)*64))); draw_rows()
    table.bind('<Down>',lambda _:key_select(1)); table.bind('<Up>',lambda _:key_select(-1))
    table.bind('<MouseWheel>',lambda e:table.yview_scroll(-int(e.delta/120),'units'))
    def receive_icon(payload):
        nonlocal redraw_scheduled
        current,icon_id,png=payload
        if current!=generation or not png:return
        try:
            images[icon_id]=tk.PhotoImage(data=png)
            while len(images)>256:images.popitem(last=False)
            # Coalesce a batch of completed icons into one redraw, keeping input responsive.
            if not redraw_scheduled:
                redraw_scheduled=True
                root.after_idle(redraw_icons)
        except tk.TclError:pass
    def redraw_icons():
        nonlocal redraw_scheduled
        redraw_scheduled=False
        draw_rows()
    def display_processes(data):
        nonlocal rows,generation,selected,process_list_limited
        process_list_limited=agent_build<407 and len(data)==150
        generation+=1; current=generation; previous=selected; rows=process_groups.group(data)
        selected=next((r for r in rows if previous and process_groups.key(r)==process_groups.key(previous)),None)
        filter_rows(); banner.set('Aplicativos agrupados. Confira os detalhes antes de encerrar.' if rows else 'Nenhum processo elegível para encerramento.')
        if process_list_limited:banner.set('O agente anterior limita a lista a 150 processos. Atualize o componente administrador em Configurações para obter a lista completa.')
        for icon_id in dict.fromkeys(r.get('icon_id') for r in rows):
            if not icon_id or icon_id in images:continue
            def load(key=icon_id):
                for attempt in range(8):
                    if closed or current!=generation:return current,key,None
                    data=api('process-icons/'+key)
                    if data['state']!='pending':return current,key,data.get('png')
                    time.sleep(.2*(attempt+1))
                return current,key,None
            task(('icon',current,icon_id),load,receive_icon,quiet=True,executor=icon_pool)
    def refresh_processes():
        task('processes',lambda:api('processes'),display_processes)
        task('status',lambda:api('status'),show_status,quiet=True)

    pair_card=card(pages['connection']); pair_card.pack(fill='x',pady=(2,0))
    label(pair_card,'Conectar Android',17,bold=True).pack(anchor='w')
    label(pair_card,'Selecione o adaptador Ethernet ligado ao roteador.',11,MUTED).pack(anchor='w',pady=(8,18))
    choices=[]
    for name,addresses in psutil.net_if_addrs().items():
        mac=next((a.address for a in addresses if a.family==psutil.AF_LINK),'')
        for address in addresses:
            if address.family==socket.AF_INET and not address.address.startswith('127.') and address.netmask:
                choices.append((name,address.address,mac,str(ipaddress.IPv4Network(f'{address.address}/{address.netmask}',strict=False).broadcast_address)))
    selector=ttk.Combobox(pair_card,state='readonly',values=[f'{v[0]} — {v[1]}' for v in choices]); selector.pack(fill='x')
    if choices:selector.current(0)
    code=tk.Text(pair_card,height=6,wrap='char',bg=BG,fg=TEXT,insertbackground=TEAL,relief='flat',padx=14,pady=14,font=('Consolas',10)); code.pack(fill='x',pady=16)
    def generate():
        if selector.current()<0:banner.set('Nenhum adaptador disponível.');return
        _,host,mac,broadcast=choices[selector.current()]
        code.delete('1.0','end'); code.insert('1.0',pairing(host,mac,broadcast)); banner.set('Código privado gerado. Cole somente no seu aplicativo Android.')
    def copy():
        value=code.get('1.0','end').strip()
        if not value:banner.set('Gere o código de conexão primeiro.');return
        root.clipboard_clear(); root.clipboard_append(value); banner.set('Código copiado. No Android, abra Ajustes → Conectar PC.')
    Button(pair_card,'Gerar código de conexão',generate,kind='connection',accent=True).pack(fill='x',pady=(0,10))
    Button(pair_card,'Copiar código',copy).pack(fill='x')
    hint=label(pair_card,'O código contém sua credencial. Use apenas na rede privada e não o compartilhe. Wake-on-LAN continua disponível pelo Android com o PC desligado.',10,MUTED)
    hint.configure(wraplength=670); hint.pack(fill='x',pady=(16,0))
    logtext=tk.Text(pages['history'],wrap='word',bg=PANEL,fg=MUTED,relief='flat',padx=20,pady=20,font=('Consolas',10),state='disabled')
    logtext.pack(fill='both',expand=True,pady=(2,12))
    def display_logs(data):
        logtext.configure(state='normal'); logtext.delete('1.0','end'); logtext.insert('1.0','\n'.join(data['lines']) or 'Nenhum evento registrado.'); logtext.configure(state='disabled'); banner.set('Histórico atualizado.')
    def refresh_logs():task('logs',lambda:api('logs'),display_logs)
    Button(pages['history'],'Atualizar histórico',refresh_logs,kind='refresh').pack(fill='x')
    def close():
        nonlocal closed
        if closed:return
        if listener:listener.close()
        if tray:tray.close()
        closed=True; launch_pool.shutdown(wait=False,cancel_futures=True); pool.shutdown(wait=False,cancel_futures=True); icon_pool.shutdown(wait=False,cancel_futures=True); root.destroy()
    def restore():
        if closed:return
        root.deiconify();root.lift();root.focus_force()
    def hide_to_tray(attempt=0):
        if closed:return
        if tray and tray.hide(root.withdraw):return
        if tray and not tray.error and attempt<20:
            root.after(100,lambda:hide_to_tray(attempt+1));return
        restore();banner.set('Bandeja indisponível. Use “Encerrar AURA” nos Ajustes para sair.')
    def quit_application():
        nonlocal quitting,listener
        if closed or quitting:return
        if 'admin-setup' in pending:
            restore();banner.set('Conclua ou cancele a configuração de administrador antes de encerrar.');return
        if installing_update:
            restore();banner.set('Aguarde a conclusão da atualização para encerrar.');return
        quitting=True
        if listener:listener.close();listener=None
        voice_meter.set_level(0)
        def finish(result):
            nonlocal quitting
            if result:
                quitting=False;restore();banner.set('Não foi possível encerrar o agente: '+result);start_voice();return
            close()
        def stop():
            from .tray import stop_agent
            try:
                deadline=time.monotonic()+22
                while 'start' in pending:
                    if time.monotonic()>=deadline:raise RuntimeError('Aguarde a inicialização do agente e tente novamente.')
                    time.sleep(.05)
                stop_agent(api,psutil.Process,os.getpid());return None
            except Exception as exc:return str(exc)
        task('quit',stop,finish,quiet=True)
    def tray_request(action):
        if action=='exit':quit_application()
        else:restore()
    Button(pages['connection'],'Encerrar AURA',quit_application).pack(fill='x',pady=(14,0))
    if '--check-ui' not in sys.argv:
        from .tray import Tray
        tray=Tray(lambda action:events.put(('tray-event',tray_request,action,None,True)))
    root.protocol('WM_DELETE_WINDOW',hide_to_tray); navigate('home'); drain()
    if '--check-ui' in sys.argv:
        from .native_runtime import DATA
        (DATA/'ui-check.txt').write_text('OK',encoding='utf-8'); root.after(100,close)
    else:
        root.after(200,configure_startup)
        root.after(400,start_agent)
        root.after(1000,start_voice)
        root.after(600,periodic_catalog)
        root.after(1200,bridge_poll)
        root.after(2000,periodic_updates)
        if '--startup' in sys.argv:root.after(100,hide_to_tray)
    root.mainloop()


if __name__=='__main__':main()
