# ai-log — Registro de uso de I.A.

Esta pasta documenta **como a I.A. foi usada** ao longo do desafio, conforme exigido pela avaliação
(“rastro do uso de I.A.”).

## O que é armazenado aqui

- Exportação **integral** da sessão do OpenCode, em texto (`.json`).
- Sem prints/capturas de tela (não são aceitos pela avaliação).
- Requisito do desafio: **exportar a sessão inteira**, não apenas trechos.

## Como a sessão foi exportada (importante)

**A exportação foi feita SEM `--sanitize`.**

> Aviso: o `--sanitize` do `opencode export` **remove o conteúdo textual** (substitui mensagens por
> `[redacted:text:...]`) e, portanto, **não atende ao requisito de entregar a conversa em texto**. Ele pode
> ser útil apenas para uma inspeção rápida, **nunca como arquivo de entrega**.

Procedimento adotado:

1. **Exportar para fora do repositório**, com stdout e stderr separados:
   ```
   cmd /c "opencode export <SESSION_ID> 1> %TEMP%\opencode-session-full.json 2> %TEMP%\opencode-export-full.log"
   ```
   (sem `--sanitize` e sem `2>&1`, para não misturar a mensagem de status ao JSON).
2. **Validar o JSON** (parse direto, UTF-8 estrito, sem U+FFFD, presença de prompts longos).
3. **Auditoria local de credenciais** sobre o JSON exportado apenas (sem ler arquivos externos):
   detectar valores `sk-…`, `Bearer …`, chaves privadas e campos `apiKey`/`token`/`password`/`secret`/
   `authorization` que **acompanhem um valor** (não mero nome em instruções).
4. **Redação mínima**: somente valores secretos **reais** encontrados foram substituídos por
   `[REDACTED_CREDENTIAL]`. Todo o restante foi **preservado integralmente**:
   prompts, respostas, comandos, erros, resultados de ferramentas, raciocínio registrado e ordem das
   mensagens.
5. **Nenhuma conversa foi resumida ou reconstruída**; erros e tentativas foram preservados.

### O que foi redigido nesta exportação

- 3 ocorrências do **mesmo valor `sk-…`** (chave de API exibida no conteúdo de um arquivo de configuração
  lido por ferramenta) foram substituídas por `[REDACTED_CREDENTIAL]`. O restante está intacto.

### Nota sobre caracteres U+FFFD

- Saídas de ferramentas continham caracteres de substituição `U+FFFD` (bytes inválidos do terminal). Eles
  foram normalizados para `?` para manter o arquivo em UTF-8 estrito legível. Isso **não** altera prompts
  nem respostas.

## Rastreabilidade

- `session.json` — exportação integral da sessão (sanitização mínima acima descrita).
- Verificações aplicadas: JSON puro; parse direto; UTF-8 estrito; sem U+FFFD; mensagens de usuário e de
  assistente legíveis; prompts, respostas, ferramentas e erros preservados.

### Sobre termos que aparecem na conversa

Os termos `opencode.json`, `[Pasted ~N lines]` e `[redacted:text:...]` **aparecem no arquivo**, mas apenas
como **assuntos discutidos na própria conversa** (por exemplo, quando foi explicado que o `--sanitize`
substitui mensagens por `[redacted:text:...]`, ou quando se discutiu o marcador `[Pasted ~N lines]`). Eles
**não** são:

- exposição de credenciais;
- placeholders que substituam mensagens reais.

A validação confirmou que **nenhuma string real** começa com `[redacted:text:` ou `[Pasted` (não há
substituição de conteúdo), e que **zero credenciais reais iniciadas por `sk-`** permanecem. As únicas
marcações de redação são as mínimas `[REDACTED_CREDENTIAL]` documentadas acima.

## Checklist de qualidade da exportação

- [x] Arquivo em texto (`.json`).
- [ ] Revisão visual humana final (conferir completude e ausência de segredos).
- [x] Prompts colados aparecem por extenso (não “pasted N lines”).
- [x] Credenciais reais minimamente redigidas (`[REDACTED_CREDENTIAL]`).
- [x] Leitura legível.

## Arquivos

- `README.md` — este documento.
- `session.json` — exportação integral da sessão de análise do desafio.