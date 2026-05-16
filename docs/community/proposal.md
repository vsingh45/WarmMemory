# Proposal: Warm Memory Implementation

> This is the canonical proposal document for submitting `warm-memory` to the
> LangGraph community. It follows the four-section structure requested in the
> LangGraph contribution guidance.

**Repo:** https://github.com/vsingh45/WarmMemory
**Package:** `warm-memory[langgraph]` (Python 3.11+, MIT)
**Status:** v0.2.0, 28 passing tests, CI on 3.11 / 3.12 / 3.13.

---

## 1. Define the abstraction

WarmStore is a **`langgraph.store.base.BaseStore` implementation**. It is not
a `Checkpoint` implementation and does not extend the `State` schema.

Concretely:

- **What it is:** a `BaseStore` subclass implementing `batch` and `abatch`, with
  the standard derived API (`get`, `put`, `search`, `delete`, `list_namespaces`,
  sync and async). Conforms to LangGraph's filter-operator dialect
  (`$eq`, `$ne`, `$gt`, `$gte`, `$lt`, `$lte`) and namespace-listing semantics
  (prefix / suffix / `max_depth`).
- **What it is not:** a checkpointer. It does not persist `StateGraph`
  execution state, channel values, or thread/checkpoint metadata. Checkpointing
  remains the responsibility of `BaseCheckpointSaver` implementations
  (`MemorySaver`, `PostgresSaver`, etc.) and is orthogonal to WarmStore.
- **Why a Store, not a Checkpointer:** the use case is *cross-thread, persistent,
  user-scoped memory* (preferences, facts, prior exchanges) — exactly what
  `BaseStore` was added to model. Checkpointers serve *within-thread* state
  recovery, which has different lifetime, granularity, and access patterns.

The novel choice within the `BaseStore` design space is **per-namespace
capacity-bounded eviction**. Each top-level namespace gets its own bounded
warm buffer. Writes that exceed `capacity` evict the oldest entries *within
that namespace only*. This eliminates the cross-tenant noisy-neighbor problem
of a global cap while still bounding total memory at `O(namespaces × capacity)`.

## 2. Usage pattern

The minimal reproducible example lives at
[`examples/minimal_langgraph_warm_memory.py`](../../examples/minimal_langgraph_warm_memory.py).
It runs with no API keys (`FakeListChatModel` + `KeywordImportanceScorer`) and
demonstrates the recall pattern inside a real LangGraph `StateGraph`:

```python
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from warm_memory.langgraph import WarmStore, build_warm_memory_agent

store = WarmStore(capacity=8)
agent = build_warm_memory_agent(
    model=FakeListChatModel(responses=["...", "..."]),
    store=store,
)

# Turn 1 — fact is captured into warm memory
agent.invoke({"query": "I prefer concise answers.", "namespace": ("alice",)})

# Turn 2 — the prior turn is recalled from the warm store and inserted
# into the system prompt before the model is invoked
result = agent.invoke({
    "query": "What response style did I ask for?",
    "namespace": ("alice",),
})
print(result["recalled"])  # [{'key': 'exchange-1', 'score': ..., 'value': {...}}]
```

`build_warm_memory_agent` compiles to a three-node graph
(`memory_lookup → respond → memory_write`). Users who want their own graph
shape can drop `WarmStore` into any node directly; it has no `StateGraph`
dependencies beyond `BaseStore`.

For semantic ranking instead of keyword overlap, swap the scorer:

```python
from langchain_openai import OpenAIEmbeddings
from warm_memory.langgraph import EmbeddingsImportanceScorer

store = WarmStore(scorer=EmbeddingsImportanceScorer(OpenAIEmbeddings()))
```

Any LangChain `Embeddings` implementation works (OpenAI, Voyage, HuggingFace,
Cohere). Embeddings are cached by content string to avoid re-embedding on
re-reads.

## 3. Performance and scaling

### Memory footprint

- **Per namespace:** `O(capacity)` items. Each item is one row in a pandas
  DataFrame: `interaction_id`, `timestamp`, `role`, `content` (extracted from
  the user's `value` dict for search), `metadata` (which carries the full
  `value` dict, `created_at`, `updated_at`).
- **Total:** `O(namespaces × capacity)`. For 10k users × `capacity=32`, that's
  roughly 320k rows. Profiling on a single-laptop run shows ~1.5 KB per row in
  the keyword-scorer case, putting the upper bound at ~500 MB in a worst-case
  fully-utilized 10k-user deployment.
- **With embeddings:** add `dims × 4 bytes` per row for the cached vector plus
  `dims × 4 bytes` per unique query in the scorer's cache. For
  `dims=1536` (OpenAI), that's ~6 KB per row of vector cache.

### Retrieval latency

- **Single-namespace search:** `O(capacity)` per turn. The scorer is called
  once per row. With `KeywordImportanceScorer` this is microseconds for
  reasonable `capacity` (e.g., 32). With `EmbeddingsImportanceScorer` the
  query embed is the dominant cost; per-row scoring is a dot product of
  cached vectors.
- **Prefix search:** `O(matching_namespaces × capacity)`. A search at the
  root prefix `()` walks every namespace; deeper prefixes scope it down.
- **Two-tier hot/cold pattern:** the load-bearing use case. Put `WarmStore`
  in front of a vector store and only consult the vector store on misses
  (score below threshold). On the synthetic benchmark this eliminates ~50%
  of vector-store calls and ships the smallest prompt while maintaining
  accuracy intermediate between vector-only and full-history. See the
  benchmark below.

