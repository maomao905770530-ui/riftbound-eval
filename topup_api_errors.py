"""Top-up failed (api_error) records in a condition-C results file.

Only api_error rows are re-run: those are infrastructure failures (proxy/SSL),
not model behavior. incorrect_syntax / truncated rows are NEVER retried here -
selective re-running of model failures would bias the benchmark.
Records are replaced in place; stats are reprinted.
"""
import datetime
import json
import sys

from run_bench import (
    MODELS, ORACLE_MAP_PATH, build_oracle_block, build_oracle_slicer,
    call_llm, extract_and_classify, load_env,
)


def main() -> None:
    path = sys.argv[1]
    mkey = sys.argv[2] if len(sys.argv) > 2 else "qwen"
    cfg = MODELS[mkey]
    env = load_env(".env")
    key = env.get(cfg["key_env"], "")

    oracle_map = json.load(open(ORACLE_MAP_PATH, encoding="utf-8"))
    frags = build_oracle_slicer()

    rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    todo = [r for r in rows if r["error_class"] == "api_error"]
    print(f"{len(todo)} api_error rows to top-up out of {len(rows)}")

    for n, rec in enumerate(todo, 1):
        item = next(
            json.loads(l)
            for l in open("data/bench/riftbench_origins_v0.3.jsonl", encoding="utf-8")
            if l.strip() and json.loads(l)["item_id"] == rec["item_id"]
        )
        block, rules_used = build_oracle_block(item["case_id"], oracle_map, frags)
        assert rules_used == rec["oracle_rules"], f"oracle mismatch on {rec['item_id']}"
        resp = call_llm(cfg["base_url"], cfg["model"], key, block + item["prompt_en"], rec["temperature"], retries=5)
        if "__error__" in resp:
            print(f"  [{n}/{len(todo)}] {rec['item_id']} STILL FAILING - left as api_error")
            continue
        choice = resp["choices"][0]["message"]
        raw_text = choice.get("content") or ""
        cls = extract_and_classify(raw_text)
        rec.update({
            "model_returned": resp.get("model"),
            "finish_reason": resp["choices"][0].get("finish_reason"),
            "ts": datetime.datetime.now().isoformat(timespec="seconds"),
            "error_class": cls["error_class"],
            "model_final_outcome": (cls.get("parsed") or {}).get("final_outcome"),
            "raw_response": raw_text,
            "usage": resp.get("usage"),
            "topup": True,
        })
        print(f"  [{n}/{len(todo)}] {rec['item_id']} -> {cls['error_class']}")

    with open(path, "w", encoding="utf-8") as out:
        for rec in rows:
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
    stats = {}
    for rec in rows:
        stats[rec["error_class"]] = stats.get(rec["error_class"], 0) + 1
    print(f"final stats: {stats}")


if __name__ == "__main__":
    main()
