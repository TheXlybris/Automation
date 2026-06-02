#!/usr/bin/env python3
"""
Diagnose why web_search returns "No web search provider configured"

Checks:
1. config.yaml has a search backend configured
2. .env has the corresponding API key
3. The gateway process actually has the key in its environment
4. The backend Python module imports cleanly

Usage: python3 scripts/diagnose-web-search.py
"""
import os, re, subprocess, sys

HERMES_HOME = os.path.expanduser("~/.hermes")
CONFIG_PATH = os.path.join(HERMES_HOME, "config.yaml")
ENV_PATH = os.path.join(HERMES_HOME, ".env")

def find_gateway_pid():
    try:
        out = subprocess.check_output(["pgrep", "-f", "hermes_cli.main gateway"], text=True)
        return [int(p) for p in out.strip().split("\n") if p]
    except subprocess.CalledProcessError:
        return []

def env_of_pid(pid):
    try:
        raw = open(f"/proc/{pid}/environ", "rb").read()
        return dict(kv.split("=", 1) for kv in raw.split(b"\x00") if b"=" in kv)
    except Exception:
        return {}

def main():
    issues = 0
    print("=== Web Search Diagnosis ===\n")

    # 1. Config
    if os.path.exists(CONFIG_PATH):
        cfg = open(CONFIG_PATH).read()
        m = re.search(r'search_backend:\s*([a-z0-9_]+)', cfg)
        backend = m.group(1) if m else None
        if backend:
            print(f" Search backend in config.yaml: {backend}")
        else:
            print(" [ISSUE] No search_backend found in config.yaml")
            issues += 1
    else:
        print(f" [ISSUE] config.yaml not found at {CONFIG_PATH}")
        issues += 1

    # 2. .env key
    env_key = None
    if os.path.exists(ENV_PATH):
        for line in open(ENV_PATH):
            line = line.strip()
            if line.startswith("TAVILY_API_KEY=") or line.startswith("FIRECRAWL_API_KEY=") or line.startswith("EXA_API_KEY=") or line.startswith("PARALLEL_API_KEY="):
                key = line.split("=", 1)[1]
                print(f" {line.split('=')[0]} in .env: {'=' * min(8, len(key))}{key[-8:] if len(key) > 8 else ''}")
                env_key = key
    else:
        print(f" [ISSUE] .env not found at {ENV_PATH}")
        issues += 1

    # 3. Gateway env
    pids = find_gateway_pid()
    if not pids:
        print(" [ISSUE] No gateway process running")
        issues += 1
    else:
        for pid in pids:
            proc_env = env_of_pid(pid)
            has_tavily = b"TAVILY_API_KEY" in proc_env
            has_firecrawl = b"FIRECRAWL_API_KEY" in proc_env
            if has_tavily or has_firecrawl:
                print(f" PID {pid}: key IS present in process environment")
            else:
                print(f" [CRITICAL] PID {pid}: key is MISSING from process environment")
                print("  -> Gateway was started before the key was exported")
                print("  -> Fix: run 'export TAVILY_API_KEY=<key>', then restart gateway")
                issues += 1

    # 4. Direct Python import check
    try:
        import yaml
        if os.path.exists(CONFIG_PATH):
            cfg = yaml.safe_load(open(CONFIG_PATH))
            search_backend = cfg.get("web", {}).get("search_backend")
            if search_backend:
                try:
                    mod = __import__(f"tools.{search_backend}", fromlist=["tools"])
                    print(f" Backend module 'tools.{search_backend}' imports OK")
                except Exception as e:
                    print(f" [ISSUE] Backend module import failed: {e}")
                    issues += 1
    except ImportError:
        pass  # yaml not installed, skip

    if issues == 0:
        print("\n All checks passed. web_search should work.")
    else:
        print(f"\n {issues} issue(s) found. See above.")
    return 1 if issues else 0

if __name__ == "__main__":
    sys.exit(main())
