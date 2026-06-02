---
name: skill-backup
description: "Preserve custom skills against `hermes update` by backing them to a GitHub repo. Also covers safe storage locations and the `~/.hermes/profiles/` fallback."
version: 1.0.0
metadata:
  hermes:
    tags: [skills, backup, persistence, version-control, hermes-update]
    related_skills: [github-auth]
---

# Skill Backup & Preservation

## Why This Matters

`hermes update` syncs bundled skills from upstream into `~/.hermes/skills/`. In previous sessions, custom skills created together with the user were **lost during updates**, despite the documentation claiming that local edits are "respected". This skill codifies the safe workflow to prevent recurrence.

## Directories Managed by `hermes update`

| Directory | Touched? | Notes |
|-----------|----------|-------|
| `~/.hermes/skills/` | **YES** — synced with upstream | Never treat as permanent archive |
| `~/.hermes/profiles/<name>/skills/` | **NO** | Profile-scoped, safe from sync |
| `~/.hermes/plugins/` | **NO** | Python plugins, not Markdown skills |
| `~/.hermes/config.yaml` / `.env` | **NO** | Config preserved |
| Paths outside `~/.hermes/` | **NO** | External storage safest |

## Workflow: Immediate GitHub Backup After Skill Creation

### Step 1 — Save the skill locally (normal flow)
```bash
skill_manage(action='create', name='my-skill', category='devops', content='...')
```

### Step 2 — Copy to tracked repo (do this BEFORE `hermes update`)
```bash
SRC="~/.hermes/skills/devops/my-skill"
DST="~/Automation/skills_backup/devops/my-skill"
mkdir -p "$(dirname "$DST")"
cp -r "$SRC" "$DST"

cd ~/Automation
git add "$DST"
git commit -m "backup(skill): my-skill — <one-line description>"
git push origin main
```

### Step 3 — If `hermes update` deletes the skill
```bash
# Restore locally from git backup
SRC="~/Automation/skills_backup/devops/my-skill"
DST="~/.hermes/skills/devops/my-skill"
rm -rf "$DST"   # remove stale/dangling directory
cp -r "$SRC" "$DST"
```

### Step 4 — Long-term: automate with post-update hook
Add to `~/.hermes/hooks/` (if hook system is supported):
```bash
#!/bin/bash
# ~/.hermes/hooks/post-update
# Restore any missing skills from backup
for skill in ~/Automation/skills_backup/*/; do
  name=$(basename "$skill")
  dst="~/.hermes/skills/$(echo "$skill" | cut -d'/' -f5)/$name"
  if [ ! -d "$dst" ]; then
    cp -r "$skill" "$dst"
    echo "Restored: $name"
  fi
done
```

## Alternative: Use `~/.hermes/profiles/default/skills/`

Skills stored under a **profile** directory are outside the upstream sync scope.

```bash
# Create skill in the profile tree instead
mkdir -p ~/.hermes/profiles/default/skills/my-namespace
cat > ~/.hermes/profiles/default/skills/my-namespace/SKILL.md << 'EOF'
---
name: my-skill
---
...content here...
EOF
```

**Trade-offs:**
- Profile skills do NOT appear in `skills_list()` unless the active profile matches
- They must be loaded explicitly or the profile must be switched

## Best Practices Summary

1. **Every new custom skill → immediate git commit to `Automation/skills_backup/`**
2. **Never rely** on `~/.hermes/skills/` alone for anything valuable
3. **Keep a manifest** — a simple `skills_manifest.md` in the backup repo listing all custom skills and their creation date
4. **After `hermes update`** — diff `~/.hermes/skills/` against the backup to detect missing items

## Session Lesson

Losing skills is expensive. The user explicitly stated: *"foi apagado num update e isso deixou-me na merda"*. This skill codifies the countermeasure: external version-controlled backup, immediate, no exceptions.
