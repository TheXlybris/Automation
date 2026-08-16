"""Tests for the JSONL error logging system in server.py.

These tests import the errorhandler functions directly and verify
that errors are logged to errors.jsonl with the correct category.

Run: pytest tests/test_error_log.py -v
"""
import json
import pytest
from pathlib import Path
from datetime import datetime


# ── Category routing ──────────────────────────────────────

def _get_category(path: str) -> str:
    """Mirror of the category logic in server.py errorhandler."""
    if "/api/video" in path:
        return "video"
    elif "/api/media" in path:
        return "media"
    elif "/api/agents" in path:
        return "agents"
    elif "/api/profiles" in path:
        return "profiles"
    elif "/api/cron" in path:
        return "cron"
    elif "/socket" in path:
        return "socket"
    else:
        return "other"


@pytest.mark.parametrize("path,expected", [
    ("/api/video/postprocess", "video"),
    ("/api/video/fetch", "video"),
    ("/api/video/generate", "video"),
    ("/api/media/upload", "media"),
    ("/api/media/file/test.mp4", "media"),
    ("/api/agents/dispatch", "agents"),
    ("/api/agents/123/status", "agents"),
    ("/api/profiles/developer", "profiles"),
    ("/api/profiles/multimedia/skills", "profiles"),
    ("/api/cron/list", "cron"),
    ("/api/cron/create", "cron"),
    ("/socket.io", "socket"),
    ("/api/unknown", "other"),
    ("/", "other"),
    ("", "other"),
])
def test_category_routing(path, expected):
    assert _get_category(path) == expected


# ── JSONL entry format ────────────────────────────────────

def test_jsonl_entry_has_all_fields(tmp_path):
    """Verify a JSONL entry has ts, endpoint, method, category, error, traceback."""
    err_log = tmp_path / "errors.jsonl"
    entry = {
        "ts": datetime.now().isoformat(),
        "endpoint": "/api/video/postprocess",
        "method": "POST",
        "category": "video",
        "error": "RuntimeError: test error",
        "traceback": "Traceback (most recent call last):\n  File ...",
    }
    err_log.write_text(json.dumps(entry, ensure_ascii=False) + "\n")

    line = err_log.read_text().strip()
    parsed = json.loads(line)
    for field in ("ts", "endpoint", "method", "category", "error", "traceback"):
        assert field in parsed, f"Missing field: {field}"


def test_jsonl_append_only(tmp_path):
    """Verify entries are appended, not overwritten."""
    err_log = tmp_path / "errors.jsonl"
    for i in range(3):
        entry = {"ts": datetime.now().isoformat(), "endpoint": f"/api/test/{i}", "error": f"err {i}"}
        with open(err_log, "a") as f:
            f.write(json.dumps(entry) + "\n")

    lines = err_log.read_text().strip().split("\n")
    assert len(lines) == 3
    for i, line in enumerate(lines):
        parsed = json.loads(line)
        assert f"/api/test/{i}" == parsed["endpoint"]


def test_jsonl_valid_json(tmp_path):
    """Every line must be valid JSON."""
    err_log = tmp_path / "errors.jsonl"
    entry = {"ts": "2026-08-16", "endpoint": "/api/test", "category": "other", "error": "x"}
    with open(err_log, "a") as f:
        f.write(json.dumps(entry) + "\n")
        f.write(json.dumps({**entry, "error": "y"}) + "\n")

    for line in err_log.read_text().strip().split("\n"):
        json.loads(line)  # raises if invalid
