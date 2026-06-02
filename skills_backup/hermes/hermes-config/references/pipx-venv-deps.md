# Pitfall: System Python vs Pipx Venv Python Dependencies

**Applies to**: Hermes agents installed via pipx where `execute_code` reports installed packages but Hermes CLI tools report they are missing.

**Date**: 2026-05-25
**Context**: Hermes runs its own processes under `~/.local/share/pipx/venvs/hermes-agent/bin/python`. The session Python may have a different `sys.path` (including system site-packages), so `execute_code` success does NOT mean the Hermes venv has the package.

## Symptom
After confirming `fastapi` and `uvicorn` are installed via `execute_code`, `hermes dashboard` still fails with:
```
Web UI dependencies not installed (need fastapi + uvicorn).
Import error: No module named 'fastapi'
```

## Diagnosis
Always check the venv Python, never the system Python:
```bash
# System Python — may succeed but is irrelevant
python3 -c "import fastapi; print('ok')"

# Pipx venv Python — this is what Hermes actually uses
~/.local/share/pipx/venvs/hermes-agent/bin/python -c "import fastapi; import uvicorn; print('ok')"
```

## Root Cause
1. `execute_code` runs in the session's default Python (`/usr/bin/python3`), which may see packages in `/usr/local/lib/...` or `~/.local/lib/python*/site-packages`.
2. The Hermes venv Python (`~/.local/share/pipx/venvs/hermes-agent/bin/python`) does NOT inherit these paths unless explicitly set.

## Fix
Install packages directly into the venv using `execute_code` to run the venv's pip:
```python
import subprocess, os
venv_python = os.path.expanduser('~/.local/share/pipx/venvs/hermes-agent/bin/python')
subprocess.run(
    [venv_python, '-m', 'pip', 'install', 'fastapi', 'uvicorn'],
    check=True,
    timeout=120,
)
```

## Related
- `hermes-dashboard/references/pipx-venv-deps.md` — dashboard-specific application of this pitfall.
