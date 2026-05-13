---
name: warmmemory-benchmark
description: Use this skill whenever the user wants to run, modify, or interpret the WarmMemory benchmark — particularly the LangGraph-based one that compares `full-history`, `vector-only`, and `warm-fallback` retrieval strategies. Trigger on mentions of benchmarking warm memory, comparing memory strategies, evaluating retrieval quality, running `run_langgraph_benchmark` or `scripts/run_langgraph_benchmark.py`, swapping in real embeddings, tuning `warm_hit_threshold` / `top_k` / `warm_capacity`, or interpreting the report at `reports/warm_memory_langgraph_benchmark.md`. Also trigger when the user asks "is warm memory actually better than just using a vector store" or wants to produce benchmark numbers for a writeup, blog post, or PR description.
---

# WarmMemory Benchmark

WarmMemory ships two benchmark harnesses. This skill focuses on the LangGraph-based one, which is the right tool for any comparison that runs through LangGraph's `BaseStore` interface.

## When this skill applies

- Running the benchmark for the first time and wanting to know what the numbers mean.
- Comparing warm-fallback against vector-only or full-history baselines.
- Swapping in real embeddings (OpenAI, HuggingFace) instead of the default synthetic ones.
- Tuning `warm_capacity`, `top_k`, `warm_hit_threshold`, or the latency cost model.
- Writing up results for a PR, blog post, or LangGraph community contribution.

## What the benchmark measures

`run_langgraph_benchmark` runs the same 12-turn synthetic workload against three retrieval strategies, all driven through the LangGraph store API:

| strategy | what it does |
|---|---|
| `full-history` | every prior turn is in the prompt every time (naive baseline, no retrieval) |
| `vector-only` | LangGraph's `InMemoryStore` with an embedding index — semantic search on every turn |
| `warm-fallback` | `WarmStore` queried first; if best score < `warm_hit_threshold`, fall back to the vector store |

For each turn, the harness records:

- `prompt_tokens` — total tokens of retrieved content fed to the model
- `end_to_end_ms` — synthetic latency (retrieval + prompt-build + simulated LLM time, scaled by tokens)
- `answer_correct` — whether retrieved memory covered the turn's `required_topics`
- `memory_precision_at_k` — fraction of retrieved items whose topic was actually required
- `warm_hit_rate`, `fallback_rate` — diagnostics for warm-fallback

The story the benchmark is designed to surface is **the tradeoff**, not "warm wins." Expect `full-history` to have the highest accuracy and highest tokens; `vector-only` to cut tokens but lose accuracy on weak embeddings; `warm-fallback` to ship the smallest prompts and eliminate ~half the vector-store calls. That tradeoff *is* the result.

## Recipe 1: Run with synthetic defaults (no API keys)

```bash
python3 scripts/run_langgraph_benchmark.py
```

This uses `DeterministicFakeEmbedding(size=64)` and `FakeListChatModel` — the same defaults the tests use, so results are reproducible across machines. Output goes to `reports/warm_memory_langgraph_benchmark.md` and a summary prints to stdout.

## Recipe 2: Run with real embeddings (real semantic ranking)

The benchmark accepts any LangChain `Embeddings`. The script understands two env vars out of the box:

```bash
# OpenAI
export WARM_BENCH_EMBEDDINGS=openai
export OPENAI_API_KEY=sk-...
python3 scripts/run_langgraph_benchmark.py

# HuggingFace (sentence-transformers/all-MiniLM-L6-v2 by default)
export WARM_BENCH_EMBEDDINGS=huggingface
python3 scripts/run_langgraph_benchmark.py
```

For anything else (Voyage, Cohere, Anthropic embeddings, a custom model), import directly:

```python
from langchain_voyageai import VoyageAIEmbeddings
from warm_memory.langgraph.benchmark import run_langgraph_benchmark

results = run_langgraph_benchmark(
    embeddings=VoyageAIEmbeddings(model="voyage-3"),
    report_path="reports/voyage_run.md",
)
```

## Recipe 3: Tune the config

