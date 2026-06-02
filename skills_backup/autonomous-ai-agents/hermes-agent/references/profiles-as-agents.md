# Hermes Profiles — Specialized Agents

Sessão: 2026-05-09
Contexto: THE RENDER WAVE — correção de conceito: `hermes profile` cria agentes especializados, não `hermes dashboard`.

## Correção de Conceito

**Erro anterior:** O agente (Hermes CLI) disse que `hermes dashboard` é a ferramenta para criar agentes especializados. **Isto está errado.**

**Verdade:** `hermes dashboard` é uma UI web para gerir config global, ver sessões, editar ficheiros (incluindo SOUL.md), e ver logs. **Não cria perfis nem agentes.**

A ferramenta correcta para criar agentes especializados é **`hermes profile`** (CLI). Cada profile é uma instância independente do Hermes com config, sessões, skills, e memória isoladas.

## Como Criar um Agente Especializado

```bash
# 1. Criar perfil (clona config, .env, SOUL.md do perfil ativo)
hermes profile create developer --clone

# 2. Editar SOUL.md para definir personalidade e regras
code ~/.hermes/profiles/developer/SOUL.md

# 3. Usar o perfil
hermes profile use developer        # sticky (default para futuras sessões)
# ou
developer chat                      # alias criado automaticamente
# ou
hermes --profile developer          # one-shot
```

## Estrutura de um Profile

```
~/.hermes/profiles/<nome>/
├── SOUL.md          # Personalidade, regras, tom de comunicação
├── config.yaml      # Config específica (modelo, provider, toolsets)
├── .env             # API keys e secrets
├── sessions/        # Histórico de conversações isolado
└── skills/          # Skills instaladas (pode divergir do default)
```

## Perfis Criados para THE RENDER WAVE

| Perfil | Comando | SOUL.md | Função |
|--------|---------|---------|--------|
| `developer` | `developer chat` | Código/debugging/optimização | Técnico, conciso, verifica antes de afirmar |
| `researcher` | `researcher chat` | Pesquisa/documentação | Sourcing, síntese, organização |

## O que o SOUL.md Controla

O ficheiro `SOUL.md` define:
- **Personalidade e tom** — como o agente fala (formal, casual, técnico)
- **Regras de workflow** — ex: developer "nunca adivinha, sempre verifica"
- **Restrições** — ex: researcher "não escreve código, não executa comandos"
- **Estilo de output** — tabelas, code blocks, estrutura preferida
- **Idioma** — português (PT-PT), inglês, etc.

**Limitação:** Todos os perfis partilham o mesmo modelo e toolset por defeito. Para restringir ferramentas por perfil, editar `~/.hermes/profiles/<nome>/.env` e `config.yaml`.

## Diferença: Profiles vs `delegate_task` vs Spawning

| | `hermes profile` | `delegate_task` | Spawn `hermes` process |
|---|----------------|-------------------|----------------------|
| Persistência | Permanente (SOUL.md, skills, memória) | Temporária (só a sessão) | Processo independente |
| Isolamento | Config + memória isolados | Contexto separado, mesma instância | Processo OS separado |
| Uso | Agente especializado de longo prazo | Subtarefa paralela rápida | Missão autónoma longa |
| Custo | Um setup, uso contínuo | Leve, dispose automático | Overhead de processo |
| Exemplo | developer, researcher, designer | "Analisa este log enquanto eu continuo" | "Corre durante a noite a processar dados" |

## Recomendação para THE RENDER WAVE

Para o ecossistema de automação de vídeos, recomenda-se:

1. **developer** — cria scripts, workflows, corrige bugs, optimiza código
2. **researcher** — pesquisa novos modelos de vídeo, compara abordagens, documenta resultados
3. **(opcional) creative** — gera prompts, ideias de cenas, conceitos artísticos
4. **(opcional) ops** — monitoriza pipelines, verifica outputs, gere cron jobs

O utilizador (Luís) lança o perfil relevante para cada tarefa. Cada perfil carrega só as skills necessárias, mantendo o contexto limpo.

## Nota sobre `hermes dashboard`

O dashboard (`hermes dashboard --port 9119`) é útil para:
- Ver histórico de sessões
- Editar ficheiros (SOUL.md, config.yaml) via browser
- Ver logs
- Gerir API keys

**Não é para:** criar perfis, definir agentes, ou gerir skills. Essas operações fazem-se via CLI.

## Referências

- `hermes profile --help`
- `~/.hermes/profiles/<nome>/SOUL.md`
- https://hermes-agent.nousresearch.com/docs/user-guide/profiles
