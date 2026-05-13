---
name: warmmemory-extend
description: Use this skill whenever the user wants to extend WarmMemory beyond the defaults — implementing a custom `ImportanceScorer` (BM25, reranker, hybrid lexical+semantic, role-aware), debugging surprising recall behavior (wrong items ranked first, expected items missing, capacity evicting unexpectedly), or hardening WarmStore for production use. Trigger on mentions of custom scorer, BM25, reranker, hybrid retrieval, recall debugging, "WarmMemory isn't finding X", per-role weighting, custom importance, or extending the warm buffer. Also trigger when the user reports the benchmark showing unexpected accuracy and wants to diagnose why.
---

# Extending and Debugging WarmMemory

WarmMemory's `ImportanceScorer` interface is the main extension point. Most behavioral questions ("why didn't it find X?", "the ranking looks wrong") trace back to the scorer or to namespace/capacity mistakes. This skill covers both: writing new scorers and debugging existing ones.

## When this skill applies

- Implementing a new ranking strategy (BM25, reranker model, hybrid, role-aware).
- Debugging unexpected recall: missing items, wrong order, low scores, empty results.
- Tuning capacity / threshold behavior when the benchmark numbers look off.
- Production hardening questions: thread safety, persistence, observability.

## Part 1 — Writing a custom ImportanceScorer

### The interface

```python
from typing import Any, Mapping
from warm_memory.scoring import ImportanceScorer

class MyScorer(ImportanceScorer):
    def score(self, query: str, row: Mapping[str, Any]) -> float:
        # row is a dict-like with keys: interaction_id, timestamp, role,
        # content, summary, tags, metadata. Return a float; higher = more relevant.
        ...
```

That's the whole contract. The buffer calls `score(query, row)` for every row when ranking, sorts descending, and returns the top-k. There's no required range — `[0, 1]`, `[-1, 1]`, raw inner products, all work. The only constraint is that *higher means more relevant*.

### Pattern 1: Hybrid lexical + semantic

A common production recipe: blend keyword overlap (cheap, recall-strong on exact terms) with semantic similarity (expensive, recall-strong on paraphrases).

```python
from warm_memory.scoring import KeywordImportanceScorer
from warm_memory.langgraph import EmbeddingsImportanceScorer

class HybridScorer(ImportanceScorer):
    def __init__(self, embeddings, lexical_weight: float = 0.3):
        self.lexical = KeywordImportanceScorer()
        self.semantic = EmbeddingsImportanceScorer(embeddings)
        self.lexical_weight = lexical_weight

    def score(self, query, row):
        return (
            self.lexical_weight * self.lexical.score(query, row)
            + (1 - self.lexical_weight) * self.semantic.score(query, row)
        )
```

`EmbeddingsImportanceScorer` already caches embeddings per content string, so repeated calls are cheap.

### Pattern 2: Reranker (cross-encoder)

Cross-encoders score `(query, doc)` jointly and are more accurate than bi-encoders, at higher per-call cost. The right pattern is **two-stage**: cheap first pass to get top-N candidates, expensive reranker to re-order them. WarmMemory doesn't ship two-stage out of the box, but you can layer it on at the application level:

```python
candidates = store.search(("alice",), query=q, limit=20)  # cheap first pass
reranked = sorted(
    candidates,
    key=lambda item: reranker.rerank(q, item.value["text"]),
    reverse=True,
)[:5]
```

Don't try to call a reranker from inside `score()` — it'll get called once per row in the buffer, which is wasteful. Use a wide first pass, then rerank the survivors.

### Pattern 3: Role-aware weighting

`KeywordImportanceScorer` already takes `role_weights`. For more elaborate per-role logic (e.g., assistant messages weighted higher for instruction-following questions):

```python
class RoleAwareScorer(ImportanceScorer):
    def __init__(self, base: ImportanceScorer, weights: dict[str, float]):
        self.base = base
        self.weights = weights

    def score(self, query, row):
        weight = self.weights.get(row.get("role", "user"), 1.0)
        return weight * self.base.score(query, row)
```

