# VERA — Assistente pessoal para Windows

Protótipo **v0.1.0**: painel web local e serviço Python para Windows 11. Projeto em desenvolvimento, mantido privado nesta fase.

## Como executar no VS Code (PowerShell)

1. Instale Python 3.11+ e abra a pasta do projeto no VS Code.
2. Execute:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

3. No arquivo `.env`, troque `ASSISTANT_TOKEN` por um token aleatório longo. **Mantenha `DRY_RUN=true`**.
4. Inicie o servidor:

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

5. Abra http://127.0.0.1:8000, informe o token e conecte.

## Segurança

O protótipo inicia acessível apenas no próprio computador. **Não exponha o servidor à internet e não abra portas no roteador.** Para testar em celular na mesma rede doméstica confiável, use `--host 0.0.0.0` e configure o Firewall apenas para redes privadas. O HTTP local não cifra o token; uso remoto exigirá VPN privada ou HTTPS.

## Funcionalidades da versão inicial

- Indicadores de CPU e RAM.
- Lista de processos e solicitação de encerramento por PID/nome, com bloqueio básico de processos críticos.
- Agendamento e cancelamento de desligamento.
- Autenticação por token e modo de simulação por padrão.

## Limitações conhecidas

- `DRY_RUN=true` simula ações destrutivas; não encerra processos nem desliga o computador.
- Agendamentos ficam apenas em memória e são perdidos quando o servidor é fechado.
- Wake-on-LAN, abertura de aplicativos, histórico persistente e comandos por voz ainda não estão implementados.
- Desligamento real não foi validado em Windows; não habilite durante trabalho importante.
- Este projeto não é um produto pronto para uso em produção.

## Próximas etapas

Testar o painel no Windows 11, validar operações de leitura, corrigir problemas identificados e implementar gradualmente os módulos de controle e automação.
