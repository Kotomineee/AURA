# AURA 0.1.2 — atualização automática (build 404)

Esta revisão substitui a primeira entrega 0.1.2/build 403. O nome continua 0.1.2; o número interno maior permite instalar por cima sem remover os dados.

## Atualização pelo aplicativo

AURA consulta somente Releases estáveis PUBLICADAS em Kotomineee/AURA. Ao encontrar uma versão pronta, mostra “Atualizar agora”. O próprio aplicativo baixa e verifica o arquivo. Não é necessário abrir o GitHub ou procurar um EXE/APK.

- Windows: baixa e confere o SHA-256, encerra o agente de forma controlada, aguarda a saída da interface, substitui o EXE e reabre a nova versão com conexão automática do agente. Mantém o arquivo anterior para recuperação. Falhas de troca ou de inicialização acionam recuperação quando possível; inicialização lenta mantém a cópia anterior disponível.
- Android: baixa o APK para armazenamento privado, verifica SHA-256, nome do pacote, versão e assinatura da instalação existente. Abre o instalador do Android. Na primeira vez, o usuário pode precisar autorizar a AURA a instalar atualizações; depois confirma a instalação do sistema. Se voltar ao app mais tarde, é possível retomar pelo botão “Instalar atualização baixada”.

O Windows não exige instalação manual de outro EXE pelo usuário. O Android exige a confirmação do sistema; não há tentativa de contorná-la. Os arquivos novos continuam sendo gerados na publicação de cada versão, mas o aplicativo cuida do download e da instalação.

A consulta ocorre ao abrir, a cada 15 minutos enquanto o aplicativo está aberto (Android: em primeiro plano), e pelo botão manual. Não existe aviso antes de publicar. Push de código, rascunhos, prévias ou Releases sem os DOIS aplicativos e hashes válidos são ignorados como atualização instalável.

## Primeira instalação desta correção

Instalar o APK build 404 por cima do anterior, sem desinstalar. Abrir o EXE novo uma vez. AURA configura a inicialização após login no Windows e conecta o agente automaticamente. Se um agente antigo ainda estiver ativo, reiniciar o Windows após a primeira abertura para carregar a versão atual.

Pareamento, certificado e configurações ficam preservados. O agente inicia APÓS entrar na conta Windows. O modo real/simulação salvo não é alterado. IP e certificado precisam continuar correspondendo ao pareamento.

## Publicar uma versão pronta

1. Gerar os dois aplicativos com a mesma identidade e assinatura de distribuição.
2. Gerar o manifesto a partir dos arquivos finais, com seus hashes reais.
3. Criar uma Release em RASCUNHO, tag v0.1.2 para esta versão, e anexar AURA-Windows-0.1.2.exe, AURA-Android-0.1.2.apk e aura-update.json.
4. Conferir os três arquivos e só então PUBLICAR como Release estável mais recente.

Na próxima consulta, aplicativos com build inferior recebem a oferta. Uma instalação build 404 não oferece a própria atualização. Para a próxima versão, aumentar o build acima de 404 e ajustar nome de versão e metadados. Nenhuma Release foi publicada nesta tarefa.

Gerar o manifesto depois da compilação, na raiz do projeto:

```powershell
python tools/make_update_manifest.py --windows dist/AURA-Windows-0.1.2.exe --android android/app/build/outputs/apk/debug/app-debug.apk --output aura-update.json
```

O manifesto registra os nomes dos arquivos recebidos. Se renomear o APK para AURA-Android-0.1.2.apk, faça isso ANTES de gerar o manifesto e publique com o mesmo nome. Não alterar ou recompilar os arquivos depois de gerar seus hashes sem regenerar o manifesto.

## Compilar Windows

Requer Python 3.12 com Tcl/Tk, no Windows:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt pyinstaller httpx
.\.venv\Scripts\python.exe tools/build_windows.py
```

Saída: dist/AURA-Windows-0.1.2.exe.

## Compilar Android

Requer JDK 17, Android SDK 35, build-tools 35.0.0 e Gradle 8.11.1 configurados. Não há Gradle Wrapper incluído.

```powershell
cd android
gradle :app:testDebugUnitTest :app:assembleDebug :app:lintDebug
```

Saída: android/app/build/outputs/apk/debug/app-debug.apk.

IMPORTANTE: manter a mesma chave de assinatura da instalação existente. As fontes não incluem a chave privada. Um APK de outro computador ou runner com outra chave debug será rejeitado pelo atualizador. O APK desta entrega usa a mesma chave local dos builds 402 e 403.

## Rede e dados

PC por Ethernet e Android no Wi-Fi da mesma rede. Código privado gerado no Windows em Conexão e importado em Ajustes → Conectar PC no Android. Permitir o aplicativo no Firewall apenas em rede privada (TCP 8765). Os dados persistem em %LOCALAPPDATA%\AURA; não remover essa pasta ao atualizar. Nenhuma credencial do pareamento é enviada ao GitHub.

O registro de inicialização pode ser desativado em Conexão no Windows. Ao executar o código-fonte em vez do EXE, a inicialização aponta para o interpretador e launch_windows.py; preservar essa pasta e o ambiente virtual. A instalação automática Windows exige o EXE.

## Verificação

```powershell
.\.venv\Scripts\python.exe tools/check_012.py
.\.venv\Scripts\python.exe tools/check_update_installer.py
.\.venv\Scripts\python.exe tools/check_native.py
.\.venv\Scripts\python.exe tools/check_icons.py
.\.venv\Scripts\python.exe tools/check_packaged_runtime.py dist/AURA-Windows-0.1.2.exe
```

Testes usam arquivos e registro simulados/isolados. Não alteram o aplicativo instalado nem repetem ações reais de energia. A atualização completa com reinício do aplicativo instalado e confirmação no celular deve ser conferida pelo usuário após publicar uma versão de teste estável e pronta.
