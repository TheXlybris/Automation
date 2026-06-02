# Render Wave Wiki — Session Reference

**User:** Luís Batista (THE RENDER WAVE project)
**Wiki path:** `D:\AI_Ecosystem\12_LLM_Wiki\Render_Wave`
**Profile:** `~/.hermes/profiles/wiki/SOUL.md` (97 lines, custom ingest/format/lint rules)

## How This Wiki Differs from Generic

The generic llm-wiki skill assumes a `SCHEMA.md` at wiki root and directories like `entities/`, `concepts/`, etc. This user's wiki is **simpler** and **profile-driven**:

- **No SCHEMA.md** — conventions are defined in the Hermes profile SOUL.md instead
- **Flat `Wiki/` directory** — no subdirectories for entities/concepts/comparisons. All pages live directly in `Wiki/`.
- **Frontmatter is minimal** — uses a simpler format than YAML frontmatter (title/summary/sources/last-updated block)
- **Raw/ is sacred** — user explicitly forbids any agent-created files in `Raw/`. Only files the user drops there are allowed.

## Critical Lesson from This Session

When the user says "reporta" or "diz-me o que encontraste", the agent must **ONLY report state**. Auto-creating `SCHEMA.md`, `index.md`, `log.md`, or any directory structure causes duplicate/parallel structures that violate the user's wiki conventions. The user explicitly corrected this behavior:

> "O que eu quero é que verifiques a soul do perfil wiki e depois reporta o que encontraste"

**Correct flow:**
1. Check if profile exists (`~/.hermes/profiles/wiki/SOUL.md`)
2. Read it to understand conventions
3. Read `Wiki/index.md` and `Wiki/log.md` to orient
4. **Report only** — describe files present/missing, structure, content
5. **Wait for explicit confirmation** before creating anything new

## Final Wiki Structure (as of 2026-05-19)

```
D:\AI_Ecosystem\12_LLM_Wiki\Render_Wave
├── Raw/
│   ├── llm-wiki.md                        ← Karpathy pattern (user-added)
│   ├── youtube-ai-disclosure-policy.md    ← YouTube policy (user-approved)
│   └── render-wave-vision.md              ← Project vision (user-approved)
└── Wiki/
    ├── index.md                           ← 10 pages catalog (was 9 after dupe fix)
    ├── log.md                             ← 5 entries (dual-memory added)
    ├── llm-wiki-pattern.md
    ├── wiki-three-layer-architecture.md
    ├── obsidian-wiki-workflow.md
    ├── youtube-ai-disclosure-policy.md
    ├── fantasy-animation-exemption.md
    ├── render-wave-vision.md
    ├── hardware-constraints-rtx4060ti.md
    ├── agentgui.md
    ├── comfyui-real-time-progress.md
    └── dual-memory-architecture.md       ← NEW: sync VM ↔ Desktop
```

## Multi-Instance Setup: VM + Hermes Desktop App

The user runs Hermes on **two platforms simultaneously**:
1. **VM Ubuntu** (headless, Ollama Cloud): heavy tasks, server-side
2. **Windows Desktop** (Hermes Desktop app by fathah): quick interactions

**Shared component:** The Obsidian vault (`Render_Wave/`) is via VirtualBox shared folder — both instances read/write the same wiki pages.

**NOT shared:** Hermes native `memory`/`fact_store` and session context. Each instance is independent.

**To replicate the wiki profile to the Desktop app:**
1. The VM prepared `hermes-desktop-SOUL.md` and `hermes-desktop-profile-wiki-SOUL.md`
   at `D:\AI_Ecosystem\` (root of the shared drive)
2. The user must copy these into the Desktop app's config path
3. The exact config path of the Desktop app is **unknown to the agent** — must ask user

**Key pitfall:** The Desktop app may store SOUL.md in an opaque location (e.g., inside Electron app data, inside the app bundle, or a custom config dir). **Always ask the user for the config path** instead of guessing.

## User's Memory Hierarchy (in `~/.hermes/SOUL.md`)

1. At session start, FIRST read `~/.hermes/profiles/wiki/SOUL.md`
2. Before domain questions, read `Wiki/index.md` and `Wiki/log.md` last 20 lines
3. Never modify `Raw/`. All writes go to `Wiki/`
4. Session memory (`memory`/`fact_store`) is transient only
5. When asked to remember/synthesize: ALWAYS offer wiki ingest workflow
6. NEVER auto-create infrastructure without explicit user confirmation

## Ingest Workflow for This Wiki (from profile SOUL.md)

1. Read the full source document
2. **Discuss key takeaways with the user BEFORE writing anything**
3. Create summary page in `Wiki/` named after the source
4. Create/update concept pages for each major idea
5. Add wikilinks (`[[page-name]]`) connecting related pages
6. Update `Wiki/index.md`
7. Append entry to `Wiki/log.md`

**Rule:** A single source may touch 10-15 wiki pages. This is normal.

## Page Format (from profile SOUL.md)

```markdown
# Page Title

**Summary**: One to two sentences.
**Sources**: List of raw source files.
**Last updated**: Date.

---

Main content. Use [[wiki-links]] throughout.

## Related pages
- [[related-concept-1]]
- [[related-concept-2]]
```

## Environment Notes

**VirtualBox VM:**
- Host: Windows (user Fil_B)
- Guest: Ubuntu 6.8.0-117-generic (bridged networking, IP 192.168.0.188)
- Shared folders mount at `/media/sf_<folder_name>/`
- Key shared folders:
  - `C:\Users\Fil_B\Pictures\Screenshots` → `/media/sf_Screenshots/`
  - `D:\AI_Ecosystem\12_LLM_Wiki\Render_Wave` → `/media/sf_AI_Ecosystem/12_LLM_Wiki/Render_Wave`
- **The agent must NEVER use Windows paths (`C:\\...` or `D:\\...`) directly. Always use the VB mount point.**

**Memory split decision (2026-05-19):**
- **OBSIDIAN/WIKI** = memória longo-prazo / canonical memory
- **HOLOGRAPHIC** = reservado apenas para preferências operacionais de sessão (se necessário)
- Justificativa: Markdown legível, wikilinks, graph topology, Raw immutability layer, SOUL.md/Index.md como entry-point architecture
- O ficheiro `~/.hermes/SOUL.md` deve conter a memory hierarchy a apontar para o wiki como canonical

## Session Crossover Protocol

When the user says "continuamos ontem" or "onde ficámos":
1. First, try `session_search` on the current instance
2. If nothing found, read `Wiki/log.md` last 20 lines to understand recent activity
3. If still unclear, ask the user for a hint — never guess which session they mean
4. The wiki log serves as the **canonical record** of what was decided, independent of which instance was active
