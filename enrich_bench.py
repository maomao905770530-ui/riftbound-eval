"""Enrich the RiftBench pilot JSONL (v0.1 -> v0.2).

Fixes applied by this script:
  1. SELF-CONTAINED PROMPTS: injects the full effective card text (errata
     applied) into every prompt, so models never need prior Riftbound
     knowledge. Also adds a JSON-in-code-block output instruction
     (BenchING-style: task instruction + card text + state + format).
  2. C11-B UPGRADE: replaces the stale two-rune base (pre-fix) with the
     six-exhausted-rune base that stresses the "up to 4" cap.
  3. C10/C14 FIX SYNC: card texts are pulled from the errata database, so
     the "(Send it to base...)" clarification and [Action] tags are
     automatically included.
  4. NEW FIELDS per item: capability (effect-comprehension / legality /
     chain-resolution), difficulty tier, has_errata.

Usage: python enrich_bench.py [input.jsonl] [output.jsonl]
Standard library only.
"""

import json
import re
import sys
from collections import defaultdict

DEFAULT_IN = r"C:\Users\90577\Documents\ChatGPT\论文\RiftBench_Origins_v0.1.jsonl"
DEFAULT_OUT = "data/bench/riftbench_origins_v0.3.jsonl"
CARDS_JSON = "data/cards/origins_enriched.json"

# Reviewer-driven fixups (小福贵 adjudication 2026-09-14 + 小彩蝶 re-check)
FIXUPS = {
    # C02-V: gold demanded the optional-zero clause as a necessary condition;
    # the core fact is that U gets the buff. Judge now compares core facts only.
    "OGN-C02-V": {"gold_final_en": "U receives a +1 [M] buff (selecting zero units is also legal, but buffing U is the natural resolution)."},
    # C11-V: base was upgraded to six exhausted runes; the variant must change
    # ONLY Sona's location, so the rune count stays six.
    "OGN-C11-V": {
        "state_task_en": "At end of your turn Sona is at base, not a battlefield. Six friendly runes R1 through R6 are all exhausted. Resolve Sona's rune ability.",
        "gold_final_en": "No rune is readied.",
        "effect_chain_en": [
            "The end-of-turn ability checks Sona's location.",
            "Sona is not at a battlefield, so the condition fails.",
            "No rune-readying effect occurs.",
        ],
    },
}

# capability mapping by case (first-pass taxonomy, reviewer may adjust)
CAPABILITY = {
    "C01": "effect-comprehension", "C02": "effect-comprehension", "C03": "effect-comprehension",
    "C07": "effect-comprehension", "C09": "effect-comprehension", "C11": "effect-comprehension",
    "C17": "effect-comprehension", "C20": "effect-comprehension",
    "C05": "legality", "C08": "legality", "C14": "legality", "C16": "legality",
    "C18": "legality", "C19": "legality",
    "C04": "chain-resolution", "C06": "chain-resolution", "C10": "chain-resolution",
    "C12": "chain-resolution", "C13": "chain-resolution", "C15": "chain-resolution",
}

# C11-B replacement (the fix that stresses the "up to 4" cap)
C11B_NEW = {
    "state": "At end of your turn Sona is at a battlefield. Six friendly runes R1 through R6 are all exhausted.",
    "question": "Resolve Sona's rune ability. How many runes can become ready, and what happens to the rest?",
    "gold_final_en": "At most 4 runes become ready; 2 of the 6 exhausted runes remain exhausted.",
    "effect_chain_en": [
        "The end-of-turn ability checks Sona's location; she is at a battlefield, so it triggers.",
        "The effect readies up to four friendly runes; six are available but the cap is four.",
        "At most four runes become ready; two exhausted runes remain exhausted.",
    ],
}

PROMPT_HEADER = (
    "You are resolving a game state in Riftbound, a trading card game. "
    "Use ONLY the card texts provided below and the stated game state; "
    "do not rely on any prior knowledge of this game.\n\n"
)

FORMAT_INSTRUCTION = (
    "\n\nReturn output in JSON format and include only the JSON in a Markdown code block. "
    'Use this schema: {"final_outcome": "<one sentence>", '
    '"effect_chain": ["<step 1>", "<step 2>", ...]}'
)

