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


def main():
    results = []

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
    print("\n结论：" + ("核心环境就绪，可以开工。" if core_ok else "先处理 FAIL 项再开工。"))


if __name__ == "__main__":
    main()
