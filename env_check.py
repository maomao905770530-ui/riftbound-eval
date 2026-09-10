# -*- coding: utf-8 -*-
"""
env_check.py -- environment sanity checks: Python, network, git, API key.

Usage: python env_check.py
"""
import os
import subprocess
import sys
import urllib.request


def check(name, ok, detail=""):
    print(f"[{'OK ' if ok else 'FAIL'}] {name} {detail}")
    return ok


def load_env_file(filename=".env"):
    """Load KEY=VALUE pairs from a local .env file into os.environ.

    Existing environment variables take precedence; utf-8-sig tolerates
    the BOM that Windows Notepad prepends.
    """
    full = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
    if not os.path.exists(full):
        return
    with open(full, encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and value and key not in os.environ:
                os.environ[key] = value


def main():
    results = []
    load_env_file()

    results.append(check("Python >= 3.10", sys.version_info >= (3, 10), sys.version.split()[0]))

    try:
        urllib.request.urlopen("https://www.baidu.com", timeout=8)
        results.append(check("Network reachable", True))
    except Exception as e:
        results.append(check("Network reachable", False, str(e)[:60]))

    try:
        v = subprocess.run(["git", "--version"], capture_output=True, text=True).stdout.strip()
        results.append(check("Git installed", True, v))
    except Exception:
        results.append(check("Git installed", False, "(optional, see git-scm.com)"))

    key = os.environ.get("DEEPSEEK_API_KEY", "")
    results.append(check("API key configured", bool(key), "" if key else "(--mock works without it)"))

    core_ok = results[0] and results[1]
    print("\n" + ("Core environment ready." if core_ok else "Fix the FAIL items first."))


if __name__ == "__main__":
    main()
