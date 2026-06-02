# Protocolo de Recuperação Após Corrupção (Post-Session Audit)

**Date:** 2026-05-11
**Context:** Utilizador reportou que sessão anterior com outro modelo "fez asneiras". Pedido: "Reverte tudo o que foi feito de errado."

## Lição Principal

> **Quando não há Git nem backups, NÃO é possível "reverter magicamente".**
> O agente deve ser honesto sobre esta limitação e propor auditoria manual + correção ou recriação.

## Protocolo de 4 Passos

### Passo 1 — Verificar se existe Git
```bash
cd /path/to/project && git status --short
cd /path/to/project && git log --oneline -5
```
- Se SIM → `git diff`, `git log`, identificar commits da sessão problemática, `git revert` ou `git reset --hard`
- Se NÃO → prosseguir para Passo 2

### Passo 2 — Inventário Completo do Estado Atual
```bash
# Listar todos os ficheiros relevantes (excluir venvs, caches)
find /path/to/project -maxdepth 3 -type f \
  \( -name "*.py" -o -name "*.html" -o -name "*.json" -o -name "*.md" \) \
  ! -path "*/venv/*" ! -path "*/__pycache__/*" | sort

# Verificar pastas vazias
find /path/to/project -maxdepth 2 -type d -empty

# Verificar diferenças vs expectativa do utilizador
```

### Passo 3 — Identificar Estragos (não assumir)
**NÃO assumir** quais ficheiros estão corrompidos. Perguntar ao utilizador:
- "Qual é o estado de referência?"
- "O ficheiro X original ainda existe nalgum sítio?"
- "Preferes que eu corrija os caminhos/erros óbvios, ou que apague tudo e voltes a zero?"

**Perguntas-chave quando não há Git:**
1. O ficheiro de workflow original onde estava?
2. O script original (o teu, antes de editarmos) — ainda o tens?
3. Preferes que eu **apague tudo** o que foi criado e volte a zero, ou que eu corrija apenas os erros óbvios?

### Passo 4 — Executar o que o utilizador decidir
- Se disser "apaga tudo" → `rm -rf` dos ficheiros criados na sessão problemática
- Se disser "corrige" → corrigir caminhos, erros de sintaxe, paths quebrados um a um
- Se disser "nada por agora" → parar. Não fazer nada além do inventário.

## Anti-Padrões a Evitar

| Anti-padrão | Porquê evitar |
|-------------|---------------|
| "Vou reverter tudo" sem verificar Git | Impossível sem controlo de versões; promessa vazia |
| Assumir quais ficheiros estão errados | O utilizador pode ter backups locais que o agente não vê |
| Corrigir automaticamente sem perguntar | Pode destrair o trabalho manual do utilizador entre sessões |
| Listar erros e esperar que o utilizador decida sozinho | O utilizador pediu ação; propor opções claras é melhor que relatório passivo |

## Sinais de Corrupção por Outro Modelo

- Caminhos hardcoded para pastas de outro utilizador (`/mnt/c/Users/Fil_B/Downloads/`)
- Parsing de `widgets_values` por índice fixo (quebra se workflow mudar)
- Erros de sintaxe Python que "parecem" causados por patches mal aplicados
- Ficheiros criados em localizações inesperadas
- Pastas que deveriam ter conteúdo mas estão vazias (`05_Scripts/` vazia)

## Regra Transversal

**Quando o utilizador diz "outro modelo fez asneiras", a resposta correcta é:**
1. "Não tenho Git nem backups — não posso reverter automaticamente."
2. "Vou fazer um inventário do estado atual."
3. "Tens o estado original nalgum sítio? Preferes que eu corrija ou que apague?"
4. Esperar resposta. Não agir sem confirmação.
