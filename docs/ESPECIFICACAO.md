# Especificação de referência e acompanhamento

Fonte: Especificacao_Assistente_Pessoal_v1.docx, versão 1.0, fornecida pelo usuário
em 20/10/2026. Este registro consolida requisitos; não substitui o documento original.
Orientação posterior prevalente: iniciar os aplicativos Windows e Android agora;
interface web serve apenas como protótipo visual anterior.

## Arquitetura decidida

- Agente Python na sessão Windows: API HTTPS, adaptadores Windows e estado persistente.
- Interface Windows nativa em Tkinter, com processo separado do agente.
- Interface Android nativa em Kotlin, com Wake-on-LAN local pelo celular.
- API comum para controles locais/remotos; estado vem sempre do agente.
- Identidade do PC transferida por código privado; credencial e certificado por instalação.
- Sem nuvem obrigatória para LAN. Acesso externo via VPN fica para validação posterior.

## Requisitos e estado no incremento 0.4.0-dev

| ID | Requisito | Estado |
|---|---|---|
| RF-01 | Interface PC e celular | Implementadas interfaces nativas iniciais; validação visual e em aparelhos pendente |
| RF-02 | Descobrir e abrir programas | Pendente; não executar comandos arbitrários |
| RF-03 | Encerrar alvo explícito | Reutiliza proteção da 0.3.1, nome, PID e horário de criação |
| RF-04 | Sites e atalhos, incluindo Gupy | Pendente |
| RF-05 | Energia e Wake-on-LAN | Implementados comandos; despertar físico ainda não validado |
| RF-06 | Agendamento persistente e cancelável | SQLite; prazos vencidos ao iniciar são cancelados e registrados |
| RF-07 | Logs com origem, horário e resultado | Log rotativo sem tokens; histórico nas interfaces |
| RF-08 | Palavra-chave GPT e voz offline | Pendente; microfone em segundo plano no Android é experimental |
| RF-09 | Sinônimos e alvo explícito | Pendente; apenas controles explícitos nesta entrega |
| RF-10 | Teclado e mouse | Pendente |
| RF-11 | Estado de mute Discord | Pendente; jamais alternar F12 para inferir estado |
| RF-12 | CPU, GPU, RAM, disco, temperaturas e processos | CPU, RAM e processos disponíveis; demais fontes pendentes |
| RF-13 | Screenshot sob demanda | Pendente; sem streaming contínuo |
| RF-14 | Rotinas e eventos verificáveis | Pendente |
| RF-15 | Acesso externo seguro | Pendente; nenhuma porta de controle publicada na internet |

## Regras preservadas

Desligar exige confirmação; agendar confirma uma vez e executa no prazo sem nova
pergunta; cancelar não precisa de confirmação. Encerrar exige alvo identificável,
nunca escolher automaticamente o que usa mais RAM. Mute desconhecido não permite
pressionar F12 por inferência; F12 explicitamente solicitado é outra operação.
O assistente é silencioso por padrão. Voz não foi simulada por botões ou anunciada
como disponível. O aplicativo não decide autonomamente ações destrutivas.

## Limites deste incremento

O agente permanece vivo após fechar a interface, mas inicialização automática após
login ainda falta. Credencial é compartilhada por instalação, sem lista de dispositivos
ou revogação individual. QR code, descoberta automática, reconexão por mudança de IP,
notificações e execução Android em segundo plano não foram implementados.

Não há promessa de Wake-on-LAN fora de casa. O emissor precisa continuar ligado
na rede do PC; o celular em casa atende esse requisito. Roteador não é configurado
automaticamente. O firmware e o hardware precisam ser testados.

## Critérios antes de ampliar os módulos

1. Compilar Windows e Android; instalar e abrir ambos no ambiente real.
2. Conectar por código, confirmar identidade e autenticação, testar sem internet.
3. Validar modo de simulação e depois energia real com arquivos salvos.
4. Confirmar persistência de agenda ao fechar a janela e reiniciar o agente.
5. Validar Wake-on-LAN no Samsung S20 FE, BIOS, driver e rede reais.
6. Registrar problemas conhecidos antes de avançar a abertura de apps/sites e voz.

Streaming estilo AnyDesk, atualização automática de programas, instalação sem
autorização, comercialização e assistente conversacional genérico permanecem fora
do escopo definido no documento.
