# AURA v0.3.1 — Pré-lançamento

Base: versão 0.2.0, com a mesma estrutura de arquivos e interface.
Adiciona emissor Wake-on-LAN e consulta de MAC/IP/broadcast no painel.
Esta versão precisa de testes no seu PC e na sua rede.

## Abrir no VS Code

Extraia o ZIP e abra a pasta AURA_v0.3.1, onde estão este README e requirements.txt.
No terminal PowerShell do VS Code:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Se já possui um .env, preserve-o em vez de substituir. Edite ASSISTANT_TOKEN
com uma senha longa de sua escolha. Mantenha DRY_RUN=true nos primeiros testes.

Inicie o painel:
```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Abra http://127.0.0.1:8000 e entre com o token do .env.
Para parar, pressione Ctrl+C no terminal.
O .env é carregado da raiz do projeto; reinicie o servidor depois de editá-lo.

## Configurar Wake-on-LAN no PC alvo

1. Com o PC ligado por Ethernet, abra Controle do PC > Ver dados de rede deste aparelho.
   Anote MAC, IP, máscara e broadcast da placa Ethernet física. Ignore interfaces
   virtuais, VPN e Wi-Fi. Esses dados são do aparelho que executa a AURA.
2. Habilite Wake-on-LAN/Power On by PCI-E na BIOS/UEFI, conforme o manual da placa-mãe.
3. Nas propriedades da placa Ethernet no Gerenciador de Dispositivos, procure
   Wake on Magic Packet e as permissões para o adaptador acordar o computador.
   Os nomes e opções variam por driver e fabricante.
4. Primeiro teste a partir da suspensão. Acordar após desligamento completo depende
   da placa-mãe, driver, alimentação da placa de rede e configurações de energia.
   Consulte o fabricante se funcionar em suspensão, mas não após desligar.

Referência: [Intel — Remote Wake-up Basics](https://www.intel.com/content/www/us/en/support/articles/000005793/ethernet-products.html).

## Usar o roteador como emissor

O PC desligado não consegue executar a AURA nem atender o painel.
O sinal precisa partir de outro aparelho ligado na rede.

Se o roteador tem uma função Wake-on-LAN, registre nela o MAC Ethernet do PC
e use o comando de acordar do próprio roteador. Alguns modelos pedem também
IP ou reserva DHCP. Estar conectado ao roteador por cabo não significa que
ele ofereça essa função. Esta versão não configura nem integra automaticamente
a interface administrativa do roteador. O procedimento exato depende do modelo
e firmware; consulte o manual do seu roteador.

## Usar a AURA como emissor em outro aparelho

Execute a AURA em outro computador ligado na mesma rede do PC alvo.
No .env desse emissor, configure:

```dotenv
WOL_MAC=AA:BB:CC:DD:EE:02
WOL_BROADCAST=192.168.1.255
WOL_PORT=9
DRY_RUN=true
```

Os endereços acima são exemplos: use o MAC do PC alvo e o broadcast da sua sub-rede.
Com DRY_RUN=true, o botão apenas simula o envio. Depois de conferir os valores,
mude DRY_RUN=false e reinicie o servidor para enviar o pacote de verdade.

**DRY_RUN=false também habilita as ações reais de desligar, reiniciar e encerrar
processos. Esses controles afetam o aparelho que executa a AURA; somente o
Wake-on-LAN usa WOL_MAC como alvo.**

Abra o painel no navegador do próprio emissor e clique em Enviar Wake-on-LAN.
A mensagem de envio significa que o pacote saiu, não que o PC já ligou.
Não exponha este painel diretamente à internet. O procedimento documentado
é para rede local; acesso externo exige uma solução de rede separada.

## Estrutura

```text
AURA_v0.3.1/
  .env.example
  .gitignore
  README.md
  requirements.txt
  app/
    main.py
    static/
      index.html
```

Há somente um README e um requirements, sem pasta tests.
Seu .env pessoal e a pasta .venv não fazem parte do pacote.

## Estado da versão

Pré-lançamento para teste manual. Não foram feitos testes físicos de despertar,
desligar ou reiniciar seu computador. A v0.2.0 continua sendo a base dos controles
de energia e processos. Agendamentos de desligamento ficam em memória e são
perdidos ao fechar o servidor.
