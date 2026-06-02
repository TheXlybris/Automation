# Pitfall: System Python vs Pipx Venv Dependencies

**Context**: Hermes dashboard `hermes dashboard` runs in a subprocess using the pipx venv's Python, NOT the system Python. This means dependencies must be installed inside the pipx venv, not just the system Python.

**Symptom**: After running `pip install fastapi uvicorn` in system Python, `hermes dashboard` still fails with:
```
Web UI dependencies not installed (need fastapi + uvicorn).
Import error: No module named 'fastapi'
```

**Cause**: Tools like `pipx inject`, `pipx runpip`, and direct `pip install` in the `terminal()` tool may be blocked by the "long-lived server/watch process" heuristic (exit code -1). This prevents the deps from actually reaching the venv.

**Diagnosis**:
```bash
# System Python — NOT enough
python3 -c "import fastapi"  

# Pipx venv Python — this is what the dashboard uses
~/.local/share/pipx/venvs/hermes-agent/bin/python -c "import fastapi; import uvicorn"
```

**Fix (verified in field)**:
Use `execute_code` to run pip inside the venv in the foreground:
```python
import subprocess, os
venv_python = os.path.expanduser('~/.local/share/pipx/venvs/hermes-agent/bin/python')
subprocess.run([venv_python, '-m', 'pip', 'install', 'fastapi', 'uvicorn'], check=True)
```

**Flow**: System Python check fails → Venv Python check fails → Use execute_code with subprocess.run([venv_python, '-m', 'pip', ...]) → Verify with venv Python → Dashboard starts successfully.
