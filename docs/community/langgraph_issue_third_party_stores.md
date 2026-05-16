# Draft: LangGraph Issue — third-party stores index

**Where to post:** https://github.com/langchain-ai/langgraph/issues/new

**Suggested labels:** `documentation`, `enhancement`

**Title:** `docs: add an index of third-party BaseStore implementations`

---

### Context

LangGraph's `BaseStore` is a clean extension point and the ecosystem already has several community implementations (Postgres, Redis, Mongo, custom in-memory tiers, etc.). Today these are scattered across individual repos and harder to discover than `Document Loaders`, `Embeddings`, or `Vector stores` are in the LangChain docs (each of which has a curated index page).

I just shipped a third-party store (`warm-memory`'s `WarmStore`, a capacity-bounded warm tier with per-namespace eviction — see [vsingh45/WarmMemory](https://github.com/vsingh45/WarmMemory)) and hit this discoverability gap while writing the README.

### Proposal

Add a docs page — e.g., `langchain-ai/langgraph/docs/docs/concepts/persistence.md` adjacent section, or a dedicated `third_party_stores.md` — that lists community `BaseStore` implementations with:

- package name + install command
- one-line description / what it's optimized for (durability, latency, multi-tenant, semantic search, capacity-bounded, etc.)
- link to repo + docs

A short minimum-bar (must implement `batch` + `abatch`, pass the contract tests, have a maintained repo) would keep quality up without gatekeeping community contributions.

### Why this is worth a small docs investment

- Reduces "do I need to write my own store?" reinvention.
- Signals to the community that third-party stores are a first-class extension surface (the way third-party vector stores are in LangChain).
- Gives prospective contributors (myself included) a clear target to aim for, rather than having to ask in a Discussion which is the right venue.

### Happy to send the PR

If this seems useful, I'd be glad to send a docs PR with a starter page including the obvious built-ins (`InMemoryStore`, `PostgresStore`) plus a "Submit yours" section. Let me know if the LangGraph team would prefer a particular location or naming convention for the page.

— Vivek
