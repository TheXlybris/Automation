# Dual-Memory Setup: Hermes Native + Obsidian Wiki

Documenta o padrão dual-memory implementado para THE RENDER WAVE.

## Contexto

O utilizador (Luís Batista) quer melhorar a memória do Hermes para não esquecer
coisas importantes do projeto. A solução é dividir a memória em dois níveis:

| Nível | Sistema | Conteúdo | Quem edita | Acesso do agente |
|-------|---------|----------|------------|------------------|
| Curto prazo | Hermes nativo (`memory`, `fact_store`, `session_search`) | Factos de sessão, preferências, correções recentes | Agente (automático) | Injetado em cada turn |
| Longo prazo | Obsidian wiki (`D:\AI_Ecosystem\12_LLM_Wiki\`) | Decisões arquiteturais, workflows validados, conhecimento estruturado | Utilizador (Obsidian) + Agente | Lido no início de cada sessão |

## Porquê separar

- **Memória nativa** compacta-se bem mas perde detalhe ao longo do tempo (factos
  antigos são sobrescritos, resumos perdem nuance)
- **Wiki** preserva fidelidade total, cross-references, e histórico de decisões
- O utilizador pode curar/editar o wiki diretamente no Obsidian
- O agente vê as edições do utilizador no início da próxima sessão

## Setup implementado (2026-05-14)

### 1. Vault Obsidian

Localização: `D:\AI_Ecosystem\12_LLM_Wiki\`

Conteúdo inicial:
- `README.md` — descrição da arquitetura dual-memory
- `hermes.md` — instruções de workflow do LLM Wiki (ingest, page format, lint rules)
- `Render_Wave/hermes.md` — cópia das instruções para o projeto específico

### 2. Ficheiro SOUL.md do Hermes

Localização WSL: `/home/xlybris/.hermes/SOUL.md`

Conteúdo: wiki workflow instructions (baseado no Karpathy LLM Wiki pattern)
- Ingest workflow (7 passos)
- Page format (Summary, Sources, Last updated, Related pages)
- Citation rules
- Question answering protocol
- Lint rules
- Rules (nunca modificar raw/, sempre atualizar index.md e log.md)

### 3. Workflow de edição

```
WSL: ~/.hermes/SOUL.md          ← agente lê em cada mensagem
      |
      |  cp (agente cria cópia)
      v
Windows: D:\AI_Ecosystem\12_LLM_Wiki\hermes.md   ← utilizador edita no Obsidian
      |
      |  utilizador diz "ficheiro editado, coloca no local correto"
      v
WSL: ~/.hermes/SOUL.md          ← agente substitui pelo editado
```

**Regra:** O ficheiro em Windows é a **cópia editável pelo utilizador**. O
ficheiro em `~/.hermes/SOUL.md` é o **original que o agente lê**. Sempre sincronizar
de Windows → WSL após o utilizador confirmar que as edições estão completas.

### 4. Orientação no início da sessão

Quando o utilizador tem um wiki existente, o agente deve:
1. Ler `SCHEMA.md` do wiki — entender domínio, convenções, taxonomia de tags
2. Ler `index.md` — saber que páginas existem e os seus resumos
3. Ler `log.md` (últimas 20-30 entradas) — entender atividade recente

Só depois de orientado deve o agente fazer ingest, query, ou lint.

## Convenções do vault

- Ficheiros `.md` com frontmatter YAML (title, date, tags)
- Links internos com sintaxe Obsidian `[[ficheiro]]` ou `[texto](ficheiro.md)`
- Datas em ISO 8601: `2026-05-14`
- Tags no frontmatter: `tags: [comfyui, ltx-video, architecture]`

## Regra de Ouro

> Nunca duplicar factos entre memória curta (Hermes nativa) e memória longa (Obsidian).
> Memória curta = sessões recentes, preferências, estado temporário.
> Memória longa = conhecimento estruturado, decisões irreversíveis, workflows validados.

## Erros comuns a evitar

1. **Criar páginas sem cross-references** — páginas isoladas são invisíveis. Cada
   página deve linkar para pelo menos 2 outras.
2. **Esquecer de atualizar index.md e log.md** — são a espinha dorsal de navegação.
   Sem eles, o wiki degrada-se.
3. **Tags fora da taxonomia** — tags livres degradam-se em ruído. Adicionar novas
   tags ao SCHEMA.md primeiro, só depois usar.
4. **Páginas demasiado grandes** — uma página deve ser legível em 30 segundos.
   Dividir páginas com >200 linhas.

## Ferramentas relacionadas

- `llm-wiki` skill — skill principal do Hermes para wiki (Karpathy pattern)
- `obsidian` skill — integração com Obsidian vault (ler/editar notas)
- `web_extract` — extrair artigos web para raw/sources/

## Referências

- Karpathy LLM Wiki gist: https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f
- Video setup guide: https://www.youtube.com/watch?v=iXd0t60YmMw
- Hermes Agent docs: https://hermes-agent.nousresearch.com/docs
