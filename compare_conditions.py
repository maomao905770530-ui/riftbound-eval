"""Three-condition comparison (A / B / C) across scored result files.

Reads the scored JSONL files for both models under all three conditions and
prints:
  1. accuracy per condition (parsed_ok records only, same caliber as the A/B report)
  2. counterfactual failure rate per condition (base correct + variant wrong)
  3. per-case pair matrix (base/variant verdicts x conditions) for the
     diagnosis pairs: C05 (pure-inference adjudication), C17/C19 (conquer
     family), plus every case that failed under B.

Verdict values from score_bench: correct / incorrect / partial / unjudgeable.
Format failures (incorrect_syntax etc.) count as incorrect for the pair
matrix but are excluded from the accuracy line (documented caliber note).
"""
import json
import sys

FILES = {
    ("deepseek", "A"): "results/pilot_deepseek_20260914_162033_scored.jsonl",
    ("deepseek", "B"): "results/pilotB_deepseek_20260914_232052_scored.jsonl",
    ("qwen", "A"): "results/pilot_qwen_20260914_162154_scored.jsonl",
    ("qwen", "B"): "results/pilotB_qwen_20260914_232208_scored.jsonl",
    # C paths filled from argv
}


def load_scored(path):
    rows = {}
    for line in open(path, encoding="utf-8"):
        if line.strip():
            r = json.loads(line)
            rows[r["item_id"]] = r
    return rows


def main():
    c_files = sys.argv[1:]
    data = {}
    for (m, c), p in FILES.items():
        data[(m, c)] = load_scored(p)
    for p in c_files:
        if "deepseek" in p:
            data[("deepseek", "C")] = load_scored(p)
        elif "qwen" in p:
            data[("qwen", "C")] = load_scored(p)

    verdict_ok = {"correct"}

    def is_correct(rec):
        # strict semantic caliber: only 'correct' counts (same as A/B report)
        return rec.get("judge_verdict") in verdict_ok or rec.get("verdict") in verdict_ok

    def has_verdict(rec):
        return bool(rec.get("judge_verdict") or rec.get("verdict"))

    print("=" * 72)
    print("1) ACCURACY (parsed_ok records with verdicts; format failures excluded)")
    for m in ["deepseek", "qwen"]:
        line = [f"  {m:9s}"]
        for c in ["A", "B", "C"]:
            recs = data.get((m, c), {})
            scored = [r for r in recs.values() if has_verdict(r)]
            ok = sum(1 for r in scored if is_correct(r))
            line.append(f"  {c}: {ok}/{len(scored)} ({100*ok/len(scored):.1f}%)" if scored else f"  {c}: n/a")
        print(" |".join(line))

    print("\n2) PAIR MATRIX (base/variant correctness per condition)")
    print("     legend: 1=correct 0=incorrect/partial/unjudgeable .=missing")
    header = "  case  " + "".join(f"{m}-{c}      " for m in ["deepseek", "qwen"] for c in ["A", "B", "C"])
    print(header)

    def pair_verdicts(m, c, case):
        recs = data.get((m, c), {})
        b = recs.get(f"OGN-{case}-B")
        v = recs.get(f"OGN-{case}-V")
        if b is None and v is None:
            return None
        return (int(is_correct(b)) if b else 0, int(is_correct(v)) if v else 0)

    fail_rows = []
    for i in range(1, 21):
        case = f"C{i:02d}"
        cells = []
        for m in ["deepseek", "qwen"]:
            for c in ["A", "B", "C"]:
                pv = pair_verdicts(m, c, case)
                cells.append("--" if pv is None else f"{pv[0]}{pv[1]}")
        # mark cases where C fixed a B failure (for either model)
        fixed = []
        for m in ["deepseek", "qwen"]:
            pvB = pair_verdicts(m, "B", case)
            pvC = pair_verdicts(m, "C", case)
            if pvB and pvC and pvB != (1, 1) and pvC == (1, 1):
                fixed.append(m)
        mark = f"  <-- C fixed ({', '.join(fixed)})" if fixed else ""
        if any(pvB and pvB != (1, 1) for m in ["deepseek", "qwen"] for pvB in [pair_verdicts(m, "B", case)]):
            fail_rows.append(case)
        print(f"  {case}  " + "  ".join(cells) + mark)

    print("\n  cases with any B-condition failure:", ", ".join(fail_rows) or "none")

    print("\n3) COUNTERFACTUAL FAILURE RATE (base correct, variant wrong)")
    for m in ["deepseek", "qwen"]:
        line = [f"  {m:9s}"]
        for c in ["A", "B", "C"]:
            recs = data.get((m, c), {})
            n = fails = 0
            for i in range(1, 21):
                case = f"C{i:02d}"
                b = recs.get(f"OGN-{case}-B")
                v = recs.get(f"OGN-{case}-V")
                if b and v and has_verdict(b) and has_verdict(v):
                    n += 1
                    if is_correct(b) and not is_correct(v):
                        fails += 1
            line.append(f"  {c}: {fails}/{n}")
        print(" |".join(line))

    print("\n4) KEY ADJUDICATION CASES (verdict per condition)")
    for case, label in [("C05", "pure-inference vs retrieval"), ("C17", "conquer family"), ("C19", "conquer family"), ("C15", "damage arithmetic (DeepSeek B regression)")]:
        print(f"  -- {case} ({label})")
        for m in ["deepseek", "qwen"]:
            cells = []
            for c in ["A", "B", "C"]:
                recs = data.get((m, c), {})
                b = recs.get(f"OGN-{case}-B")
                v = recs.get(f"OGN-{case}-V")
                def fmt(r):
                    if r is None:
                        return "missing"
                    vd = r.get("judge_verdict") or r.get("verdict") or r.get("error_class", "?")
                    return vd[:4] + ("*" if not has_verdict(r) else "")
                cells.append(f"{c}: B={fmt(b)} V={fmt(v)}")
            print(f"     {m:9s} " + " | ".join(cells))


if __name__ == "__main__":
    main()
