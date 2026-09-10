# riftbound-eval

Evaluating how well large language models play Riftbound, the League of Legends trading card game, at the level of individual decisions: card text understanding, legal-move selection, and resource planning.

Part of a research project on LLM agents in strategic games. The evaluation set, experiment scripts, and results will be added as they are built.

## Setup

Requires Python 3.10+.

1. Clone the repo and create a `.env` file in the project root:

   ```
   DEEPSEEK_API_KEY=sk-...
   ```

2. Check your environment:

   ```
   python env_check.py
   ```

3. Smoke test without spending API credits:

   ```
   python 01_hello_llm.py --mock
   ```

4. Run a real query:

   ```
   python 01_hello_llm.py
   ```

## Structure

```
01_hello_llm.py     minimal end-to-end example: prompt -> API call -> saved result
env_check.py        environment sanity checks
data/cards/         card text data (Origins set)
results/            model outputs, gitignored
docs/               project notes and literature notes
```

## Data versioning

Card data and experiments are tied to a fixed rules version (2026-07 core rules update) and set (Origins). Each card record stores its source and retrieval date.

## Status

Work in progress. Current stage: building the evaluation set.
