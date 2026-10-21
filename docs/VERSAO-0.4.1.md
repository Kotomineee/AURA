# AURA 0.4.1 — reformulação visual Windows e Android

## Referência aprovada

`REFERENCIA-APROVADA.png` é a imagem de design aprovada pelo usuário, **não uma
captura dos aplicativos implementados**. O tema usa fundo carvão `#0C1219`,
superfícies `#141D27`, contornos `#2C3B49`, texto `#F0F4FA`, texto secundário
`#A9BACB`, seleção `#16363E` e destaque verde-água `#31D0C3`.

Windows usa Segoe UI e Android usa a fonte sans-serif nativa. Ícones de navegação
são traços vetoriais desenhados localmente, com uma linguagem comum nas duas
plataformas. Não dependem de emoji, fontes de ícones ou requisições externas.

## O que mudou

- Windows: barra lateral com Visão geral, Processos, Energia, Agendamentos e
  Conexão; estado do PC no rodapé; histórico acessível pela Visão geral.
- Android: cabeçalho AURA, estado/conexão do PC, cartões CPU/RAM, páginas Início,
  Processos, Energia e Ajustes na navegação inferior; agenda em Energia e histórico
  acessível em Início e Ajustes. O conteúdo usa medidas independentes de densidade.
- Processos: pesquisa por nome/PID, ícones reais, separadores, seleção verde-água,
  dados do alvo selecionado e ação de encerramento em vermelho discreto. Android
  usa uma lista nativa rolável; Windows aceita mouse e seleção por setas.
- Estados de conexão, carregamento, falha, busca sem resultados e ausência de
  processos elegíveis. Confirmação antes de encerrar o alvo ou solicitar energia.
- As telas de energia, agenda, pareamento e histórico seguem a mesma hierarquia.
  Páginas longas podem rolar. Android ajusta o conteúdo ao teclado e às barras do
  sistema nas versões atuais, com compatibilidade de insets para API 26–29.
- Cartões mostram CPU, RAM usada/total e porcentagem reais. A linha de CPU só é
  desenhada após duas consultas reais; nenhum histórico ou dado da imagem é inventado.

## Ícones reais e privacidade

1. A listagem existente continua restringindo os processos elegíveis. Para cada
   alvo, o agente confere novamente PID e horário de criação e resolve internamente
   o executável. Um PID reutilizado não herda a identidade do processo anterior.
2. Em aplicativos MSIX, procura a identidade no `AppxManifest.xml` do próprio
   executável e carrega o ativo PNG indicado, incluindo variantes de tamanho.
   A resolução fica confinada à pasta do pacote, com limites de arquivo e imagem.
3. Para executáveis tradicionais, extrai o recurso de ícone com `ExtractIconExW`
   e o desenha em bitmap de 32 pixels. A transparência é reconstruída por duas
   passagens, e HICON, bitmap e contexto gráfico são liberados em `finally`.
4. O agente retorna apenas um identificador SHA-256 opaco com sal por execução.
   O novo endpoint autenticado `GET /api/process-icons/{icon_id}` aceita somente
   identificadores já registrados; não recebe caminho, URL, nome de arquivo ou PID.
5. A resposta JSON contém `state` (`ready`, `pending` ou `unavailable`) e `png`
   (base64 PNG ou null). Usa o mesmo HTTPS, token e certificado do restante da API,
   com `Cache-Control: no-store`. Nenhum caminho ou erro interno é transportado.
6. O cache em memória do agente tem até 256 entradas e validade de cinco minutos,
   incluindo falhas, com no máximo duas extrações simultâneas e fila limitada pelo
   próprio cache. A leitura de um ícone pendente espera no máximo 200 ms por pedido.
7. Windows e Android consultam ícones em executores separados das ações e da UI.
   Resultados de uma lista antiga são descartados. O Windows agrupa redesenhos;
   o Android limita o cache a 2 MiB e limpa tudo ao trocar/esquecer o PC. Também
   limita o tamanho da resposta e confere as dimensões antes de decodificar o PNG.

Falhas de permissão, encerramento do processo, executáveis sem recurso ou ativos
inacessíveis usam um monograma discreto. Não há imagens de marca baixadas da web
nem substituição por logotipos supostos a partir do nome. A disponibilidade do
ícone depende da identidade que o Windows permite ler; processos hospedados por
outro executável podem expor apenas a identidade desse host.

## Recursos preservados

Agente HTTPS separado da janela, pareamento privado, certificado fixado no
Android, configuração criptografada no Keystore, Wake-on-LAN pelo celular,
simulação/modo real, desligar/reiniciar, agenda persistente/cancelamento,
idempotência, proteções de processos e histórico com rotação. Não foram
implementados voz, abertura de programas/sites ou outros módulos pendentes.

## Validação desta entrega

- Compilação sintática dos módulos Python.
- `tools/check_native.py`: autenticação, validação, UUID/idempotência, agenda
  persistente, prazo, cancelamento, simulação, pareamento e restrição do modo real.
  Usa dados temporários e substitui os comandos de energia; nenhuma ação real.
- `tools/check_icons.py`: PNG/transparência, extração PE real do próprio executável
  Python sem abrir UI, estabilidade dos recursos GDI em 20 extrações, ativos MSIX
  temporários e bloqueio de traversal, identidade/PID reutilizado, deduplicação,
  expiração, falhas, estado pendente, limite de cache e autenticação do endpoint.
- Kotlin 2.1.10 compilado contra a biblioteca oficial Android API 35, alvo JVM 17,
  em classes temporárias. Não gera APK. XMLs de manifesto/tema também verificados.

Não foram abertos aplicativos, criadas janelas ocultas para teste, controlados
mouse/teclado, capturadas telas ou repetidos testes físicos/LAN já confirmados
pelo usuário. Na entrega inicial, não foram gerados instalador, APK, ZIP, release ou push.
Posteriormente, o usuário solicitou APK e .exe para testes; o build completo e as
checagens desses arquivos estão em [TESTES-0.4.1.md](../../TESTES-0.4.1.md).

**Limite da validação:** sem execução visual permitida, não há captura real nem
comparação pixel a pixel da implementação. Compilação Kotlin valida os tipos e
as APIs usadas, mas não substitui o build Gradle completo, lint Android ou uma
inspeção visual em aparelho. Diferenças de renderização nativa, DPI e escala de
fonte podem afetar medidas; a imagem aprovada continua sendo a referência.

O protótipo web anterior é mantido como código legado, fora da interface nativa
reformulada. A política de processos protegidos foi preservada: o Explorador,
usado como dado ilustrativo na referência, não vira um alvo encerrável nesta versão.
