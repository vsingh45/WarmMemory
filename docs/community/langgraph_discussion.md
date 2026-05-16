# Draft: LangGraph Discussions post

**Where to post:** https://github.com/langchain-ai/langgraph/discussions/new?category=show-and-tell

**Suggested category:** Show and tell

**Title:** `WarmStore — a capacity-bounded BaseStore that acts as a warm tier in front of vector memory`

---

Hi LangGraph team and community,

I built a small `BaseStore` implementation that targets a gap I kept hitting when building multi-turn agents: I wanted a **bounded, in-process "warm" memory tier** that sits in front of a vector store, without paying the round-trip cost of an embedding query on every turn.

Repo: https://github.com/vsingh45/WarmMemory
Install: `pip install warm-memory[langgraph]` (PyPI publish in progress — see repo for `pip install -e ".[langgraph]"` for now)

## What it is

`WarmStore` is a `langgraph.store.base.BaseStore` implementation with three design choices specific to the warm-tier use case:

1. **Per-namespace eviction.** Each top-level namespace (typically a user / session) gets its own bounded buffer. When namespace A overflows, namespace B's entries are untouched. This matches the "warm memory per user" intuition and avoids the noisy-neighbor problem you'd get from a global cap.
2. **Pluggable scorer.** Default is a keyword/cosine `ImportanceScorer`, but `EmbeddingsImportanceScorer(your_embeddings)` lets you bring any LangChain `Embeddings` (OpenAI, HuggingFace, Voyage, etc.). The scorer caches per content string.
3. **Full filter-operator support.** `$eq`, `$ne`, `$gt`, `$gte`, `$lt`, `$lte` plus prefix/suffix/max_depth namespace listing, batch + abatch, etc.

22 conformance tests cover the BaseStore contract; the package is opt-in via a `[langgraph]` extra so the core stays pandas-only.

## Why I think this is useful

The headline pattern is **WarmStore in front of an `InMemoryStore` (or your real vector DB)**. The benchmark in the repo runs three strategies through the BaseStore API:

| strategy | avg prompt tokens | answer accuracy | warm-hit rate |
|---|---|---|---|
| `full-history` | 52.0 | 0.583 | — |
| `vector-only` (`InMemoryStore` + index) | 35.4 | 0.417 | — |
| `warm-fallback` (`WarmStore` → vector) | **35.3** | 0.500 | **0.50** |

On this 12-turn synthetic workload, the warm tier eliminates ~50% of vector-store calls and ships the smallest prompt while beating `vector-only` on accuracy. The synthetic workload obviously isn't the last word — the next milestone is running it against real agent traces with real embeddings. The benchmark is set up to take `WARM_BENCH_EMBEDDINGS=openai` (or any LangChain `Embeddings` programmatically) so anyone reading this can plug their own model in and reproduce.

## Quick example

```python
from langchain_anthropic import ChatAnthropic
from langchain_openai import OpenAIEmbeddings
from warm_memory.langgraph import (
    WarmStore,
    EmbeddingsImportanceScorer,
    build_warm_memory_agent,
)

store = WarmStore(
    capacity=16,
    scorer=EmbeddingsImportanceScorer(OpenAIEmbeddings()),
)
agent = build_warm_memory_agent(
    model=ChatAnthropic(model="claude-opus-4-7"),
    store=store,
)
agent.invoke({"query": "Where's my invoice?", "namespace": ("alice",)})
```

`build_warm_memory_agent` is a pre-built graph (`memory_lookup → respond → memory_write`) for the common case; the underlying `WarmStore` is a plain `BaseStore` so it drops into any LangGraph graph you already have.

## What I'd love feedback on

1. **Cookbook fit.** Would the LangGraph docs team be open to a cookbook entry / example showing this two-tier pattern? I'm happy to send a PR to `langchain-ai/langgraph` if so.
2. **Third-party stores list.** Is there a canonical place to register third-party `BaseStore` implementations? I noticed there isn't a single index for these yet, and I think the ecosystem would benefit from one.
3. **API ergonomics.** Anything in the `WarmStore` surface that feels off vs. LangGraph conventions? I tried to mirror `InMemoryStore`'s shape closely, but a fresh pair of eyes would help.

Code, tests, benchmark report, and Claude Code skills for working with it all live in the repo. Happy to expand on any part, take feedback, and contribute back upstream.

— Vivek
