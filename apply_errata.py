"""Merge official errata into the fetched card data.

Why: the official Card Gallery API serves as-printed text (pre-errata),
while the effective wording is the errata-corrected one. The benchmark
must use the effective wording for questions, so every card record gets:
  - text (as printed, from the gallery - kept for provenance)
  - errata_new_text (effective wording, if this card was errata'd)
  - errata_batch (1 or 2)

Unmatched errata entries are reported loudly instead of being dropped
silently - a name mismatch means the data pipeline needs attention.

Usage:
    python apply_errata.py
        reads  data/cards/origins_raw.json + data/cards/errata.json
        writes data/cards/origins_enriched.json

Standard library only, by design.
"""

import json
import unicodedata

RAW_PATH = "data/cards/origins_raw.json"
ERRATA_PATH = "data/cards/errata.json"
OUT_PATH = "data/cards/origins_enriched.json"

def norm_name(name: str) -> str:
    """Normalize card names for matching: curly -> straight apostrophe, strip, casefold."""
    s = (name or "").replace("\u2019", "'").replace("\u2018", "'").strip()
    return unicodedata.normalize("NFKC", s).casefold()

def main() -> None:
    raw = json.load(open(RAW_PATH, encoding="utf-8"))
    err = json.load(open(ERRATA_PATH, encoding="utf-8"))

    by_name = {}
    for c in raw["cards"]:
        by_name.setdefault(norm_name(c["name"]), []).append(c)

    matched, unmatched, out_of_scope, multi = 0, [], [], []
    for e in err["errata"]:
        if e.get("set") == "OGS":
            out_of_scope.append(e["card_name"])
            continue
        key = norm_name(e["card_name"])
        hits = by_name.get(key, [])
        if not hits:
            unmatched.append(e["card_name"])
            continue
        if len(hits) > 1:
            multi.append((e["card_name"], len(hits)))
        for c in hits:  # applies to every printing variant of the card
            c["errata_new_text"] = e["new_text"]
            c["errata_old_text"] = e["old_text"]
            c["errata_batch"] = e["batch"]
        matched += 1

    raw["meta"]["errata_applied"] = {
        "entries": len(err["errata"]),
        "matched": matched,
        "unmatched": unmatched,
        "out_of_scope_ogs": out_of_scope,
        "multi_variant_cards": multi,
    }
    raw["meta"]["note"] += (
        " Errata merged from official sources; effective wording is errata_new_text "
        "where present, else text."
    )
    json.dump(raw, open(OUT_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    n_errata_cards = sum(1 for c in raw["cards"] if "errata_new_text" in c)
    print(f"matched {matched}/{len(err['errata'])} errata entries")
    print(f"cards carrying errata fields: {n_errata_cards}/{len(raw['cards'])}")
    if unmatched:
        print("UNMATCHED (fix these!):", unmatched)
    if multi:
        print("multi-variant (errata applied to all variants):", multi)
    print(f"wrote {OUT_PATH}")

if __name__ == "__main__":
    main()
