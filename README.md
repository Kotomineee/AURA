# AURA 0.4.0-dev — Aplicativos Windows e Android

Primeiro incremento nativo, baseado na Especificação do Assistente Pessoal v1
e na orientação de 20/10/2026: as interfaces principais são aplicativos Windows
e Android. O painel web da 0.3.1 é somente o protótipo anterior.

## O que está implementado neste incremento

- Janela nativa no Windows, com controles locais, processos e conexão do Android.
- Aplicativo Android nativo em Kotlin, sem WebView e sem aplicativo de terceiros.
- Wake-on-LAN enviado diretamente pelo Android, mesmo com o PC desligado.
- Comunicação HTTPS com credencial e identidade do PC conferida pelo certificado.
- CPU/RAM, processos elegíveis, desligamento confirmado e reinicialização.
- Agendamento persistente em SQLite e cancelamento.
- Registro de ações com rotação e consulta nas duas interfaces.
- Agente em processo separado: fechar a janela Windows não o encerra.

Voz, abertura de aplicativos/sites, teclado/mouse, Discord, screenshots, GPU,
temperaturas, rotinas e acesso externo ainda não estão implementados.
O mapa completo está em docs/ESPECIFICACAO.md. Esta é uma versão de desenvolvimento,
não uma implementação concluída de toda a especificação.

## Como os aplicativos se conectam

O Windows executa o agente HTTPS na porta 8765. A interface Windows se conecta
por loopback. O Android se conecta pelo endereço da placa Ethernet na LAN.
As duas interfaces usam a mesma API e o mesmo estado de agendamento.

No Windows, abra Conectar Android, selecione o adaptador Ethernet e gere o
código. Cole esse código em Conectar PC no Android. Ele contém endereço, MAC,
broadcast, credencial aleatória e impressão digital do certificado. É privado:
não publique, não inclua em screenshots e não envie ao GitHub.

O Android guarda a configuração criptografada com chave no Android Keystore.
Ele aceita somente o certificado copiado do PC. Uma alteração de IP exige gerar
e importar novo código; uma renovação de certificado também exige reconexão.
O certificado inicial vale por um ano. A autenticação deste incremento usa uma
credencial compartilhada por instalação; revogação individual e QR code ficam
para um próximo incremento. Para revogar todas as conexões, encerre o agente,
remova identity.json da pasta de dados e reabra o aplicativo.

## Instalar no Windows a partir do código

Requer Windows 11 e Python 3.11+ com Tcl/Tk (incluído no instalador oficial).
Extraia o ZIP em uma pasta nova. Execute Instalar AURA.cmd e depois Iniciar AURA.cmd.
Também é possível abrir esta pasta no VS Code e executar:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe launch_windows.py
```

Na janela, clique em Iniciar / conectar agente. O modo inicial é SIMULAÇÃO.
O botão Ativar modo real, disponível no Windows, habilita ações reais nos dois
aplicativos. A mudança exige uma confirmação explícita. Wake-on-LAN do Android
é independente desse modo e sempre envia o pacote ao tocar em Ligar PC.

O agente é um processo da sessão do usuário, não um serviço Windows de sistema.
Ele continua ao fechar a janela, mas ainda não inicia automaticamente após login
ou reinício. Depois de ligar o PC por Wake-on-LAN, abra a AURA e inicie o agente
para usar os demais comandos. Inicialização automática é um próximo requisito.
Para diagnóstico: execute .\.venv\Scripts\python.exe -m app.native_agent no terminal.
Para encerrá-lo, use Ctrl+C quando iniciado pelo terminal ou encerre o processo
da AURA com --agent no Gerenciador de Tarefas quando iniciado pela interface.

As configurações, certificado, chave, logs e banco ficam em %LOCALAPPDATA%\AURA.
O arquivo settings.env nessa pasta guarda o modo de simulação. O .env da 0.3.1
não é necessário para a autenticação nativa; o agente gera sua própria credencial.
Não execute múltiplas instâncias do agente na mesma porta/pasta de dados.

## Rede local e firewall

PC por Ethernet e Android no Wi-Fi principal da mesma rede. Permita o aplicativo
somente em redes privadas no Firewall do Windows. A porta TCP usada é 8765.
O instalador não altera o firewall. A permissão pode exigir administrador.
Não configure redirecionamento de porta no roteador nem exponha a API na internet.
VPN e acesso externo serão validados em outra etapa.

O emissor do Android usa explicitamente uma interface Wi-Fi disponível para enviar
o pacote UDP. O PC precisa ter Wake-on-LAN habilitado na BIOS e no driver Ethernet.
Teste primeiro a partir da suspensão. O estado desligado depende do hardware e do
driver. Um pacote enviado não confirma que o computador acordou.

## Android e APK

Código em android/. Requer JDK 17, Android SDK 35, Gradle 8.11.1 e AGP 8.9.2.
O projeto usa Kotlin 2.1.10 e Android 8+ (API 26+). O Samsung S20 FE é o aparelho
de teste previsto; o funcionamento real ainda exige validação nele.

O workflow Aplicativos AURA no GitHub Actions compila um APK debug e o aplicativo
Windows portátil. Quando a execução estiver verde, os arquivos estarão em Artifacts.
Uma execução iniciada ou um projeto gerado não equivalem a uma compilação aprovada.
O APK é de desenvolvimento e não possui assinatura de distribuição estável.

Para compilar manualmente com Gradle instalado:

```powershell
cd android
gradle :app:assembleDebug :app:lintDebug
```

Saída: android/app/build/outputs/apk/debug/app-debug.apk.
Este repositório não inclui os binários do Gradle Wrapper; use a versão indicada
ou o workflow. Nenhum segredo de assinatura é publicado.

## Agendamentos e confirmações

Desligamento imediato e criação de agendamento exigem confirmação. Reiniciar e
encerrar o processo explicitamente selecionado não pedem confirmação rotineira.
O modo real pode encerrar sua sessão; salve seu trabalho.

Prazos futuros sobrevivem ao reinício do agente. Prazos vencidos enquanto o agente
estava parado são cancelados e registrados no log, evitando desligamento surpresa
ao iniciar o aplicativo. Agendamentos criados em simulação nunca são promovidos a
ações reais. Cada comando de alteração recebe um UUID para reduzir duplicações;
comandos com resultado incerto não são repetidos automaticamente.

## Verificação

tools/check_native.py usa pasta temporária e comandos de energia substituídos
por simulações. Verifica autenticação, validação, duplicação, persistência,
cancelamento, prazo, conexão e restrição de modo real ao cliente local.
Não existe pasta tests. Para executá-lo, instale httpx além de requirements.txt.

Também são necessários testes manuais: Android e Windows na mesma LAN, Wi-Fi sem
internet, firewall, fechamento da janela, reinício do agente, modos de energia,
instalação dos binários e reconexão após mudança de IP. Ainda não há testes de voz,
pois esse módulo não faz parte deste incremento.
