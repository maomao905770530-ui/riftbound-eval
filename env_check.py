# -*- coding: utf-8 -*-
"""
env_check.py —— 环境自检：Python / 网络 / Git / API Key。全绿就能开工。

用法：python env_check.py
"""
import os
import subprocess
import sys
import urllib.request


def check(name, ok, detail=""):
    print(f"[{'OK ' if ok else 'FAIL'}] {name} {detail}")
    return ok


def load_env_file(filename=".env"):
    """从脚本所在目录的 .env 文件读取 KEY=VALUE（不覆盖已有环境变量）。"""
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

    results.append(check("Python 版本 >= 3.10", sys.version_info >= (3, 10), sys.version.split()[0]))

    try:
        urllib.request.urlopen("https://www.baidu.com", timeout=8)
        results.append(check("网络连通", True))
    except Exception as e:
        results.append(check("网络连通", False, str(e)[:60]))

    try:
        v = subprocess.run(["git", "--version"], capture_output=True, text=True).stdout.strip()
        results.append(check("Git 已安装", True, v))
    except Exception:
        results.append(check("Git 已安装", False, "（可选，去 git-scm.com 下载）"))

    key = os.environ.get("DEEPSEEK_API_KEY", "")
    results.append(check("DeepSeek API Key 已设置", bool(key), "" if key else "（未设置也能先跑 --mock 演练）"))

    core_ok = results[0] and results[1]
    print("\n" + ("Core environment ready." if core_ok else "Fix the FAIL items first."))


if __name__ == "__main__":
    main()