### Integration with LangGraph checkpoints

Orthogonal subsystems. A typical agent uses both:

```python
from langgraph.checkpoint.postgres import PostgresSaver
from warm_memory.langgraph import WarmStore

checkpointer = PostgresSaver.from_conn_string(...)  # within-thread state
warm = WarmStore(capacity=32)                       # cross-thread memory

graph = StateGraph(...).compile(
    checkpointer=checkpointer,
    store=warm,  # passed through to nodes as the standard `store` param
)
```

WarmStore is constructed in-process and is not durable across restarts —
**by design**. It is a warm tier, not a persistent store. The companion
recommendation is to mirror puts to a durable store (your vector DB, or
`PostgresStore` if you want LangGraph-native long-term memory) and rely on
WarmStore only as a low-latency cache.

### Benchmark (deterministic synthetic workload, 12 turns)

Run with `python scripts/run_langgraph_benchmark.py` (synthetic) or
`WARM_BENCH_EMBEDDINGS=openai OPENAI_API_KEY=... python scripts/run_langgraph_benchmark.py`
(real embeddings).

| strategy | avg prompt tokens | answer accuracy | warm-hit rate |
|---|---|---|---|
| `full-history` (every turn in prompt) | 52.0 | 0.583 | — |
| `vector-only` (`InMemoryStore` + index) | 35.4 | 0.417 | — |
| `warm-fallback` (WarmStore → vector) | **35.3** | 0.500 | **0.50** |

The benchmark is synthetic and is best understood as a *contract test* for the
two-tier pattern, not a production claim. Validating on real agent traces with
real embeddings is the next milestone and is explicitly called out as open
work.

## 4. Integration with existing tools

### Alignment with `langgraph-checkpoint-postgres` conventions

The existing `langgraph-checkpoint-postgres` package establishes the
convention for third-party storage backends:

- **Package name:** `langgraph-{component}-{backend}` (e.g.,
  `langgraph-checkpoint-postgres`). For inclusion in the monorepo, the
  parallel name would be **`langgraph-store-warm`** under
  `libs/store-warm/`. Today the integration ships as a submodule of
  `warm-memory` (`warm-memory[langgraph]`); if maintainers prefer a focused
  distribution name, factoring out is trivial and we're happy to do so.
- **Dependency pinning:** `langgraph-checkpoint-postgres` pins
  `langgraph-checkpoint>=4.1.0,<5.0.0`. We currently pin
  `langgraph>=1.0`, `langchain-core>=1.0`. Happy to follow whatever range
  policy maintainers prefer.
- **Conformance tests:** the repo ships `libs/checkpoint-conformance`, a
  shared contract suite that checkpoint backends must pass. If a parallel
  `store-conformance` suite exists (or maintainers would like one),
  WarmStore would be run against it. Today we ship 20 internal conformance
  tests covering: put-get round-trip, update preserving `created_at`,
  delete via `put(None)` and `delete()`, filter operators including
  unknown-operator errors, prefix/suffix/max_depth namespace listing,
  query plus filter, limit and offset pagination, per-namespace eviction
  isolation, sync `batch` op ordering, and the async path.
- **`store` parameter wiring:** WarmStore is passed to
  `StateGraph.compile(store=...)` and accessed by nodes through the
  standard `config["configurable"]["__pregel_store"]` resolution. No
  special integration glue is required.

### Doesn't conflict with

- `langgraph-checkpoint` — different abstraction (Checkpointer vs. Store).
- `InMemoryStore` — complementary; WarmStore is the *bounded, per-namespace,
  in-process* counterpart, intended to layer in front of `InMemoryStore` or
  any other `BaseStore` for a warm/cold split.
- `PostgresStore` (when used) — same pattern: WarmStore in front,
  `PostgresStore` as the durable tier.

## How to evaluate this proposal

Suggested checklist for reviewers:

- [ ] Is the abstraction (BaseStore implementation, **not** a Checkpointer)
      the right framing?
- [ ] Does per-namespace eviction belong in a community store, or does it
      generalize enough that LangGraph would want a built-in policy hook on
      `BaseStore` itself?
- [ ] Should the distribution be `warm-memory[langgraph]` (as today) or a
      focused `langgraph-store-warm` package (mirroring
      `langgraph-checkpoint-postgres`)?
- [ ] Would the LangGraph docs benefit from a third-party-stores index page,
      so this and future community stores are discoverable? (See
      [`langgraph_issue_third_party_stores.md`](langgraph_issue_third_party_stores.md).)
- [ ] What additional tests / benchmarks / docs would maintainers like to see
      before considering adoption or a docs link-out?

## Open work the proposer commits to

- Real-trace benchmarks against an agent of the maintainers' choice.
- TTL support on the store (`supports_ttl = True`) once a design is agreed.
- Conformance against any future `store-conformance` suite.
- Factoring out to `langgraph-store-warm` if maintainers prefer that
  distribution shape.

---

**Asking for:** initial review of the abstraction framing, then guidance on
whether to (a) submit a docs-PR adding a third-party-stores section linking
to the package, (b) submit a draft code-PR factoring out
`langgraph-store-warm` into the monorepo, or (c) stay as a clearly-labeled
third-party package and link from the LangGraph community resources.
