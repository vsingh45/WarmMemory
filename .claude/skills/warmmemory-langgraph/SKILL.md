---
name: warmmemory-langgraph
description: Use this skill whenever the user wants to wire WarmMemory's WarmStore into a LangGraph agent, add a warm/hot memory tier in front of a vector store, give a multi-tenant LangGraph agent per-user short-term memory, or use the prebuilt `build_warm_memory_agent` graph. Trigger on mentions of WarmStore, WarmMemoryBuffer, warm memory, warm tier, hot memory layer, memory for LangGraph agent, two-tier memory, per-user memory, or recalling previous turns in a LangGraph workflow — even when the user doesn't explicitly say "WarmMemory." Also trigger when the user is building a LangGraph agent and asks how to reduce repeated retrieval, control prompt growth, or keep recent interactions close to the agent.
---

# WarmMemory + LangGraph Integration

WarmMemory exposes its short-term memory layer to the LangGraph ecosystem through `warm_memory.langgraph`. This skill gets you from "I have a LangGraph agent" to "my agent has bounded per-user warm memory backed by a real LangGraph BaseStore" in minutes.

## When this skill applies

Use it when the user is doing any of the following:

- Building or modifying a LangGraph agent that needs short-term memory.
- Looking for a `BaseStore` implementation that bounds memory per user/session.
- Adding a "warm" tier in front of an existing vector store to cut retrieval cost.
- Wiring `build_warm_memory_agent` into an application.
- Asking how WarmMemory differs from LangGraph's `InMemoryStore` (the answer: capacity-bounded per-namespace eviction, plus a pluggable scorer).

## Mental model

WarmMemory's LangGraph integration is three things glued together:

1. **`WarmStore(BaseStore)`** — a LangGraph store where each top-level namespace gets its own bounded warm buffer. Writes that exceed `capacity` evict the oldest entries within that namespace only. Other namespaces are untouched.
2. **`ImportanceScorer`** — the strategy that ranks rows for a query. Default is keyword cosine; swap in `EmbeddingsImportanceScorer(your_embeddings)` for semantic search.
3. **`build_warm_memory_agent`** — a compiled LangGraph that does `memory_lookup → respond → memory_write` around any LangChain chat model. Use it as-is, or copy the pattern into your own graph.

The whole package is opt-in via `pip install WarmMemory[langgraph]` — core WarmMemory stays pandas-only.

## Recipe 1: Drop WarmStore into an existing LangGraph agent

If the user already has a `StateGraph` or `create_react_agent` setup, the minimal change is to add a node that searches `WarmStore` before the LLM call and a node that writes after. WarmStore conforms to `BaseStore`, so all standard ops work.

```python
from warm_memory.langgraph import WarmStore

store = WarmStore(capacity=16)

# Reading — query-based recall
hits = store.search(("alice",), query="how do I pay my invoice?", limit=5)
for h in hits:
    print(h.key, h.score, h.value)

# Reading — exact filter
billing = store.search(("alice",), filter={"topic": "billing"})

# Reading — operator filter ($eq, $ne, $gt, $gte, $lt, $lte)
high_priority = store.search(("alice",), filter={"priority": {"$gte": 3}})

# Writing
store.put(("alice",), "invoice-march", {"text": "March invoice overdue", "topic": "billing"})

# Async API also exists: aget, aput, asearch, abatch
```

Namespaces are tuples of strings, the standard LangGraph convention. The first element is typically a user/tenant id; deeper levels organize sub-collections (`("alice", "private")`, `("alice", "preferences")`).

## Recipe 2: Use the prebuilt agent

For users who just want "an agent with warm memory" without wiring nodes themselves:

```python
from langchain_anthropic import ChatAnthropic  # or any LangChain chat model
from warm_memory.langgraph import WarmStore, build_warm_memory_agent

model = ChatAnthropic(model="claude-opus-4-7", temperature=0)
store = WarmStore(capacity=8)
agent = build_warm_memory_agent(model=model, store=store)

result = agent.invoke({"query": "Where's my invoice?", "namespace": ("alice",)})
print(result["response"])
print(result["recalled"])  # list of {key, value, score} dicts pulled from warm memory
```

The agent compiles to a three-node `StateGraph`:
- `memory_lookup` — searches `store` for `state["query"]` within `state["namespace"]`
- `respond` — calls the model with a system prompt that includes the recalled rows
- `memory_write` — writes the new (query, response) pair back as `exchange-N`

If the user wants to customize the system prompt, recall limit, or default namespace, pass `system_prompt=`, `recall_limit=`, or `namespace_default=`.

## Recipe 3: Bring your own LLM and embeddings

The integration ships with `FakeListChatModel` and `DeterministicFakeEmbedding` defaults so the example and benchmark run with zero API keys. Production setups swap these out:

**LLM (any LangChain chat model works):**
```python
from langchain_anthropic import ChatAnthropic
model = ChatAnthropic(model="claude-opus-4-7")

# or
from langchain_openai import ChatOpenAI
model = ChatOpenAI(model="gpt-4o")
```

**Embeddings for semantic search:**
```python
from langchain_openai import OpenAIEmbeddings
from warm_memory.langgraph import EmbeddingsImportanceScorer, WarmStore

scorer = EmbeddingsImportanceScorer(OpenAIEmbeddings())
store = WarmStore(scorer=scorer)
```

Any LangChain `Embeddings` implementation works — Voyage, HuggingFace, Cohere, etc. The scorer caches embeddings by string content, so adding the same row twice doesn't re-embed.

## Recipe 4: Multi-tenant pattern (the load-bearing reason to use WarmStore)

For agents serving many users, use the first namespace level as the tenant id. Per-namespace eviction means heavy users don't push light users' memory out.

```python
store = WarmStore(capacity=32)  # 32 items per user, not global

# Same store, isolated per-user warm memory
agent.invoke({"query": "...", "namespace": ("user-123",)})
agent.invoke({"query": "...", "namespace": ("user-456",)})

# Deep namespacing for sub-collections
store.put(("user-123", "preferences"), "tone", {"text": "concise answers"})
store.put(("user-123", "history"), "msg-1", {"text": "..."})

# Search across all of user-123's sub-collections
hits = store.search(("user-123",), query="...")
```

`store.search(prefix)` walks every namespace whose tuple starts with `prefix`, so a prefix of `("user-123",)` finds matches in `("user-123", "preferences")` and `("user-123", "history")` automatically.

## Common pitfalls

- **Namespace must be a tuple of strings, not a string.** `store.put("alice", ...)` will fail. Use `("alice",)`. This is a LangGraph convention, not WarmMemory's invention.
- **`WarmStore(capacity=N)` means N per namespace, not N total.** If you actually want a global cap, you'd need a single shared namespace, or to track totals yourself.
- **The default scorer is keyword-based, not semantic.** If recall feels weak, the first thing to try is swapping in `EmbeddingsImportanceScorer(real_embeddings)`. See `warmmemory-extend` for custom scorer patterns.
- **WarmStore is in-memory only.** It's a warm tier, by design. Pair it with a persistent store (LangGraph's Postgres store, your vector DB, etc.) for anything that needs to survive a restart.

## Where to look in the repo

- `warm_memory/langgraph/store.py` — `WarmStore` implementation, batch routing, filter logic
- `warm_memory/langgraph/agent.py` — `build_warm_memory_agent`
- `warm_memory/langgraph/embeddings.py` — `EmbeddingsImportanceScorer`
- `examples/langgraph_warm_agent.py` — runnable end-to-end example with no API keys
- `tests/test_langgraph_store.py` — 20 conformance/eviction tests; useful as living documentation of the API surface
