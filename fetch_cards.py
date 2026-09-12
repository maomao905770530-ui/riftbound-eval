"""Fetch Riftbound Origins card data from the official card gallery API.

Why this script exists: the pilot study (20-30 counterfactual items) needs
verbatim card text with a traceable source. The official gallery exposes a
JSON endpoint (no auth) used by the card gallery page itself; pulling from
it guarantees the text matches the source we cite, instead of relying on
community re-transcriptions.

Scope: this project freezes its card pool to the first set, Origins (OGN),
per the version-locking policy in the research plan. Other sets are fetched
by the API but filtered out here.

Usage:
    python fetch_cards.py                # fetch Origins set -> data/cards/origins_raw.json
    python fetch_cards.py --limit 5      # small test run
    python fetch_cards.py --out other.json

Output: one JSON file with metadata (fetch time, API URL, build id, set
filter, card count) plus a list of card records. Raw file is for internal
research use; check Riot's developer/content policy before redistributing
card text or images publicly.

Standard library only, by design: fewer installs, fewer failure points.
"""

import argparse
import datetime
import json
import re
import sys
import time
import urllib.request

GALLERY_PAGE = "https://riftbound.leagueoflegends.com/en-us/card-gallery"
API_TEMPLATE = "https://riftbound.leagueoflegends.com/_next/data/{build_id}/en-us/card-gallery.json"
SET_FILTER = "OGN"  # Origins only - the card pool is frozen per the research plan

def http_get(url: str, retries: int = 3) -> bytes:
    """GET with retry; the CDN occasionally drops connections."""
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "riftbound-eval-research/0.1"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read()
        except Exception as e:  # noqa: BLE001
            last_err = e
            print(f"  attempt {attempt}/{retries} failed: {e}", file=sys.stderr)
            time.sleep(2 * attempt)
    raise RuntimeError(f"GET failed after {retries} retries: {url} ({last_err})")

def find_build_id(page_html: str) -> str:
    m = re.search(r'"buildId"\s*:\s*"([^"]+)"', page_html)
    if not m:
        raise RuntimeError("buildId not found in gallery page - site layout may have changed")
    return m.group(1)

def facet_value(node: dict):
    """API fields are 'facet' objects: {label, value} or {label, values[]}."""
    if not isinstance(node, dict):
        return node
    if "value" in node and isinstance(node["value"], dict):
        return node["value"].get("id") or node["value"].get("label")
    if "values" in node and isinstance(node["values"], list):
        return [v.get("id") or v.get("label") for v in node["values"] if isinstance(v, dict)]
    return node.get("value")

def facet_label(node: dict):
    if not isinstance(node, dict):
        return node
    if "value" in node and isinstance(node["value"], dict):
        return node["value"].get("label")
    if "values" in node and isinstance(node["values"], list):
        return [v.get("label") for v in node["values"] if isinstance(v, dict)]
    return None

def facet_type_ids(node: dict):
    if not isinstance(node, dict) or not isinstance(node.get("type"), list):
        return []
    return [t.get("id") for t in node["type"] if isinstance(t, dict)]

def strip_html(raw: str) -> str:
    """Card text comes as HTML; plain text is what we feed to models."""
    if not raw:
        return ""
    txt = re.sub(r"<br\s*/?>", "\n", raw)
    txt = re.sub(r"</p>\s*<p[^>]*>", "\n", txt)
    txt = re.sub(r"<[^>]+>", "", txt)
    # collapse spaces but keep the line breaks that structure the card text
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in txt.split("\n")]
    return "\n".join(ln for ln in lines if ln)

def card_text(card: dict) -> str:
    """Ability text lives at text.richText.body as HTML (verified 2026-09-12)."""
    t = card.get("text")
    if isinstance(t, dict):
        body = ((t.get("richText") or {}).get("body")) or ""
        return strip_html(body)
    return strip_html(t if isinstance(t, str) else "")

def simplify(card: dict) -> dict:
    """Flatten one card record to the fields the benchmark needs.

    Card text: the API exposes both the ability text (text.richText.body)
    and the image's accessibilityText. Both are stored; the human-audit
    stage decides which is authoritative if they ever differ.
    """
    img = card.get("cardImage") or {}
    return {
        "id": card.get("id"),
        "public_code": card.get("publicCode"),
        "collector_number": card.get("collectorNumber"),
        "name": card.get("name"),
        "set": facet_value(card.get("set")),
        "set_label": facet_label(card.get("set")),
        "type": facet_type_ids(card.get("cardType")),
        "rarity": facet_value(card.get("rarity")),
        "domains": facet_value(card.get("domain")) or [],
        "energy": facet_value(card.get("energy")),
        "text": card_text(card),
        "accessibility_text": (img.get("accessibilityText") or "").strip(),
    }

def main() -> None:
    ap = argparse.ArgumentParser(description="Fetch Riftbound Origins cards from the official gallery API")
    ap.add_argument("--limit", type=int, default=0, help="keep only first N cards (0 = all)")
    ap.add_argument("--out", default="data/cards/origins_raw.json")
    args = ap.parse_args()

    print("Locating buildId from gallery page ...")
    page = http_get(GALLERY_PAGE).decode("utf-8", errors="replace")
    build_id = find_build_id(page)
    api_url = API_TEMPLATE.format(build_id=build_id)
    print(f"buildId: {build_id}")

    print("Fetching card gallery JSON ...")
    data = json.loads(http_get(api_url).decode("utf-8", errors="replace"))

    # Card list lives at pageProps.page.blades[2].cards.items (verified 2026-09-12).
    try:
        cards = data["pageProps"]["page"]["blades"][2]["cards"]["items"]
    except (KeyError, IndexError, TypeError) as e:
        raise RuntimeError(f"card list not at expected path ({e}) - site structure changed; inspect raw JSON")

    print(f"Total cards in gallery: {len(cards)}")
    kept = [c for c in cards if facet_value(c.get("set")) == SET_FILTER]
    print(f"Cards in set {SET_FILTER} (Origins): {len(kept)}")
    if args.limit:
        kept = kept[: args.limit]

    simplified = [simplify(c) for c in kept]
    record = {
        "meta": {
            "source": api_url,
            "gallery_page": GALLERY_PAGE,
            "build_id": build_id,
            "set_filter": SET_FILTER,
            "fetched_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "card_count": len(simplified),
            "note": "Raw data pulled from the official gallery API for internal research use. "
                    "Card text stored verbatim (text + accessibilityText). Redistribution policy "
                    "TBD pending Riot content policy review.",
        },
        "cards": simplified,
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    empty_text = sum(1 for c in simplified if not c["text"] and not c["accessibility_text"])
    print(f"Saved {len(simplified)} cards -> {args.out}")
    print(f"Cards with empty text fields: {empty_text} (check these manually if > 0)")

if __name__ == "__main__":
    main()
