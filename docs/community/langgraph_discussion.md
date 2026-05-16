# Draft: LangGraph Proposal Issue

**Where to post:** https://github.com/langchain-ai/langgraph/issues/new
**Title:** `Proposal: Warm Memory Implementation`
**Suggested labels:** `enhancement`, `discussion`

> The maintainer guidance for this kind of contribution is to **open an issue
> titled "Proposal: Warm Memory Implementation"** with the architectural
> approach before sending a PR. This draft follows that exact path.

---

# Proposal: Warm Memory Implementation

Hi LangGraph team,

I'd like to propose a `BaseStore` implementation that adds **per-namespace
capacity-bounded warm memory** in front of a vector or durable store. Before
opening any PR I'm following the contribution guidance and posting this as
an issue so the abstraction framing can be reviewed.

**Repo:** https://github.com/vsingh45/WarmMemory
**Package:** `warm-memory[langgraph]` (Python 3.11+, MIT licence)
**Full proposal document** (with the four required sections — Abstraction /
Usage Pattern / Performance & Scaling / Integration with Existing Tools):
[`docs/community/proposal.md`](https://github.com/vsingh45/WarmMemory/blob/main/docs/community/proposal.md)

## TL;DR for triage

1. **Abstraction:** `BaseStore` implementation. **Not** a `Checkpoint`. Not a
   `State` extension. Implements `batch` / `abatch` and conforms to the
   standard filter-operator dialect.
2. **Novel choice:** per-namespace capacity-bounded eviction. Each top-level
   namespace gets its own bounded warm buffer; A's writes never evict B's
   memory. Bounds total memory at `O(namespaces × capacity)`.
3. **Use case:** warm tier in front of a vector store (`InMemoryStore`,
   `PostgresStore`, your own). On a synthetic 12-turn workload this
   eliminates ~50% of vector-store retrievals and ships the smallest prompt
   while maintaining accuracy between `vector-only` and `full-history`.
4. **Integration:** orthogonal to `langgraph-checkpoint*`. Mirrors the
   `langgraph-checkpoint-postgres` packaging conventions if maintainers
   prefer a separate `langgraph-store-warm` distribution.

## Minimal reproducible example

Runs with **no API keys** — `FakeListChatModel` + the default
`KeywordImportanceScorer`:

[`examples/minimal_langgraph_warm_memory.py`](https://github.com/vsingh45/WarmMemory/blob/main/examples/minimal_langgraph_warm_memory.py)

```python
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from warm_memory.langgraph import WarmStore, build_warm_memory_agent

store = WarmStore(capacity=8)
agent = build_warm_memory_agent(
    model=FakeListChatModel(responses=[
        "Noted: you prefer concise answers.",
        "Yes, you asked for concise answers earlier.",
    ]),
    store=store,
)

agent.invoke({"query": "I prefer concise answers.", "namespace": ("alice",)})
result = agent.invoke({
    "query": "What response style did I ask for?",
    "namespace": ("alice",),
})
print(result["recalled"])
# [{'key': 'exchange-1', 'score': 0.55..., 'value': {'user': '...', 'assistant': '...'}}]
```

The package ships 28 tests (20 of which are `BaseStore` conformance for
`WarmStore`), CI on Python 3.11 / 3.12 / 3.13, and a comparative benchmark
in the repo.

## Benchmark headline (deterministic synthetic, 12 turns)

| strategy | avg prompt tokens | answer accuracy | warm-hit rate |
|---|---|---|---|
| `full-history` | 52.0 | 0.583 | — |
| `vector-only` (InMemoryStore + index) | 35.4 | 0.417 | — |
| `warm-fallback` (WarmStore → vector) | **35.3** | 0.500 | **0.50** |

The synthetic benchmark is best understood as a *contract test* for the
two-tier pattern. Validating against real agent traces with real embeddings
is the next milestone and is explicitly open work.

## What I'm asking from maintainers

Per the contribution guidance, I'd love feedback on:

1. **Is `BaseStore` the right abstraction?** (Versus a Checkpointer or a
   `State` extension — I argue it is in the proposal but happy to be
   corrected.)
2. **Does per-namespace eviction belong in a community store**, or does it
   generalize enough that LangGraph would want a built-in policy hook on
   `BaseStore`?
3. **Preferred distribution shape:** stay as a third-party package
   (`warm-memory[langgraph]`), or factor out a focused
   `langgraph-store-warm` distribution mirroring
   `langgraph-checkpoint-postgres`?
4. **Any additional tests or benchmarks** you'd want to see before
   considering a docs link-out or adoption?

Once the abstraction is settled I'm happy to open a draft PR (docs first,
code second) for whichever path you steer toward.

Thanks for the clear contribution guidance — it made shaping this proposal
much easier.

— Vivek
