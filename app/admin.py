"""Install the elevated agent in an administrator-protected location.

The desktop stays unelevated. A single UAC-approved installation registers a
fixed scheduled action; no user-writable executable is run at highest privilege.
"""
import base64
import csv
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import zipfile
from .version import BUILD


def system_directory():
    buffer=ctypes.create_unicode_buffer(32768)
    if not ctypes.windll.kernel32.GetSystemDirectoryW(buffer,len(buffer)):raise ctypes.WinError()
    return Path(buffer.value)


def sid():
    result=subprocess.run([str(system_directory()/'whoami.exe'),'/user','/fo','csv','/nh'],capture_output=True,text=True,check=True,creationflags=subprocess.CREATE_NO_WINDOW)
    value=next(csv.reader([result.stdout.strip()]))[-1]
    if not re.fullmatch(r'S-1-5-21-(?:\d+-){2}\d+-\d+',value):raise OSError('Conta Windows não compatível com a configuração automática.')
    return value


def task_name():return 'AURA-Agent-'+sid()


def run_elevated(powershell, script):
    from ctypes import wintypes as w
    class ExecuteInfo(ctypes.Structure):
        _fields_=[('cbSize',w.DWORD),('fMask',w.ULONG),('hwnd',w.HWND),('lpVerb',w.LPCWSTR),('lpFile',w.LPCWSTR),('lpParameters',w.LPCWSTR),('lpDirectory',w.LPCWSTR),('nShow',ctypes.c_int),('hInstApp',w.HINSTANCE),('lpIDList',ctypes.c_void_p),('lpClass',w.LPCWSTR),('hkeyClass',w.HKEY),('dwHotKey',w.DWORD),('hIcon',w.HANDLE),('hProcess',w.HANDLE)]
    encoded=base64.b64encode(script.encode('utf-16-le')).decode('ascii')
    arguments='-NoProfile -NonInteractive -EncodedCommand '+encoded
    if len(arguments)>30000:raise OSError('Configuração excedeu o limite de instalação.')
    info=ExecuteInfo();info.cbSize=ctypes.sizeof(info);info.fMask=0x40
    info.lpVerb='runas';info.lpFile=str(powershell);info.lpParameters=arguments;info.nShow=0
    shell=ctypes.WinDLL('shell32',use_last_error=True)
    shell.ShellExecuteExW.argtypes=[ctypes.POINTER(ExecuteInfo)];shell.ShellExecuteExW.restype=w.BOOL
    if not shell.ShellExecuteExW(ctypes.byref(info)):raise OSError('A autorização de administrador foi cancelada ou não está disponível.')
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.WaitForSingleObject.argtypes=[w.HANDLE,w.DWORD];kernel.WaitForSingleObject.restype=w.DWORD
    kernel.GetExitCodeProcess.argtypes=[w.HANDLE,ctypes.POINTER(w.DWORD)];kernel.GetExitCodeProcess.restype=w.BOOL
    kernel.CloseHandle.argtypes=[w.HANDLE];kernel.CloseHandle.restype=w.BOOL
    try:
        if kernel.WaitForSingleObject(info.hProcess,0xFFFFFFFF)!=0:raise ctypes.WinError(ctypes.get_last_error())
        code=w.DWORD()
        if not kernel.GetExitCodeProcess(info.hProcess,ctypes.byref(code)):raise ctypes.WinError(ctypes.get_last_error())
        return code.value
    finally:kernel.CloseHandle(info.hProcess)


def configured():
    if os.name!='nt':return False
    from .native_runtime import DATA
    try:
        installed=json.loads((DATA/'admin.json').read_text(encoding='utf-8')).get('build')
        return type(installed) is int and 405<=installed<=BUILD
    except (OSError,ValueError):return False


