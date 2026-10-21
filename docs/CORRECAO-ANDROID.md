# Correção da inicialização Android — AURA 0.4.1, build 402

## Falha reproduzida

Os testes de ciclo de vida Android reproduziram uma `NullPointerException` em
`MainActivity.configureSystemBars()` nas APIs 30, 33 e 35 (Android 11, 13 e 15).
A tela inicial ainda não havia sido instalada quando o app acessava
`window.insetsController`. O getter de `PhoneWindow` dereferencia internamente
seu `DecorView`, que ainda era null. O operador `?.` aplicado ao resultado do
getter não evita essa falha dentro do próprio getter.

Sem o log do celular não se pode afirmar que essa seja a única causa possível
nesse aparelho, mas a falha reproduzida interrompia a inicialização exatamente
antes da abertura da tela. A correção instala primeiro o conteúdo da janela com
`setContentView` e só então configura as barras do sistema.

## Diagnóstico visível

Falhas capturáveis durante a construção da interface agora exibem uma tela
simples de recuperação com código, tipos de exceção, API Android, pontos do
código AURA e instruções. É possível copiar o diagnóstico, tentar novamente ou
fechar. Os códigos incluem `AURA-START-NULL`, `AURA-START-STATE`,
`AURA-START-RESOURCES`, `AURA-START-CLASS` e `AURA-START-001`.

Mensagens brutas de exceção, tokens, endereços, caminhos e conteúdo do perfil não
são incluídos. O diagnóstico é limitado a 4000 caracteres e armazenado somente
na pasta privada do app. Nada é enviado automaticamente. O perfil salvo não é
apagado pela recuperação. O tratamento não promete recuperar erros fatais de
memória/processo nem falhas do Android anteriores à criação da Activity.

## Testes executados

Teste local em JVM com Robolectric 4.14.1, usando recursos Android compilados e
ciclo de vida real da Activity no ambiente de teste, sem emulador ou janela na
área de trabalho. Esse tipo de teste não é uma execução física no celular.

Antes da correção: 6 falhas em 8 verificações nas APIs 28, 30, 33 e 35.
Depois: **12 testes, zero falhas, zero erros**:

- Abertura a frio, medição/layout e primeiro desenho nas APIs 26, 28, 30, 33 e 35.
- Navegação por Início, Processos, Energia e Ajustes, seguida de recriação da
  Activity, nas mesmas cinco APIs.
- Diagnóstico sem mensagens sensíveis.
- Tela de recuperação com código e ação de copiar, preservando o perfil salvo.

Os testes ficam em `android/app/src/test/java/io/aura/personal/StartupTest.kt` e
também foram adicionados ao workflow de compilação. Para executar:

```text
gradle :app:testDebugUnitTest :app:assembleDebug :app:lintDebug
```

A versão Robolectric 4.17 foi tentada inicialmente e apresentou um erro interno
de shadow de Bluetooth na checagem de recuperação. O conjunto final usa 4.14.1,
compatível com as APIs e com o JDK 17 deste projeto. Dependências de teste não
fazem parte do APK.

## Novo APK

`AURA-Android-0.4.1-corrigido.apk`, versão 0.4.1, versionCode **402** (antes 401).
Mantém o identificador `io.aura.personal` e a mesma chave de assinatura debug do
APK anterior para permitir atualização sem remover a instalação e o perfil.
Assinatura, identidade, versão e integridade do pacote são conferidas no build.
O `.exe` corrigido do Windows permanece o mesmo.

Se o Android solicitar confirmação de atualização, use a opção de atualizar.
Não é necessário desinstalar a versão anterior para esta correção quando o APK
instalado for o fornecido nesta entrega. Se ainda ocorrer falha capturada, envie
o texto de **Copiar diagnóstico**. Não foram repetidos testes físicos de energia
ou LAN nem feita instalação em dispositivos do usuário.
