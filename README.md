# WarmMemory

[![PyPI](https://img.shields.io/pypi/v/warm-memory.svg)](https://pypi.org/project/warm-memory/)
[![CI](https://github.com/vsingh45/WarmMemory/actions/workflows/ci.yml/badge.svg)](https://github.com/vsingh45/WarmMemory/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![LangGraph](https://img.shields.io/badge/LangGraph-BaseStore-1f6feb)](https://langchain-ai.github.io/langgraph/)

WarmMemory is a Python package for short-term memory management in LLM agents.
It adds a small in-process working-memory layer that keeps the most recent or most
relevant interactions close to the agent, reducing repeated retrieval work and
helping control prompt growth.

The repository provides:

- a reusable Python package for warm-memory buffering,
- a decorator for automatic interaction capture,
- a pluggable importance scoring interface,
- a deterministic benchmark for recency vs relevance vs fallback memory policies,
- a LangGraph `BaseStore` integration with per-namespace eviction, embeddings-based
  ranking, and a pre-built agent,
- HTML documentation for architecture and usage.

## Why This Exists

Many agent systems use one of two expensive patterns:

- they keep appending conversation history to the prompt,
- or they query long-term memory on nearly every turn.

Both increase latency and cost. WarmMemory introduces a hot path:

- keep a small working set in RAM,
- retrieve from that working set first,
- fall back to longer-term retrieval only when needed,
- and send only a compact context window to the model.

## Core Ideas

### 1. Sliding-Window Memory

The system can keep the last `N` interactions using `recent(k)`.

### 2. Relevance-Aware Memory

Instead of only keeping the latest messages, the system can rank rows against the
current query using `relevant(query, k)` and compact the active working set with
`retain_relevant(query, k)`.

### 3. Automatic Agent Capture

The `@remember_interaction` decorator records agent inputs and outputs without forcing
changes into the core agent logic.

### 4. Two-Tier Memory Architecture

The benchmark models a practical split:

- warm memory for fast in-process access,
- long-term memory for slower fallback retrieval.

## Repository Layout

- `warm_memory/`: package source code
- `warm_memory/buffer.py`: Pandas-backed warm-memory store
- `warm_memory/scoring.py`: scoring interface and default heuristic scorer
- `warm_memory/decorators.py`: function decorator for interaction capture
- `warm_memory/benchmark.py`: deterministic benchmark harness
- `warm_memory/workload.py`: synthetic workload for evaluation
- `warm_memory/langgraph/`: LangGraph integration (optional extra)
  - `store.py`: `WarmStore(BaseStore)` with per-namespace eviction
  - `embeddings.py`: bring-your-own embeddings scorer
  - `agent.py`: pre-built `build_warm_memory_agent` graph
  - `benchmark.py`: full-history vs vector-only vs warm-fallback benchmark
- `examples/langgraph_warm_agent.py`: runnable LangGraph agent example
- `scripts/run_benchmark.py`: legacy benchmark entrypoint
- `scripts/run_langgraph_benchmark.py`: LangGraph-based benchmark entrypoint
- `reports/warm_memory_benchmark.md`: legacy benchmark output
- `reports/warm_memory_langgraph_benchmark.md`: LangGraph benchmark output
- `docs/warm_memory_guide.html`: public-facing HTML documentation
- `tests/`: unit tests

## Installation

```bash
pip install warm-memory
# or with the LangGraph integration:
pip install warm-memory[langgraph]
```

Or install from source for development:

```bash
python3 -m pip install -e ".[langgraph]"
```

## Quick Start

```python
from warm_memory import WarmMemoryBuffer, remember_interaction

memory = WarmMemoryBuffer(capacity=8)

@remember_interaction(memory)
def agent(prompt: str) -> str:
    if "billing" in prompt.lower():
        return "Your invoice is available in the billing portal."
    return f"Echo: {prompt}"

agent("How do I reset my password?")
agent("Where is my billing invoice?")

recent_rows = memory.recent(4)
relevant_rows = memory.relevant("invoice", limit=2)
memory.retain_relevant("invoice", limit=4)
```

## Example Usage Pattern

Use WarmMemory in front of a larger memory system:

1. Receive a new user query.
2. Search the warm buffer first.
3. If warm memory is sufficient, build a compact prompt from those rows.
4. If warm memory is weak, fall back to long-term retrieval.
5. Write the new interaction back into warm memory.

This pattern is useful for:

- coding agents,
- research assistants,
- task-oriented copilots,
- customer support agents,
- and any multi-turn system with repeated local context.

## Benchmark

The repository includes a deterministic benchmark that compares:

- `recency`: always use the latest warm-memory rows,
- `relevance`: rank and retain the top relevant warm-memory rows,
- `fallback`: use warm relevance first, then long-term retrieval on misses.

Run it with:

```bash
python3 scripts/run_benchmark.py
```

This writes a report to `reports/warm_memory_benchmark.md`.

On the current synthetic workload, the tradeoff looks like this:

- `recency` is the fastest policy,
- `fallback` is the most accurate policy,
- `relevance` sits between the two and provides a cleaner hot working set.

The benchmark is designed to surface that tradeoff rather than name a single
winner: each policy occupies a different point on the latency-accuracy curve.

## Documentation

- HTML guide: `docs/warm_memory_guide.html`
- Benchmark report: `reports/warm_memory_benchmark.md`
- Architecture diagram: [`docs/warm_memory_architecture.drawio.svg`](docs/warm_memory_architecture.drawio.svg) (animated, edits in app.diagrams.net)
- TwoTierStore design: [`docs/design/two_tier_store.md`](docs/design/two_tier_store.md) + [diagram](docs/design/two_tier_store.drawio.svg)

The HTML guide explains:

- how the architecture works,
- where latency is saved,
- how to use the package,
- and how the components fit together.

## Architecture

![WarmMemory architecture](https://raw.githubusercontent.com/vsingh45/WarmMemory/main/docs/warm_memory_architecture.drawio.svg)

The dashed gold boundary is **`TwoTierStore`** — the v0.3.0 `BaseStore`
wrapper that owns the warm-first/durable-fallback logic. From the agent's
perspective, it's a single `BaseStore`; the read fan-out, threshold check,
fallback, and concurrent write mirror all happen inside the boundary.

The pipeline:

1. **Agent Runtime** calls `store.search(...)` and `store.aput(...)` once per
   turn. No orchestration code — the wrapper handles everything below.
2. Inside the boundary, the search hits **WarmMemory** (the in-process
   working set) and runs through the **Retrieval Ranker**
   (`KeywordImportanceScorer` by default; swap in
   `EmbeddingsImportanceScorer` for semantic ranking).
3. **Warm Hit?** checks the best score against the configured threshold.
4. **Green path (warm hit):** results flow to **Prompt Builder**, which
   injects only the top-K rows into the system prompt before invoking the
   **LLM**. The durable tier is never touched.
5. **Orange path (warm miss):** the query falls through to **Long-Term
   Memory** (LangGraph's `InMemoryStore` with an embedding index,
   `PostgresStore`, or any `BaseStore`) and the LLM consumes those results
   as fallback. The result also populates warm on the way back.
6. **Write-back:** `store.aput(...)` returns to TwoTierStore, which fans
   out **concurrently via `asyncio.gather`** to both warm and durable so
   total write latency is `max(warm, durable)` instead of the sum.
   "capture output (decorator)" routes the LLM response back through the
   agent's `memory_write` node.

On the synthetic benchmark, ~50% of turns take the green path, eliminating
that many durable-store calls.

The diagram ships in two paired formats:

- **[`docs/warm_memory_architecture.drawio.svg`](docs/warm_memory_architecture.drawio.svg)** —
  the rendered SVG that GitHub displays inline. The decision arrows flow
  ("marching ants" SMIL animation) so the hot/cold paths read at a glance.
  Open the file directly in a browser to see the animation; GitHub also
  renders the animation when displaying the SVG.
- **[`docs/warm_memory_architecture.drawio`](docs/warm_memory_architecture.drawio)** —
  the editable mxgraph source. Open at [diagrams.net](https://app.diagrams.net)
  (File → Open from device) to edit; re-export the SVG when done.

The `.drawio.svg` also embeds the mxgraph XML in its `content` attribute, so
either file round-trips through the editor — they're kept in sync from the
same generator script.

For a richer narrated walkthrough, open
[`docs/warm_memory_guide.html`](docs/warm_memory_guide.html) locally or publish
it with GitHub Pages.

## Development

Run tests:

```bash
python3 -m unittest discover -s tests -v
```

## LangGraph Integration

WarmMemory ships an optional `warm_memory.langgraph` module that plugs directly
into the LangGraph ecosystem. Install with the extra:

```bash
pip install warm-memory[langgraph]
```

### Drop-in `BaseStore`

`WarmStore` implements LangGraph's `BaseStore` interface with **per-namespace
warm buffers** — each namespace gets its own bounded buffer, so multi-tenant
agents don't evict each other's memory.

```python
from warm_memory.langgraph import WarmStore

store = WarmStore(capacity=16)
store.put(("alice",), "preferences", {"text": "wants concise answers"})
store.put(("alice",), "billing", {"text": "invoice overdue", "topic": "billing"})

# query-based recall (keyword scorer by default)
hits = store.search(("alice",), query="how do I pay my invoice?")

# filter operators: $eq, $ne, $gt, $gte, $lt, $lte
billing = store.search(("alice",), filter={"topic": "billing"})
```

### Bring-your-own embeddings

Swap the default keyword scorer for any LangChain `Embeddings`:

```python
from langchain_openai import OpenAIEmbeddings
from warm_memory.langgraph import EmbeddingsImportanceScorer, WarmStore

scorer = EmbeddingsImportanceScorer(OpenAIEmbeddings())
store = WarmStore(scorer=scorer)
```

Works with any LangChain embeddings provider — OpenAI, HuggingFace, Voyage,
Anthropic — or `DeterministicFakeEmbedding` for tests.

### Two-tier deployment (`TwoTierStore`)

For production, pair `WarmStore` with a durable backing tier
(`PostgresStore`, your vector DB, etc.) through `TwoTierStore` so the agent
code can use one `BaseStore` and the wrapper handles warm-first reads,
fallback on miss, and write-through to both tiers:

```python
from langgraph.store.memory import InMemoryStore
from warm_memory.langgraph import WarmStore, TwoTierStore

warm = WarmStore(capacity=32)
durable = InMemoryStore(index={"embed": my_embeddings, "dims": 1536, "fields": ["text"]})
# Or: durable = PostgresStore.from_conn_string(DB_URI)

store = TwoTierStore(warm=warm, durable=durable, warm_hit_threshold=0.34)

# Use `store` like any single BaseStore — TwoTierStore handles the rest.
graph = StateGraph(...).compile(store=store)
```

Key properties:

- **Reads:** warm first; on miss (or score below `warm_hit_threshold`), fall
  through to durable and populate warm with the result.
- **Async writes** (`aput`, `abatch`): fan out **concurrently** via
  `asyncio.gather` — total latency is `max(warm_put, durable_put)` instead
  of the sum. The tests assert this with a wall-clock timing check.
- **Sync writes** (`put`, `batch`): sequential. Use the async API in
  production for parallel writes.
- **Error semantics:** durable success is required (errors propagate). Warm
  failures are tolerated by default (`fail_on_warm_error=False`) — the data
  is safe in durable and warm rehydrates on the next read miss.
- **Restart resilience:** on redeploy/restart, the warm cache is empty but
  the durable tier is intact. First reads miss warm → hit durable →
  populate warm. Users perceive no data loss; cache rehydrates in minutes.

See [`docs/design/two_tier_store.md`](docs/design/two_tier_store.md) for the
full design with the architecture diagram, per-operation contract, and
configuration knobs.

### Pre-built agent

`build_warm_memory_agent` returns a compiled LangGraph that reads warm memory
before responding and writes the new exchange back on the way out:

```python
from warm_memory.langgraph import WarmStore, build_warm_memory_agent

store = WarmStore(capacity=8)
agent = build_warm_memory_agent(model=my_chat_model, store=store)
agent.invoke({"query": "Where's my invoice?", "namespace": ("alice",)})
```

A runnable example using `FakeListChatModel` (no API keys) lives at
`examples/langgraph_warm_agent.py`.

### Comparative benchmark

`scripts/run_langgraph_benchmark.py` compares three retrieval strategies through
the LangGraph store API:

- `full-history`: every prior turn in the prompt (naive baseline)
- `vector-only`: LangGraph's `InMemoryStore` with an embedding index
- `warm-fallback`: `WarmStore` in front of the vector store

```bash
python3 scripts/run_langgraph_benchmark.py
```

This writes `reports/warm_memory_langgraph_benchmark.md`. Run it with synthetic
embeddings by default; set `WARM_BENCH_EMBEDDINGS=openai` (and `OPENAI_API_KEY`)
to compare against real semantic search.

## Roadmap

- ~~add an embedding-based or reranker-based importance scorer~~ (done via
  `EmbeddingsImportanceScorer`)
- ~~compare against vector-store-first baselines~~ (done via
  `warm-fallback` strategy in the LangGraph benchmark)
- benchmark against real agent traces instead of only synthetic workloads
- record actual model latency and token usage from a live LLM pipeline
- add charts and experiment summaries for publication-style reporting
- TTL support for the LangGraph `BaseStore`
- ~~publish `warm-memory` to PyPI~~ ([live at v0.2.1](https://pypi.org/project/warm-memory/))
- propose inclusion in LangGraph's third-party store list (LangChain Forum
  proposal in flight)

## License

This project is released under the MIT License. See `LICENSE`.

