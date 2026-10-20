# VERA

Estou criando a VERA para facilitar algumas tarefas no meu computador. Quero conseguir acompanhar o uso do PC e controlar algumas coisas pelo navegador. Mais pra frente, a ideia é usar comandos de voz e IA para pedir ações sem precisar fazer tudo manualmente.

Ainda estou no começo do projeto. Por enquanto, já dá para ver o uso de CPU e memória, consultar os processos abertos e testar os controles de encerramento de processos e desligamento agendado.

**Os comandos que podem fechar programas ou desligar o computador estão em modo de simulação.** Eles ainda não fazem essas ações de verdade.

## Como testar

Estou usando Python e VS Code no Windows 11. Com o Python 3.11 ou mais recente instalado, abra a pasta no VS Code e execute no PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Abra o arquivo `.env` e troque o valor de `ASSISTANT_TOKEN` por uma senha longa. Deixe `DRY_RUN=true` para manter a simulação ativada.

Depois execute:

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

O painel abre em http://127.0.0.1:8000. É só informar o token configurado.

## O que ainda falta

Ainda quero adicionar a abertura de programas, comandos de voz, automações e acesso seguro pelo celular. Também preciso testar melhor os controles antes de permitir que façam alterações reais no Windows.

Por enquanto, o painel deve ser usado localmente. Não abra acesso a ele pela internet. Os desligamentos agendados também são perdidos quando o servidor é fechado.

Vou melhorando o projeto aos poucos e registrando as mudanças aqui.
