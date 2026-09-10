# -*- coding: utf-8 -*-
"""
01_hello_llm.py —— 你的第一个 LLM 调用脚本（阶段 0 毕业作业）

跑通它 = 学会评测研究最核心的技术动作：给模型出题、收答案、存结果。

怎么跑：
  1. 去 https://platform.deepseek.com 注册，充值几块钱，创建 API Key
  2. 设置环境变量后运行：
       PowerShell:  $env:DEEPSEEK_API_KEY="sk-xxx"
       CMD:         set DEEPSEEK_API_KEY=sk-xxx
       python 01_hello_llm.py            # 正式调用
  3. 还没注册？先离线演练，不花一分钱：
       python 01_hello_llm.py --mock

零依赖：只用 Python 标准库，不需要 pip install 任何东西。
"""
import json
import os
import sys
import time
import urllib.request

# ---------- 配置区：换厂商只需改这三行 ----------
BASE_URL = "https://api.deepseek.com"   # 阿里Qwen: https://dashscope.aliyuncs.com/compatible-mode/v1
MODEL = "deepseek-chat"                 # 模型名随平台变
KEY_ENV = "DEEPSEEK_API_KEY"            # 环境变量名 / .env 文件里的变量名
# ------------------------------------------------


def load_env_file(filename=".env"):
    """从脚本所在目录的 .env 文件读取 KEY=VALUE，塞进环境变量（不覆盖已有的）。

    这样你只需用记事本把 Key 粘进 .env 文件，不用碰系统环境变量。
    utf-8-sig 是为了容忍记事本保存时自动加的 BOM 头。
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


def ask_llm(question, api_key, temperature=0.7):
    """给 LLM 发一条消息，返回回复文本。OpenAI 兼容接口，全平台通用。"""
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": question}],
        "temperature": temperature,
    }
    req = urllib.request.Request(
        BASE_URL + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + api_key,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"]


def save_result(question, answer, out_path):
    """把问答存成 JSON——评测研究的原始数据就是这么攒的。"""
    record = {
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "model": MODEL,
        "question": question,
        "answer": answer,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    mock = "--mock" in sys.argv

    # 这道题就是一个微型"单决策点评测"样例——阶段 2 会把它扩展成 100 道
    question = (
        "你在玩一款卡牌游戏。你本回合有 2 点资源，手牌如下：\n"
        "A. 花费 2 点：召唤一个 3 攻击力的单位\n"
        "B. 花费 1 点：抽一张牌\n"
        "C. 花费 0 点：本回合结束前获得 1 点护盾\n"
        "对手场上已有一个 2 攻击力的单位。"
        "请从 A/B/C 中选一个最优动作，并用一句话说明理由。"
    )
    print("题目：")
    print(question)
    print()

    if mock:
        answer = "[mock 模式] 选 A：对手场上已有单位，先建立场面压力比抽牌和防御更主动……"
        print("(离线演练回复)")
        print(answer)
    else:
        load_env_file()
        api_key = os.environ.get(KEY_ENV, "")
        if not api_key:
            sys.exit(
                "未找到 API Key。两种设置方式任选：\n"
                "  A. 用记事本打开本目录下的 .env 文件，把 Key 粘到等号后面并保存；\n"
                "  B. 设置环境变量 " + KEY_ENV + "，然后重新运行。\n"
                "或者先跑 --mock 离线演练。"
            )
        print("正在调用模型，请稍候……")
        answer = ask_llm(question, api_key)
        print("模型回复：")
        print(answer)

    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "hello_llm.json")
    save_result(question, answer, out_path)
    print()
    print("Result saved to " + out_path)
