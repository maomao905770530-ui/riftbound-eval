# -*- coding: utf-8 -*-
"""
01_hello_llm.py -- minimal end-to-end example for this repo.

Builds a single decision prompt, calls an OpenAI-compatible chat API,
and persists the answer as JSON. This is the same loop the full
evaluation pipeline uses, scaled down to one question.

Usage:
  python 01_hello_llm.py --mock   # offline test, no API cost
  python 01_hello_llm.py          # real call; reads DEEPSEEK_API_KEY
                                  # from the environment or a .env file

Standard library only, by design: fewer installs, fewer failure points.
"""
import json
import os
import sys
import time
import urllib.request

# --- Provider settings. Switching vendors means editing these three lines. ---
BASE_URL = "https://api.deepseek.com"   # e.g. Qwen: https://dashscope.aliyuncs.com/compatible-mode/v1
MODEL = "deepseek-chat"
KEY_ENV = "DEEPSEEK_API_KEY"
# -----------------------------------------------------------------------------


def load_env_file(filename=".env"):
    """Load KEY=VALUE pairs from a local .env file into os.environ.

    Variables already set in the environment take precedence. Encoding
    is utf-8-sig so the file survives being saved by Windows Notepad,
    which prepends a BOM.
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
    """Send one user message, return the reply text."""
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
    """Persist one prompt/answer pair.

    The model name and timestamp are stored with every record so that
    results stay comparable across runs and models.
    """
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

    # A minimal single-decision probe. The full evaluation set will
    # extend this pattern to ~100 items with reference answers.
    question = (
        "You are playing a card game. You have 2 resources this turn. Your hand:\n"
        "A. Cost 2: summon a unit with 3 attack.\n"
        "B. Cost 1: draw a card.\n"
        "C. Cost 0: gain 1 shield until end of turn.\n"
        "Your opponent has a unit with 2 attack on the battlefield. "
        "Pick the best action among A/B/C and justify it in one sentence."
    )
    print("Prompt:")
    print(question)
    print()

    if mock:
        answer = ("[mock] B: the 3-attack unit does not immediately remove the "
                  "opponent's 2-attack unit, and drawing keeps a resource open.")
        print("(mock reply)")
        print(answer)
    else:
        load_env_file()
        api_key = os.environ.get(KEY_ENV, "")
        if not api_key:
            sys.exit(
                "No API key found. Either put DEEPSEEK_API_KEY=sk-... in a .env "
                "file next to this script (see README), or run with --mock for "
                "an offline test."
            )
        print("Calling model ...")
        answer = ask_llm(question, api_key)
        print("Reply:")
        print(answer)

    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "hello_llm.json")
    save_result(question, answer, out_path)
    print()
    print("Result saved to " + out_path)