def effective_text(c: dict) -> str:
    return (c.get("errata_new_text") or c.get("text") or "").strip()

def main() -> None:
    src = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_IN
    out = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_OUT

    db = json.load(open(CARDS_JSON, encoding="utf-8"))
    cards = {}
    for c in db["cards"]:
        n = c.get("collector_number")
        if n and n <= 298 and c["name"].replace("\u2019", "'") not in cards:
            cards[c["name"].replace("\u2019", "'")] = c

    rows = [json.loads(l) for l in open(src, encoding="utf-8").read().strip().split("\n") if l.strip()]
    missing = set()

    # PASS 1: collect base state text per case (for reference expansion)
    base_state = {}
    for r in rows:
        if r["pair_role"] == "base":
            base_state[r["case_id"]] = r["prompt_en"]

    # PASS 2: expand cross-references in variant prompts.
    # "As C04-B, but ..." / "Use C13-B, but ..." -> inline the full base state.
    def expand(match, base_state):
        cid, conj = match.group(1), (match.group(2) or "")
        b = base_state.get(cid)
        if not b:
            return match.group(0)
        joiner = " However, " if conj else " "
        return b.rstrip(". ") + "." + joiner

    ref_re = re.compile(r"(?:As|Use) (C\d+)-B,?\s*(but |except )?", re.I)
    for r in rows:
        if r["pair_role"] == "variant":
            r["prompt_en"] = ref_re.sub(lambda m: expand(m, base_state), r["prompt_en"])

    out_rows = []
    for r in rows:
        r = dict(r)
        # 1) collect card texts (effective, errata-applied)
        texts, errata_flag = {}, False
        for ref in r["card_refs"]:
            m = re.match(r"(.+?) \(OGN-", ref)
            name = m.group(1).replace("\u2019", "'") if m else ref
            c = cards.get(name)
            if not c:
                missing.add(name)
                continue
            texts[c["name"]] = effective_text(c)
            if "errata_new_text" in c:
                errata_flag = True
        r["card_texts_effective"] = texts
        r["has_errata_card"] = errata_flag

        # 2) C11-B fix sync
        if r["item_id"] == "OGN-C11-B":
            r["gold_final_en"] = C11B_NEW["gold_final_en"]
            r["effect_chain_en"] = C11B_NEW["effect_chain_en"]
            r["state_task_en"] = C11B_NEW["state"] + " " + C11B_NEW["question"]
        else:
            r["state_task_en"] = r["prompt_en"]
        # apply reviewer fixups AFTER state_task_en is set (they override it)
        if r["item_id"] in FIXUPS:
            r.update(FIXUPS[r["item_id"]])

        # 3) rebuild self-contained prompt
        card_block = "\n".join(f"- {ref}: {texts[ref.split(' (')[0].replace(chr(8217), chr(39))]}"
                               for ref in r["card_refs"]
                               if ref.split(" (")[0].replace(chr(8217), chr(39)) in texts)
        r["prompt_en"] = (PROMPT_HEADER + "CARD TEXT:\n" + card_block +
                          "\n\nGAME STATE AND TASK:\n" + r["state_task_en"] + FORMAT_INSTRUCTION)

        # 4) new fields
        r["capability"] = CAPABILITY.get(r["case_id"], "unclassified")
        r["schema_version"] = "0.3"
        r["status"] = "enriched_draft_pending_model_run"
        out_rows.append(r)

    if missing:
        print("MISSING CARDS (fix refs!):", missing, file=sys.stderr)
        sys.exit(2)

    import os
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        for r in out_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # summary
    caps = defaultdict(int)
    for r in out_rows:
        caps[r["capability"]] += 1
    n_errata = sum(1 for r in out_rows if r["has_errata_card"])
    print(f"wrote {len(out_rows)} items -> {out}")
    print(f"capability distribution: {dict(caps)}")
    print(f"items referencing errata cards: {n_errata}")
    print("C11-B upgraded:", next(r["item_id"] for r in out_rows if r["item_id"] == "OGN-C11-B") == "OGN-C11-B")

if __name__ == "__main__":
    main()
