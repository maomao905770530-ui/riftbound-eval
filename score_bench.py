"""Score pilot run results with an LLM judge + consistency check.

Why LLM-as-judge here: the gold answers already exist (human-reviewed), so
the judge only decides semantic equivalence between a model's final outcome
and the gold — much weaker than free-form judging. Reliability controls:
  - every item is judged TWICE; disagreement -> "unjudgeable" (manual review)
  - the judge sees the task and both effect chains, not just conclusions
Known limitation (pilot only): judge model == one of the evaluated models;
the formal run should use a stronger judge and human-verify a sample.

Core output: the base/variant consistency matrix per case:
  both_correct   -> genuine rule use
  base_only      -> surface pattern match (counterfactual FAILURE - the key metric)
  variant_only   -> lucky guess
  both_wrong     -> comprehension failure

Usage: python score_bench.py results/pilot_deepseek_XXX.jsonl [...]
Writes: results/scored_<name>.jsonl and prints a summary.
"""

import datetime
import json
import os
import sys
import time
import urllib.request

ENV_PATH = ".env"
JUDGE = {
    "base_url": "https://api.deepseek.com",
    "model": "deepseek-chat",
    "key_env": "DEEPSEEK_API_KEY",
}

JUDGE_SYSTEM = (
    "You are a strict grader for game-rule reasoning answers. Decide whether the "
    "model's final outcome is semantically equivalent to the gold answer. Key facts "
    "matter (who dies/survives, what is drawn/readied/played, counts, legality); "
    "wording does not. Output only JSON."
)

JUDGE_TEMPLATE = """TASK:
{task}

GOLD ANSWER: {gold}
GOLD EFFECT CHAIN: {gold_chain}

MODEL ANSWER: {model_out}
MODEL EFFECT CHAIN: {model_chain}

Question: Is the model's final outcome semantically equivalent to the gold answer?
Return JSON: {{"verdict": "correct" | "incorrect" | "partial", "reason": "<one sentence>"}}"""

def load_env(path: str) -> dict:
    env = dict(os.environ)
    try:
        for line in open(path, encoding="utf-8-sig"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env.setdefault(k.strip(), v.strip())
    except FileNotFoundError:
        pass
    return env

def call_judge(key: str, user_msg: str, retries: int = 3) -> str:
    payload = {
        "model": JUDGE["model"],
        "messages": [
            {"role": "system", "content": JUDGE_SYSTEM},
            {"role": "user", "content": user_msg},
        ],
        "temperature": 0.0,
        "max_tokens": 300,
    }
    body = json.dumps(payload).encode("utf-8")
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(
                JUDGE["base_url"].rstrip("/") + "/chat/completions",
                data=body,
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))["choices"][0]["message"]["content"]
        except Exception as e:  # noqa: BLE001
            print(f"  judge attempt {attempt} failed: {e}", file=sys.stderr)
            time.sleep(2 * attempt)
    return ""

def parse_verdict(raw: str) -> str:
    import re
    if not raw:
        return "judge_error"
    m = re.findall(r'"verdict"\s*:\s*"(correct|incorrect|partial)"', raw)
    return m[-1] if m else "judge_error"

def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    env = load_env(ENV_PATH)
    key = env.get(JUDGE["key_env"], "")
    if len(key) < 10:
        print("missing judge key", file=sys.stderr)
        sys.exit(2)

    for path in sys.argv[1:]:
        rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
        # attach the original task text from the bench file
        bench = {json.loads(l)["item_id"]: json.loads(l)
                 for l in open("data/bench/riftbench_origins_v0.3.jsonl", encoding="utf-8") if l.strip()}
        out_path = path.replace(".jsonl", "_scored.jsonl")
        verdicts = {}
        with open(out_path, "w", encoding="utf-8") as out:
            for i, r in enumerate(rows, 1):
                item = bench.get(r["item_id"], {})
                task = item.get("state_task_en", "")
                msg = JUDGE_TEMPLATE.format(
                    task=task,
                    gold=r["gold_final_en"],
                    gold_chain=json.dumps(item.get("effect_chain_en", [])),
                    model_out=r.get("model_final_outcome") or "(no parsed outcome)",
                    model_chain=json.dumps(((r.get("raw_response") or "")[:600])),
                )
                v1 = parse_verdict(call_judge(key, msg))
                v2 = parse_verdict(call_judge(key, msg))
                final = v1 if v1 == v2 else "unjudgeable"
                verdicts[r["item_id"]] = final
                rec = dict(r)
                rec["judge_v1"], rec["judge_v2"], rec["verdict"] = v1, v2, final
                rec["judge_model"] = JUDGE["model"]
                rec["judged_at"] = datetime.datetime.now().isoformat(timespec="seconds")
                out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                out.flush()
                print(f"[{os.path.basename(path)}] {i}/{len(rows)} {r['item_id']} -> {final}")
                time.sleep(0.3)

        # summary: per-case consistency matrix
        by_case = {}
        for r in rows:
            cid = r["case_id"]
            by_case.setdefault(cid, {})[r["pair_role"]] = verdicts[r["item_id"]]
        matrix = {"both_correct": 0, "base_only": 0, "variant_only": 0, "both_wrong": 0, "other": 0}
        for cid, pair in sorted(by_case.items()):
            b, v = pair.get("base"), pair.get("variant")
            if b == "correct" and v == "correct":
                matrix["both_correct"] += 1
            elif b == "correct":
                matrix["base_only"] += 1
            elif v == "correct":
                matrix["variant_only"] += 1
            elif b == "incorrect" and v == "incorrect":
                matrix["both_wrong"] += 1
            else:
                matrix["other"] += 1
        total = len(rows)
        correct = sum(1 for x in verdicts.values() if x == "correct")
        print(f"\n=== {os.path.basename(path)} ===")
        print(f"accuracy: {correct}/{total}")
        print(f"consistency matrix: {matrix}")
        print(f"counterfactual failure rate (base_only): {matrix['base_only']}/{len(by_case)}")
        print(f"scored -> {out_path}\n")

if __name__ == "__main__":
    main()
