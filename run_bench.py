"""Run the RiftBench pilot benchmark against one or more models.

Design notes (why it looks like this):
- Zero-dependency urllib calls (project convention: fewer failure points).
- BenchING-style error classification for every response:
  empty_response / incorrect_syntax / incomplete_keys / parsed_ok.
- Version lock: the exact model id returned by the API, sampling params,
  and a timestamp are stored with EVERY record (README reproducibility
  promise).
- Raw responses are kept verbatim so parsing can be re-audited later
  without re-paying for calls.

Usage:
    python run_bench.py --model deepseek            # one model
    python run_bench.py --model qwen
    python run_bench.py --model deepseek --limit 3  # smoke test
Results -> results/pilot_<model>_<ts>.jsonl
"""

import argparse
import datetime
import json
import os
import re
import sys
import time
import urllib.request

BENCH_PATH = "data/bench/riftbench_origins_v0.2.jsonl"
ENV_PATH = ".env"

MODELS = {
    "deepseek": {
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-chat",
        "key_env": "DEEPSEEK_API_KEY",
    },
    "qwen": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-plus",
        "key_env": "DASHSCOPE_API_KEY",
    },
}

SYSTEM_PROMPT = (
    "You are a careful game-rules engine. Resolve the given game state step by step, "
    "using only the card texts and state provided. Output only the requested JSON."
)

def load_env(path: str) -> dict:
    env = dict(os.environ)
    try:
        for line in open(path, encoding="utf-8-sig"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env.setdefault(k.strip(), v.strip())  # existing env wins, like 01_hello_llm.py
    except FileNotFoundError:
        pass
    return env

def call_llm(base_url: str, model: str, key: str, user_msg: str, temperature: float, retries: int = 3) -> dict:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        "temperature": temperature,
        "max_tokens": 1500,
    }
    body = json.dumps(payload).encode("utf-8")
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(
                base_url.rstrip("/") + "/chat/completions",
                data=body,
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:  # noqa: BLE001
            last_err = e
            err_txt = ""
            if hasattr(e, "read"):
                try:
                    err_txt = e.read().decode("utf-8", errors="replace")[:300]
                except Exception:
                    pass
            print(f"  attempt {attempt}/{retries} failed: {e} {err_txt}", file=sys.stderr)
            time.sleep(3 * attempt)
    return {"__error__": f"{last_err}"}

def extract_and_classify(raw_text: str) -> dict:
    """BenchING-style classification of the model output."""
    if not raw_text or not raw_text.strip():
        return {"error_class": "empty_response", "parsed": None}
    blocks = re.findall(r"```(?:json)?\s*(.*?)```", raw_text, re.S)
    content = blocks[-1].strip() if blocks else raw_text.strip()
    try:
        obj = json.loads(content)
    except json.JSONDecodeError:
        return {"error_class": "incorrect_syntax", "parsed": None, "extracted": content[:500]}
    if not isinstance(obj, dict) or "final_outcome" not in obj or "effect_chain" not in obj:
        return {"error_class": "incomplete_keys", "parsed": obj}
    return {"error_class": "parsed_ok", "parsed": obj}

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, choices=list(MODELS) + ["all"])
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--temperature", type=float, default=0.2)
    ap.add_argument("--bench", default=BENCH_PATH)
    args = ap.parse_args()

    env = load_env(ENV_PATH)
    items = [json.loads(l) for l in open(args.bench, encoding="utf-8") if l.strip()]
    if args.limit:
        items = items[: args.limit]
    print(f"items: {len(items)} | temperature: {args.temperature}")

    todo = list(MODELS) if args.model == "all" else [args.model]
    for mkey in todo:
        cfg = MODELS[mkey]
        key = env.get(cfg["key_env"], "")
        if len(key) < 10:
            print(f"[{mkey}] MISSING {cfg['key_env']} - skipped", file=sys.stderr)
            continue
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = f"results/pilot_{mkey}_{ts}.jsonl"
        os.makedirs("results", exist_ok=True)
        stats = {"empty_response": 0, "incorrect_syntax": 0, "incomplete_keys": 0, "parsed_ok": 0}
        with open(out_path, "w", encoding="utf-8") as out:
            for i, item in enumerate(items, 1):
                resp = call_llm(cfg["base_url"], cfg["model"], key, item["prompt_en"], args.temperature)
                if "__error__" in resp:
                    raw_text, api_model, usage = "", None, None
                    stats["empty_response"] += 1
                    cls = {"error_class": "api_error", "parsed": None}
                else:
                    choice = resp["choices"][0]["message"]
                    raw_text = choice.get("content") or ""
                    api_model = resp.get("model")
                    usage = resp.get("usage")
                    cls = extract_and_classify(raw_text)
                    stats[cls["error_class"]] = stats.get(cls["error_class"], 0) + 1
                rec = {
                    "item_id": item["item_id"],
                    "case_id": item["case_id"],
                    "pair_role": item["pair_role"],
                    "capability": item["capability"],
                    "benchmark_schema": item["schema_version"],
                    "model_requested": cfg["model"],
                    "model_returned": api_model,
                    "temperature": args.temperature,
                    "ts": datetime.datetime.now().isoformat(timespec="seconds"),
                    "error_class": cls["error_class"],
                    "gold_final_en": item["gold_final_en"],
                    "model_final_outcome": (cls.get("parsed") or {}).get("final_outcome"),
                    "raw_response": raw_text,
                    "usage": usage,
                }
                out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                out.flush()
                print(f"[{mkey}] {i}/{len(items)} {item['item_id']} -> {cls['error_class']}")
                time.sleep(0.5)
        print(f"\n[{mkey}] DONE -> {out_path}")
        print(f"[{mkey}] stats: {stats} | parse rate: {stats['parsed_ok']}/{len(items)}")

if __name__ == "__main__":
    main()
