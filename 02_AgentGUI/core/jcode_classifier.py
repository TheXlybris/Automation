"""
jcode task classifier — decide whether a developer task should be delegated to jcode.

Rules (in order):
1. Explicit opt-out: task contains 'no_jcode' or 'sem jcode' → force Hermes path.
2. Explicit opt-in: task contains 'jcode:' or 'usar jcode' → force jcode path.
3. Heuristic: task matches coding keywords AND has enough specificity → jcode path.
4. Otherwise → Hermes path.

The classifier returns a dict with:
  use_jcode: bool
  reason: str
  confidence: float (0.0-1.0)
  matched_keywords: list[str]
"""

import re
from typing import Optional

# Keywords that strongly suggest a coding/automation task suitable for jcode.
_JCODE_KEYWORDS = [
    "create", "criar", "add", "adicionar", "implement", "implementar",
    "fix", "corrigir", "debug", "refactor", "refatorar", "write", "escrever",
    "script", "function", "class", "module", "api", "endpoint", "route",
    "component", "jsx", "react", "flask", "server", "runner", "profile",
    "config", "yaml", "json", "toml", "patch", "edit file", "modificar ficheiro",
    "git", "commit", "merge", "pull request", "pr", "test", "teste", "unit test",
    "pytest", "docker", "dockerfile", "compose", "deploy", "build", "install",
    "package", "pip", "npm", "cargo", "requirements", "dependenc",
    "lint", "format", "prettier", "black", "ruff", "mypy",
    "log", "error", "traceback", "exception", "bug", "issue",
    "comfyui", "workflow", "node", "python", "javascript", "typescript",
    "shell", "bash", "sql", "query", "database", "migration",
]

# Keywords that suggest the task is NOT suitable for jcode (planning, research, meta).
_HERMES_KEYWORDS = [
    "research", "pesquisar", "investigar", "study", "estudar",
    "summarize", "resumir", "explain", "explicar", "compare", "comparar",
    "analyze", "analisar", "document", "documentar", "wiki", "obsidian",
    "plan", "plano", "roadmap", "architecture", "arquitetura", "design doc",
    "decision", "decisão", "review code only", "review only", "apenas revisa",
    "brainstorm", "ideias", "discuss", "discutir", "ask", "perguntar",
]


def _normalize(text: Optional[str]) -> str:
    if not text:
        return ""
    return text.lower()


def classify_task(task: Optional[str]) -> dict:
    """Classify a task and return whether jcode should handle it."""
    text = _normalize(task)
    if not text:
        return {"use_jcode": False, "reason": "empty task", "confidence": 0.0, "matched_keywords": []}

    # Explicit opt-out
    if re.search(r"\b(no_jcode|sem jcode|sem o jcode|disable jcode)\b", text):
        return {"use_jcode": False, "reason": "explicit opt-out", "confidence": 1.0, "matched_keywords": []}

    # Explicit opt-in
    if re.search(r"\b(jcode:|usar jcode|use jcode|with jcode|via jcode)\b", text):
        return {"use_jcode": True, "reason": "explicit opt-in", "confidence": 1.0, "matched_keywords": []}

    matched = [kw for kw in _JCODE_KEYWORDS if kw in text]
    hermes_matched = [kw for kw in _HERMES_KEYWORDS if kw in text]

    # Specificity signals: file paths, file names, code patterns
    specificity = 0.0
    if re.search(r"\.[a-z]{2,5}\b", text):  # file extensions
        specificity += 0.2
    if re.search(r"`[^`]+`", text):  # inline code
        specificity += 0.15
    if len(text.split()) > 8:
        specificity += 0.1
    if re.search(r"\b(server\.py|app\.py|main\.py|run_.*\.py|.*\.jsx|.*\.js|.*\.ts|.*\.json|.*\.yaml|.*\.toml)\b", text):
        specificity += 0.2

    if matched and not hermes_matched:
        confidence = min(0.95, 0.5 + len(matched) * 0.08 + specificity)
        return {"use_jcode": True, "reason": "coding keywords matched", "confidence": round(confidence, 2), "matched_keywords": matched}

    if matched and hermes_matched:
        # Ambiguous: prefer Hermes unless specificity is high
        if specificity >= 0.4:
            confidence = min(0.85, 0.45 + len(matched) * 0.06 + specificity)
            return {"use_jcode": True, "reason": "coding keywords + high specificity", "confidence": round(confidence, 2), "matched_keywords": matched}
        confidence = min(0.7, 0.35 + len(hermes_matched) * 0.08)
        return {"use_jcode": False, "reason": "ambiguous, research keywords present", "confidence": round(confidence, 2), "matched_keywords": hermes_matched}

    return {"use_jcode": False, "reason": "no coding keywords", "confidence": 0.0, "matched_keywords": []}
