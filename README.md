# VERA

VERA é um aplicativo de assistência pessoal desenvolvido para facilitar tarefas no computador por meio de uma interface web. A proposta é reunir funções de monitoramento, controle do sistema e automação em um só lugar, com a possibilidade de utilizar inteligência artificial e comandos de voz para executar ações de forma mais prática.

O projeto está em desenvolvimento. Nesta primeira versão, o foco é testar a comunicação entre a interface e o programa em Python que roda no Windows.

## Funcionalidades

Atualmente, a VERA permite:

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

A VERA ainda está em fase de testes e deve ser executada localmente. Não é recomendado disponibilizar o painel diretamente na internet.

Os agendamentos de desligamento ainda não são salvos: se o programa for fechado, eles serão perdidos. As funções que alteram o estado do Windows também precisam ser validadas antes de sair do modo de simulação.