This decorator pattern keeps the base scorer's logic intact and stacks cleanly with other wrappers.

### Wiring a custom scorer into WarmStore

```python
from warm_memory.langgraph import WarmStore

store = WarmStore(scorer=MyScorer(), capacity=16)
```

The scorer is also passed down to every per-namespace buffer created lazily on first `put`, so all namespaces share the same scoring strategy. If you ever need *per-namespace* scorers, that's not a current feature — open an issue or subclass `WarmStore` and override `_buffer_for`.

## Part 2 — Debugging recall

Recall problems almost always come from one of four root causes. Diagnose in this order:

### 1. Namespace mismatch

`store.search(("alice",), ...)` only finds items in `("alice",)` and namespaces with that prefix. If you wrote to `("Alice",)` (capital A) or `("user-123",)` and search `("alice",)`, you'll see zero hits.

**Diagnostic:** `store.list_namespaces()`. If the namespace you expect isn't there, the writes went somewhere else.

### 2. Capacity eviction

`WarmStore(capacity=N)` keeps at most N items *per namespace*, evicting oldest by `interaction_id` (insertion order). If you wrote 50 items to `("alice",)` and capacity is 8, only the last 8 are findable.

**Diagnostic:** `store.size(("alice",))`. If it's `capacity` and you wrote more than that, you're seeing eviction.

### 3. The default scorer is keyword-only

`KeywordImportanceScorer` matches on whole tokens (case-insensitive, lowercased, alphanumeric + underscore). It does *not* understand synonyms, paraphrases, or morphology. "invoice" matches "invoice" but not "bill" or "invoices."

**Diagnostic:** rephrase your search query using exact words from the stored content. If that finds it, the scorer is the bottleneck. Swap to `EmbeddingsImportanceScorer` or a hybrid.

### 4. Empty content

If `value["text"]` is missing or empty, `_extract_search_text` (in `warm_memory/langgraph/store.py`) produces nothing to score against. The row exists (`get()` returns it) but `search(query=...)` won't surface it.

**Diagnostic:** `store.get(namespace, key).value` — confirm the value dict has searchable strings.

### Useful debugging snippet

```python
def debug_recall(store, namespace, query, limit=20):
    items = store.search(namespace, query=query, limit=limit)
    print(f"namespace={namespace} query={query!r}")
    print(f"  found {len(items)} items (size={store.size(namespace)})")
    for it in items:
        print(f"    score={it.score!r:>10} key={it.key} value={it.value}")
```

Running this with `limit=size` shows every item's score, which usually reveals whether ranking or filtering is the issue.

## Part 3 — Production considerations

WarmStore is purpose-built as an *in-process warm tier*. A few things to know before depending on it in production:

- **Not persistent.** Restart the process and all warm memory is gone. Pair with a persistent LangGraph store (Postgres) or your existing vector DB for long-term memory.
- **Not thread-safe.** The underlying pandas frame is mutated in place. If you need concurrent reads/writes from multiple threads, wrap calls in a `threading.Lock`. Async usage through `abatch` is fine because it just delegates to `asyncio.to_thread`, but parallel async tasks on the same store also need a lock.
- **No TTL.** `BaseStore` supports TTL; `WarmStore` doesn't implement it yet (`supports_ttl = False`). The capacity bound is the only eviction mechanism.
- **Embedding cache is unbounded.** `EmbeddingsImportanceScorer` caches embeddings by string. For long-lived processes with high content churn, periodically clear `scorer._cache` or implement an LRU.

For a contribution back to the LangGraph community, TTL support and a proper async lock would be the obvious next features.

## Where to look in the repo

- `warm_memory/scoring.py` — the `ImportanceScorer` ABC and `KeywordImportanceScorer`
- `warm_memory/langgraph/embeddings.py` — the embedding-based scorer with caching
- `warm_memory/langgraph/store.py` — search routing, namespace logic, eviction
- `warm_memory/buffer.py` — the underlying pandas buffer and `_evict_over_capacity`
- `tests/test_langgraph_store.py` — examples of correct ranking, filter, and eviction behavior
