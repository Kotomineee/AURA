# AURA

AURA é um aplicativo de assistência pessoal desenvolvido para facilitar tarefas no computador por meio de uma interface web. A proposta é reunir funções de monitoramento, controle do sistema e automação em um só lugar, com a possibilidade de utilizar inteligência artificial e comandos de voz para executar ações de forma mais prática.

O projeto está em desenvolvimento. Nesta primeira versão, o foco é testar a comunicação entre a interface e o programa em Python que roda no Windows.

## Funcionalidades

Atualmente, a AURA permite:

- Consultar o uso de CPU e memória RAM.
- Visualizar os processos em execução.
- Solicitar o encerramento de um processo específico.
- Agendar ou cancelar o desligamento do computador.

**Importante:** o encerramento de processos e o desligamento ainda funcionam em modo de simulação. Os comandos podem ser testados pela interface, mas não executam essas ações no Windows.

## Instalação e execução

É necessário ter o Python 3.11 ou superior instalado. No Windows, abra a pasta do projeto no VS Code e execute os comandos abaixo no terminal PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

No arquivo `.env`, substitua o valor de `ASSISTANT_TOKEN` por uma senha longa. Para os primeiros testes, mantenha `DRY_RUN=true`.

Em seguida, inicie o programa:

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Com o servidor em execução, acesse http://127.0.0.1:8000 pelo navegador e informe o token configurado.

## Próximas funcionalidades

As próximas etapas incluem abertura de aplicativos, comandos de voz, automações de teclado e mouse, monitoramento mais detalhado e acesso seguro pelo celular.

A integração com IA também faz parte do planejamento, mas ainda não está disponível nesta versão.

## Observações

A AURA ainda está em fase de testes e deve ser executada localmente. Não é recomendado disponibilizar o painel diretamente na internet.

Os agendamentos de desligamento ainda não são salvos: se o programa for fechado, eles serão perdidos. As funções que alteram o estado do Windows também precisam ser validadas antes de sair do modo de simulação.


## AURA v0.3.1 — Wake-on-LAN (pré-lançamento)

Versão reconstruída a partir da v0.2.0 do repositório. Adiciona envio de magic
packet UDP, configuração validada no servidor, autenticação, confirmação e simulação.

No arquivo .env do **aparelho emissor**, adicione (valores de exemplo):
```dotenv
WOL_MAC=AA:BB:CC:DD:EE:02
WOL_BROADCAST=192.168.1.255
WOL_PORT=9
DRY_RUN=true
```
Use o MAC da placa Ethernet do PC alvo e o broadcast correto da sua sub-rede.
Reinicie a AURA após alterar a configuração. A tela Controle do PC indica se
o emissor está configurado. Com DRY_RUN=true, nenhum pacote é enviado.
Com DRY_RUN=false, o botão envia o pacote, sem confirmar que o PC ligou.

### Para ligar este PC quando ele estiver desligado
A AURA instalada apenas no PC alvo fica indisponível quando ele está desligado.
É necessário outro aparelho sempre ligado na mesma rede executando o emissor,
ou um roteador que tenha sua própria função Wake-on-LAN. Estar conectado por
cabo ao roteador, sozinho, não habilita essa função no roteador.
Esta versão não instala software no roteador nem configura BIOS ou drivers.
Se executar a AURA em outro aparelho, os controles de desligar/reiniciar afetam
o aparelho que executa a AURA; somente Wake-on-LAN usa WOL_MAC como alvo.

Ative Wake-on-LAN na BIOS/UEFI e Wake on Magic Packet no driver Ethernet,
conforme o fabricante. Acordar a partir de desligamento completo depende do
hardware, driver e estado de energia. Primeiro teste a partir da suspensão.
Consulte a [documentação Intel](https://www.intel.com/content/www/us/en/support/articles/000005793/ethernet-products.html).
Não exponha o painel diretamente à internet.

### Validação
Sete testes unitários isolados usam sockets e comandos de energia simulados.
Eles executam as funções de produção sem importar o framework HTTP; a integração
HTTP completa ainda precisa ser validada. Eles verificam
autenticação, confirmação, validação do destino, bytes do pacote, simulação e
tratamento de falhas. Não comprovam que o seu hardware acordará e não desligam
nem reiniciam uma máquina real.
