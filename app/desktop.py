"""Native Windows UI; closing the window leaves the separate HTTPS agent running."""
import json
import os
from pathlib import Path
import ssl
import subprocess
import sys
import threading
import urllib.request
import urllib.error
import uuid

from .native_runtime import PORT, identity, pairing


def main():
    if '--agent' in sys.argv:
        from .native_agent import run
        run()
        return
    import tkinter as tk
    from tkinter import ttk, messagebox
    import psutil
    import socket
    import ipaddress

    root = tk.Tk()
    root.title('AURA • Windows • 0.4.0-dev')
    root.geometry('850x680')
    root.minsize(700, 560)
    root.configure(bg='#101827')
    style = ttk.Style()
    style.theme_use('clam')
    style.configure('.', font=('Segoe UI', 11), background='#101827', foreground='#e6edf8')
    style.configure('TButton', padding=10, background='#263d61')
    style.configure('TEntry', fieldbackground='#f3f6fc', foreground='#101827')
    style.configure('Treeview', fieldbackground='#172338', background='#172338', foreground='white', rowheight=28)
    settings = identity()
    context = ssl.create_default_context(cafile=settings['cert'])
    banner = tk.StringVar(value='Inicie o agente para conectar. Fechar a janela mantém o agente ativo.')
    metrics = tk.StringVar(value='Computador desconectado')
    ttk.Label(root, text='AURA', font=('Segoe UI', 25, 'bold')).pack(anchor='w', padx=24, pady=(20, 8))
    ttk.Label(root, textvariable=metrics).pack(anchor='w', padx=24)
    tabs = ttk.Notebook(root)
    tabs.pack(fill='both', expand=True, padx=20, pady=16)
    control, procs, pair, history = [ttk.Frame(tabs, padding=16) for _ in range(4)]
    for frame, title in [(control,'Controle do PC'),(procs,'Processos'),(pair,'Conectar Android'),(history,'Histórico')]:
        tabs.add(frame, text=title)
    ttk.Label(root, textvariable=banner, wraplength=800).pack(fill='x', padx=24, pady=(0,16))

    def api(path, body=None):
        payload = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request('https://127.0.0.1:' + str(PORT) + '/api/' + path, data=payload,
            headers={'Authorization': 'Bearer ' + settings['token'], 'Content-Type': 'application/json',
                     'X-Command-ID': str(uuid.uuid4())}, method='POST' if body is not None else 'GET')
        try:
            with urllib.request.urlopen(request, context=context, timeout=10) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            try:
                detail = json.load(exc).get('detail', 'Falha no comando')
            except (ValueError, OSError):
                detail = 'Falha no comando'
            raise RuntimeError(str(detail)) from None

    def task(fn, callback):
        banner.set('Conectando…')
        def work():
            try:
                result = fn()
                root.after(0, lambda: callback(result))
            except Exception as exc:
                message = 'Não foi possível concluir: ' + str(exc)
                root.after(0, lambda: banner.set(message))
        threading.Thread(target=work, daemon=True).start()

    def show_status(data):
        mode = 'SIMULAÇÃO' if data['dry_run'] else 'MODO REAL'
        metrics.set(f"{data['hostname']} • CPU {data['cpu']}% • RAM {data['ram']}% • {mode}")
        if data['shutdown_at']:
            from datetime import datetime
            banner.set('Desligamento: ' + datetime.fromtimestamp(data['shutdown_at']).strftime('%d/%m %H:%M:%S'))
        else:
            banner.set('Conectado. Nenhum desligamento agendado.')

    def refresh():
        task(lambda: api('status'), show_status)

    def start_agent():
        def start():
            try:
                return api('status')
            except (OSError, RuntimeError):
                pass
            if getattr(sys, 'frozen', False):
                args = [sys.executable, '--agent']
            else:
                executable = Path(sys.executable).with_name('pythonw.exe')
                args = [str(executable if executable.exists() else sys.executable), '-m', 'app.desktop', '--agent']
            flags = (subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS) if os.name == 'nt' else 0
            subprocess.Popen(args, cwd=Path(__file__).resolve().parents[1], creationflags=flags,
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            import time
            for _ in range(20):
                time.sleep(.5)
                try:
                    return api('status')
                except (OSError, RuntimeError):
                    continue
            raise RuntimeError('O agente não iniciou. Execute python -m app.native_agent para ver o erro.')
        task(start, show_status)

    def action(path, body):
        task(lambda: api(path, body), lambda data: banner.set(data['message']))

    ttk.Button(control, text='Iniciar / conectar agente', command=start_agent).pack(fill='x', pady=5)
    ttk.Button(control, text='Atualizar estado', command=refresh).pack(fill='x', pady=5)
    ttk.Button(control, text='Ativar simulação', command=lambda: action('mode', {'dry_run':True})).pack(fill='x', pady=5)
    ttk.Button(control, text='Ativar modo real', command=lambda: action('mode', {'dry_run':False})
               if messagebox.askyesno('Modo real', 'Habilitar ações reais no Windows para os dispositivos conectados?') else None).pack(fill='x', pady=5)
    ttk.Button(control, text='Desligar PC', command=lambda: action('power', {'action':'shutdown','confirm':True})
               if messagebox.askyesno('Desligar PC', 'Confirmar desligamento deste PC? Salve seus arquivos.') else None).pack(fill='x', pady=5)
    ttk.Button(control, text='Reiniciar PC', command=lambda: action('power', {'action':'restart'})).pack(fill='x', pady=5)
    ttk.Label(control, text='Minutos até desligar:').pack(anchor='w', pady=(16,4))
    minutes = ttk.Entry(control)
    minutes.insert(0,'30')
    minutes.pack(fill='x')
    def schedule():
        try:
            value = int(minutes.get())
            if not 1 <= value <= 10080:
                raise ValueError()
        except ValueError:
            banner.set('Informe de 1 a 10080 minutos.')
            return
        if messagebox.askyesno('Agendar', f'Confirmar desligamento em {value} minutos?'):
            action('shutdown', {'delay_seconds':value*60,'confirm':True})
    ttk.Button(control, text='Agendar desligamento', command=schedule).pack(fill='x', pady=5)
    ttk.Button(control, text='Cancelar agendamento', command=lambda: action('shutdown/cancel', {})).pack(fill='x', pady=5)

    tree = ttk.Treeview(procs, columns=('name','pid','ram'), show='headings')
    for col, title in [('name','Aplicativo'),('pid','PID'),('ram','RAM MB')]:
        tree.heading(col, text=title)
    tree.pack(fill='both', expand=True)
    items = {}
    def display_processes(rows):
        tree.delete(*tree.get_children())
        items.clear()
        for row in rows:
            key = tree.insert('', 'end', values=(row['name'],row['pid'],row['ram_mb']))
            items[key] = row
        banner.set('Selecione o processo exato para encerrar. Alterações não salvas podem ser perdidas.')
    ttk.Button(procs, text='Atualizar processos', command=lambda: task(lambda: api('processes'), display_processes)).pack(fill='x')
    def terminate():
        selection = tree.selection()
        if selection:
            action('processes/terminate', items[selection[0]])
    ttk.Button(procs, text='Encerrar processo selecionado', command=terminate).pack(fill='x')

    ttk.Label(pair, text='Selecione o adaptador Ethernet que liga este PC ao roteador.', wraplength=700).pack(anchor='w')
    choices = []
    for name, addresses in psutil.net_if_addrs().items():
        mac = next((a.address for a in addresses if a.family == psutil.AF_LINK), '')
        for address in addresses:
            if address.family == socket.AF_INET and not address.address.startswith('127.') and address.netmask:
                choices.append((name, address.address, mac, str(ipaddress.IPv4Network(f'{address.address}/{address.netmask}', strict=False).broadcast_address)))
    selector = ttk.Combobox(pair, state='readonly', values=[f'{v[0]} — {v[1]}' for v in choices])
    selector.pack(fill='x', pady=10)
    if choices:
        selector.current(0)
    code = tk.Text(pair, height=8, wrap='char')
    code.pack(fill='x', pady=10)
    def generate():
        if selector.current() < 0:
            banner.set('Nenhum adaptador disponível.')
            return
        _, host, mac, broadcast = choices[selector.current()]
        code.delete('1.0','end')
        code.insert('1.0', pairing(host,mac,broadcast))
        banner.set('Código privado: contém a credencial de acesso. Cole somente no seu aplicativo Android.')
    ttk.Button(pair, text='Gerar código de conexão', command=generate).pack(fill='x', pady=5)
    def copy():
        root.clipboard_clear()
        root.clipboard_append(code.get('1.0','end').strip())
        banner.set('Código copiado. No Android, use Conectar PC.')
    ttk.Button(pair, text='Copiar código', command=copy).pack(fill='x', pady=5)
    ttk.Label(pair, text='O celular precisa alcançar este PC pela rede local. Se o Windows pedir acesso à rede, permita somente a rede privada. Wake-on-LAN continua disponível no Android com o PC desligado.', wraplength=700).pack(pady=12)
    logtext = tk.Text(history, wrap='word')
    logtext.pack(fill='both', expand=True)
    def display_logs(data):
        logtext.delete('1.0','end')
        logtext.insert('1.0','\n'.join(data['lines']))
        banner.set('Últimos eventos do agente.')
    ttk.Button(history, text='Atualizar histórico', command=lambda: task(lambda: api('logs'), display_logs)).pack(fill='x')
    root.mainloop()


if __name__ == '__main__':
    main()
