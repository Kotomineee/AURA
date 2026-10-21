# Correção de empacotamento Windows — 0.4.1

O executável inicial falhava ao criar `ssl.SSLContext`, antes de carregar o
certificado da instalação. O runtime Python usado nesta compilação carrega um
recurso próprio de certificados, `codex-rejected-cas.pem`, ao construir cada
contexto TLS. O empacotamento inicial não incluiu esse arquivo de acesso dinâmico.

O novo executável inclui o recurso no local esperado por `ssl.__file__`, mantendo
a validação TLS. A correção também está em `tools/build_windows.py` e há uma
checagem do pacote em `tools/check_packaged_runtime.py` para evitar regressão.

O diagnóstico `--check-runtime` cria uma identidade temporária, verifica os
contextos cliente/servidor, negocia TLS 1.3 com verificação de certificado e troca
dados usando `ssl.MemoryBIO`, inteiramente em memória. Também confere suporte PNG
e importação de Tkinter/psutil. Não cria Tk(), inicia agente, abre listener, conecta
à rede nem altera a identidade salva da AURA. Falhas são registradas como JSON e
encerram o diagnóstico sem abrir diálogo.

O próprio executável recompilado passou por esse diagnóstico, além da inspeção
de seus recursos e módulos. O arquivo com sufixo `-corrigido.exe` é uma cópia
idêntica da nova compilação, para distingui-la do download anterior. O APK não
precisou de alteração. Não houve teste da interface na área de trabalho.
