# riftbound-eval

I'm studying how well large language models play [Riftbound](https://playriftbound.com/), the League of Legends trading card game — not full games yet, but the individual decisions a player faces: reading card text, picking legal plays, and planning resources.

Why Riftbound? Its cards are dense natural-language artifacts — effects, triggers, restrictions — so playing well requires exactly the kind of precise reading that LLMs are supposed to be good at, and often aren't. The game is also new (released October 2025) and has no official digital client, so no published LLM benchmark for it exists as far as I can tell.

## What's here now

- `01_hello_llm.py` — a minimal end-to-end script: builds a decision prompt, calls an OpenAI-compatible API, saves the answer. Run with `--mock` to test the pipeline without spending credits.
- `env_check.py` — sanity checks for Python, network, git, and the API key.
- `data/cards/` — card data from the Origins set. A format example is included; real data is being collected.

## What's coming

- An evaluation set of ~100 decision problems (card text understanding, move selection, resource planning), each with a reference answer and a rationale.
- Runs across 6–8 models (proprietary and open, reasoning and non-reasoning), followed by error analysis grouped by failure mode.

## Reproducibility notes

- Everything is pinned to the 2026-07 core rules update and the Origins set. Card records store their source and retrieval date.
- Each experiment run will record model version, temperature, and sampling settings.
- API keys live in a local `.env` file, which is gitignored. No keys in the repo, ever.

## Setup

Python 3.10+ only, standard library — nothing to install. Put your key in a `.env` file in the project root:

```
DEEPSEEK_API_KEY=sk-...
```

Then:

```
python env_check.py            # sanity check
python 01_hello_llm.py --mock  # no API cost
python 01_hello_llm.py         # real call
```
