#!/usr/bin/env python3
"""
Hermes Gateway Environment Diagnostic
"""
Quickly check if known web-search and API key environment variables
are actually present in running Hermes gateway AND TUI processes.

Usage:
    python scripts/check-gateway-env.py

Exit codes:
    0 — at least one relevant key is loaded in at least one process
    1 — no Hermes processes found OR no keys loaded in any process
"""
import glob
import os
import sys

# keys we care about for web search and core tools
KEY_NAMES = [
    "TAVILY_API_KEY",
    "FIRECRAWL_API_KEY",
    "EXA_API_KEY",
    "PARALLEL_API_KEY",
    "OPENROUTER_API_KEY",
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "GOOGLE_API_KEY",
    "GEMINI_API_KEY",
    "TELEGRAM_BOT_TOKEN",
    "OLLAMA_API_KEY",
]


def _hermes_pids():
    """Return PIDs of processes whose cmdline contains 'hermes'."""
    pids = []
    for path in glob.glob("/proc/[0-9]*/cmdline"):
        try:
            with open(path, "rb") as f:
                data = f.read()
            if b"hermes" in data.lower():
                pid = os.path.basename(os.path.dirname(path))
                pids.append(int(pid))
        except (OSError, ValueError):
            continue
    return pids


def _env_for_pid(pid: int) -> dict:
    """Return parsed environ dict for a pid."""
    try:
        with open(f"/proc/{pid}/environ", "rb") as f:
            raw = f.read()
    except OSError:
        return {}
    env = {}
    for item in raw.split(b"\0"):
        if b"=" not in item:
            continue
        key, val = item.split(b"=", 1)
        try:
            env[key.decode("utf-8", "replace")] = val.decode("utf-8", "replace")
        except UnicodeDecodeError:
            continue
    return env


def _process_type(cmdline: bytes) -> str:
    """Classify whether this is a gateway or TUI process."""
    low = cmdline.lower()
    if b"gateway" in low:
        return "gateway"
    if b"chat" in low or b"tui" in low:
        return "TUI"
    return "other"



def main() -> int:
    pids = _hermes_pids()
    if not pids:
        print("No Hermes processes found.")
        return 1

    any_found = False
    for pid in sorted(pids):
        env = _env_for_pid(pid)
        found = [(k, env.get(k, "")[:8] + "..." if env.get(k) else "")
                 for k in KEY_NAMES if k in env]
        # Determine process type from cmdline
        ptype = "other"
        for path in glob.glob("/proc/[0-9]*/cmdline"):
            if os.path.basename(os.path.dirname(path)) == str(pid):
                try:
                    with open(path, "rb") as f:
                        data = f.read()
                    ptype = _process_type(data)
                except OSError:
                    pass
                break
        if not found:
            print(f"PID {pid} ({ptype}): no API keys loaded")
            continue
        any_found = True
        print(f"PID {pid} ({ptype}): found {len(found)} key(s)")
        for k, v in found:
            print(f"  {k}={v}")

    if not any_found:
        print("Hermes processes found, but none have the expected API keys loaded.")
        print("Probable cause: env variables not exported in the shell before process start.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