def start():
    result=subprocess.run([str(system_directory()/'schtasks.exe'),'/Run','/TN',task_name()],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:raise OSError('A tarefa de administrador não iniciou. Reconfigure o administrador automático na AURA.')


def installation_script(archive, digest, account_sid, identity_archive=None, identity_digest=None):
    if not re.fullmatch('[a-f0-9]{64}',digest):raise ValueError('Hash inválido')
    if not re.fullmatch(r'S-1-5-21-(?:\d+-){2}\d+-\d+',account_sid):raise ValueError('SID inválido')
    source=str(archive).replace("'","''")
    if identity_digest is not None and not re.fullmatch('[a-f0-9]{64}',identity_digest):raise ValueError('Hash de identidade inválido')
    return r'''
$ErrorActionPreference='Stop'
$identity=[Security.Principal.WindowsIdentity]::GetCurrent()
if ($identity.User.Value -ne '__SID__') { throw 'Use a mesma conta Windows para autorizar a instalação.' }
$principal=[Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'Administrador necessário.' }
$programFiles=[Environment]::GetFolderPath('ProgramFiles')
$base=Join-Path $programFiles 'AURA-Agent'
$destination=Join-Path $base ('__BUILD__-'+[Guid]::NewGuid().ToString('N'))
foreach ($path in @($programFiles,$base,$destination)) {
    if ((Test-Path -LiteralPath $path) -and ((Get-Item -LiteralPath $path -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'Diretório redirecionado recusado.' }
}
New-Item -ItemType Directory -Path $base -Force | Out-Null
$acl=[Security.AccessControl.DirectorySecurity]::new()
$acl.SetAccessRuleProtection($true,$false)
$inherit=[Security.AccessControl.InheritanceFlags]'ContainerInherit,ObjectInherit'
foreach ($entry in @(@('S-1-5-18','FullControl'),@('S-1-5-32-544','FullControl'),@('S-1-5-32-545','ReadAndExecute'))) {
    $rule=[Security.AccessControl.FileSystemAccessRule]::new([Security.Principal.SecurityIdentifier]::new($entry[0]),[Security.AccessControl.FileSystemRights]$entry[1],$inherit,[Security.AccessControl.PropagationFlags]::None,[Security.AccessControl.AccessControlType]::Allow)
    $acl.AddAccessRule($rule)
}
$acl.SetOwner([Security.Principal.SecurityIdentifier]::new('S-1-5-32-544'))
Set-Acl -LiteralPath $base -AclObject $acl
if (Test-Path -LiteralPath $destination) { throw 'Esta versão já está instalada. Reinicie o Windows ou use reparar configuração.' }
New-Item -ItemType Directory -Path $destination | Out-Null
$payload=Join-Path $destination 'payload.zip'
Copy-Item -LiteralPath '__SOURCE__' -Destination $payload
if ((Get-FileHash -LiteralPath $payload -Algorithm SHA256).Hash.ToLowerInvariant() -ne '__HASH__') { throw 'Arquivo de instalação inválido.' }
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip=[IO.Compression.ZipFile]::OpenRead($payload)
try {
    $total=0L
    foreach ($entry in $zip.Entries) {
        $target=[IO.Path]::GetFullPath((Join-Path $destination $entry.FullName))
        if (-not $target.StartsWith($destination+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)) { throw 'Caminho inválido no pacote.' }
        $total+=$entry.Length
        if ($total -gt 500MB) { throw 'Pacote excedeu o limite.' }
    }
} finally { $zip.Dispose() }
[IO.Compression.ZipFile]::ExtractToDirectory($payload,$destination)
Remove-Item -LiteralPath $payload
$exe=Join-Path $destination 'AURA-Agent.exe'
if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) { throw 'Agente ausente.' }
$state=Join-Path $destination 'state'
New-Item -ItemType Directory -Path $state | Out-Null
$stateAcl=[Security.AccessControl.DirectorySecurity]::new()
$stateAcl.SetAccessRuleProtection($true,$false)
foreach ($entry in @(@('S-1-5-18','FullControl'),@('S-1-5-32-544','FullControl'),@('__SID__','ReadAndExecute'))) {
    $stateAcl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new([Security.Principal.SecurityIdentifier]::new($entry[0]),[Security.AccessControl.FileSystemRights]$entry[1],$inherit,[Security.AccessControl.PropagationFlags]::None,[Security.AccessControl.AccessControlType]::Allow))
}
$stateAcl.SetOwner([Security.Principal.SecurityIdentifier]::new('S-1-5-32-544'))
Set-Acl -LiteralPath $state -AclObject $stateAcl
$identityZip=Join-Path $destination 'identity.zip'
Copy-Item -LiteralPath '__IDENTITY_SOURCE__' -Destination $identityZip
if ((Get-FileHash -LiteralPath $identityZip -Algorithm SHA256).Hash.ToLowerInvariant() -ne '__IDENTITY_HASH__') { throw 'Identidade inválida.' }
$identityPackage=[IO.Compression.ZipFile]::OpenRead($identityZip)
try {
    foreach ($entry in $identityPackage.Entries) {
        if ($entry.FullName -notin @('identity.json','server.crt','server.key','settings.env') -or $entry.Length -gt 65536) { throw 'Arquivo de identidade inválido.' }
    }
} finally { $identityPackage.Dispose() }
[IO.Compression.ZipFile]::ExtractToDirectory($identityZip,$state)
Remove-Item -LiteralPath $identityZip
$action=New-ScheduledTaskAction -Execute $exe -Argument '--agent' -WorkingDirectory $destination
$trigger=New-ScheduledTaskTrigger -AtLogOn -User '__SID__'
$user=New-ScheduledTaskPrincipal -UserId '__SID__' -LogonType Interactive -RunLevel Highest
$settings=New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero)
Register-ScheduledTask -TaskName 'AURA-Agent-__SID__' -Action $action -Trigger $trigger -Principal $user -Settings $settings -Force | Out-Null
$scheduler=New-Object -ComObject 'Schedule.Service'
$scheduler.Connect()
$task=$scheduler.GetFolder('\').GetTask('AURA-Agent-__SID__')
$task.SetSecurityDescriptor('D:P(A;;FA;;;SY)(A;;FA;;;BA)(A;;GRGX;;;__SID__)',0)
'''.replace('__SID__',account_sid).replace('__SOURCE__',source).replace('__HASH__',digest).replace('__BUILD__',str(BUILD)).replace('__IDENTITY_SOURCE__',str(identity_archive or archive).replace("'","''")).replace('__IDENTITY_HASH__',identity_digest or digest)


def install():
    if os.name!='nt' or not getattr(sys,'frozen',False):raise OSError('Disponível no aplicativo Windows empacotado.')
    base=Path(sys._MEIPASS)
    metadata=json.loads((base/'admin-agent.json').read_text(encoding='utf-8'))
    from .native_runtime import DATA
    temporary=tempfile.TemporaryDirectory(prefix='admin-setup-',dir=DATA)
    package=Path(temporary.name)/'identity.zip'
    with zipfile.ZipFile(package,'w',zipfile.ZIP_DEFLATED) as archive:
        for name in ('identity.json','server.crt','server.key','settings.env'):
            value=(DATA/name).read_bytes()
            if len(value)>65536:raise OSError('Identidade local inválida.')
            archive.writestr(name,value)
    script=installation_script(base/'admin-agent.zip',metadata['sha256'],sid(),package,hashlib.sha256(package.read_bytes()).hexdigest())
    powershell=system_directory()/'WindowsPowerShell/v1.0/powershell.exe'
    try:code=run_elevated(powershell,script)
    finally:temporary.cleanup()
    if code:raise OSError('A configuração não foi concluída. Autorize a solicitação do Windows usando sua conta de administrador.')
    (DATA/'admin.json').write_text(json.dumps({'build':BUILD}),encoding='utf-8')