```python
from warm_memory.langgraph.benchmark import (
    LangGraphBenchmarkConfig,
    run_langgraph_benchmark,
)

config = LangGraphBenchmarkConfig(
    warm_capacity=16,        # per-namespace warm buffer size
    top_k=5,                 # retrieved items per turn
    embedding_dims=384,      # must match your embeddings model
    warm_hit_threshold=0.5,  # raise -> more fallback; lower -> warm catches more
    long_term_latency_ms=8.0,
    llm_base_latency_ms=35.0,
    llm_latency_per_token_ms=0.12,
)
results = run_langgraph_benchmark(config=config, report_path="reports/tuned.md")
```

Three knobs that change the story most:

- **`warm_hit_threshold`**: how confident WarmStore must be to skip the fallback. Too low and you ship stale warm hits; too high and you defeat the warm tier and end up paying vector cost on every turn.
- **`warm_capacity`**: how much fits in the warm tier per namespace. Larger = more warm hits, but at some point you're just rebuilding the vector store in memory.
- **`top_k`**: items retrieved per turn. Drives prompt tokens linearly.

## Recipe 4: Interpret the report

The report (`reports/warm_memory_langgraph_benchmark.md`) ends with a summary table. The most useful columns:

- `warm_hit_rate` for `warm-fallback`: fraction of turns where the vector store was *not* queried. Treat this as "how much retrieval cost did the warm tier save."
- `avg_prompt_tokens`: directly proportional to LLM cost in real deployments.
- `answer_accuracy` vs. `memory_precision_at_k`: accuracy answers "did we retrieve the right thing," precision answers "did we retrieve too much."

A good headline for write-ups is the pair *(prompt-token reduction vs. full-history, accuracy delta vs. full-history)*. That's the honest tradeoff, not a single number.

## Recipe 5: Compare against a real workload

The default workload is `warm_memory.workload.default_workload()` — 12 deterministic turns. To benchmark against your own traces:

1. Build a list of `ScenarioTurn(turn_id, topic, query, required_topics)`. `required_topics` is the set of topics whose retrieval would constitute a "correct" answer.
2. Patch or replicate `_write_full_history_log` / `_run_vector_only` / `_run_warm_fallback` in `warm_memory/langgraph/benchmark.py` to take a custom `turns` list (currently hardcoded to `default_workload()`).
3. The metrics will be meaningful as long as your turns include enough cross-turn references (so retrieval actually matters).

For a real LLM-grading approach (no `required_topics` needed), call the model on each turn and have a judge model rate the response; this is a larger change and not currently in-tree.

## Common pitfalls

- **Embedding dims must match.** If you set `embedding_dims=384` in the config but pass `OpenAIEmbeddings()` (which is 1536), `InMemoryStore` rejects writes. Match the config to the model.
- **Synthetic embeddings are deterministic but not semantic.** `DeterministicFakeEmbedding` gives reproducible numbers, but it doesn't actually understand language. A 50% accuracy gap between `vector-only` (synthetic) and `vector-only` (real) is normal — that's why the headline numbers should be from a real-embedding run.
- **`warm-fallback` writes to both stores.** It mirrors every turn into the vector store so the fallback has something to find on a miss. Don't be surprised if `warm-fallback`'s `vector_only_fallback_rate` looks like 50% on the first run — that's the cold-start period where warm hasn't had time to fill.
- **The latency numbers are synthetic.** They come from a token-cost model (`llm_latency_per_token_ms × tokens + llm_base_latency_ms`). They reflect *relative* cost between strategies, not absolute wall-clock time of a real LLM call.

## Where to look in the repo

- `scripts/run_langgraph_benchmark.py` — entrypoint, env-var dispatch for real embeddings
- `warm_memory/langgraph/benchmark.py` — strategy implementations, config, report rendering
- `warm_memory/workload.py` — the synthetic workload
- `reports/warm_memory_langgraph_benchmark.md` — latest synthetic run
- `warm_memory/benchmark.py` + `scripts/run_benchmark.py` — the older, non-LangGraph benchmark (still useful for measuring the buffer itself in isolation)
