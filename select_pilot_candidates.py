"""Select pilot-question candidate cards from the Origins pool.

Why: the v3 pilot (20-30 counterfactual items) needs a stratified candidate
pool. This script builds it with two hard safety rails:
  1. ERRATA SAFETY: it REFUSES to run on origins_raw.json - only the
     errata-merged origins_enriched.json is accepted, so question text can
     never be built from stale as-printed wording.
  2. POOL DEDUP: 298 base cards only (collector_number 1-298, one entry per
     number). Alt-art (a-suffix) and overnumbered variants are dropped.
     Dedup is by collector number, NEVER by name (30 same-name-different-
     card pairs exist: 15 champions x2 + 6 runes x2).

Stratification (effect-chain complexity, heuristic):
  - rune cards: no ability text -> listed separately (T3 resource material)
  - simple:   <=1 sentence, no bracketed keywords beyond the action tag
  - medium:   2 sentences or 1 keyword like [Reaction]/[Hidden]/[Ganking]
  - complex:  >=3 sentences or >=2 keywords or chain connectors (Then/If you do)
  - errata cards (32) listed separately as priority candidates (their
    ambiguity is exactly what makes good effect-chain reasoning items)

Usage: python select_pilot_candidates.py
Writes: data/cards/pilot_candidates.json
"""

import json
import re
import sys

SRC = "data/cards/origins_enriched.json"  # errata-merged ONLY - see rail 1
OUT = "data/cards/pilot_candidates.json"

KEYWORDS = ["[Reaction]", "[Hidden]", "[Ganking]", "[Vision]", "[Deflect]", "[Assault]", "[Mighty]", "[Quick-Draw]", "[Predict]", "[Repeat]"]
CHAIN_WORDS = ["then", "if you do", "instead", "may", "when you"]

def effective_text(c: dict) -> str:
    """Effective wording = errata text if present, else as-printed text."""
    return c.get("errata_new_text") or c.get("text") or ""

def complexity(c: dict):
    txt = effective_text(c)
    sents = [s for s in re.split(r"\n|(?<=\.)\s+", txt) if s.strip()]
    n_kw = sum(1 for k in KEYWORDS if k.lower() in txt.lower())
    n_chain = sum(1 for w in CHAIN_WORDS if w in txt.lower())
    score = len(sents) + n_kw + n_chain
    if n_kw >= 2 or len(sents) >= 3 or n_chain >= 3:
        return "complex", score
    if n_kw == 1 or len(sents) == 2 or n_chain == 2:
        return "medium", score
    return "simple", score

def main() -> None:
    if "enriched" not in SRC:
        print("REFUSING: source must be the errata-merged enriched file, not raw.", file=sys.stderr)
        sys.exit(2)
    d = json.load(open(SRC, encoding="utf-8"))
    cards = d["cards"]

    base = {}
    for c in cards:
        n = c.get("collector_number")
        if n and 1 <= n <= 298 and n not in base:
            base[n] = c
    assert len(base) == 298, f"expected 298 base cards, got {len(base)}"

    runes, simple, medium, complex_, errata = [], [], [], [], []
    for n, c in sorted(base.items()):
        if "rune" in (c.get("type") or []):
            runes.append(c)
            continue
        tier, score = complexity(c)
        entry = {
            "public_code": c["public_code"],
            "name": c["name"],
            "type": c["type"],
            "energy": c["energy"],
            "tier": tier,
            "complexity_score": score,
            "text": effective_text(c)[:400],
            "has_errata": "errata_new_text" in c,
        }
        {"simple": simple, "medium": medium, "complex": complex_}[tier].append(entry)
        if "errata_new_text" in c:
            errata.append(entry)

    out = {
        "meta": {
            "source": SRC,
            "pool": "298 base cards (collector_number 1-298, dedup by number)",
            "note": "Effective text (errata applied) used for all entries. Errata cards are priority pilot candidates.",
            "counts": {
                "simple": len(simple), "medium": len(medium), "complex": len(complex_),
                "runes_separate": len(runes), "errata": len(errata),
            },
        },
        "errata_cards": errata,
        "simple": simple,
        "medium": medium,
        "complex": complex_,
    }
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"pool: 298 | simple {len(simple)} | medium {len(medium)} | complex {len(complex_)} | runes {len(runes)} | errata {len(errata)}")
    print(f"wrote {OUT}")

if __name__ == "__main__":
    main()
