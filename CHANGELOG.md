# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-05-15

### Added

- `warm_memory.langgraph` module (opt-in via the `[langgraph]` extra):
  - `WarmStore(BaseStore)` — LangGraph store with per-namespace warm buffers.
    Each top-level namespace gets its own bounded buffer so multi-tenant
    agents do not evict each other's memory. Supports `$eq`, `$ne`, `$gt`,
    `$gte`, `$lt`, `$lte` filter operators and prefix/suffix/max_depth
    namespace listing.
  - `EmbeddingsImportanceScorer` — bring-your-own LangChain `Embeddings`
    instance for semantic ranking with built-in per-string caching.
  - `build_warm_memory_agent` — a compiled LangGraph
    (`memory_lookup → respond → memory_write`) that wraps any LangChain
    chat model.
- `warm_memory.langgraph.benchmark` — comparative benchmark across three
  retrieval strategies driven entirely through `BaseStore`:
  - `full-history`: every prior turn in the prompt
  - `vector-only`: `InMemoryStore` with an embedding index
  - `warm-fallback`: `WarmStore` in front of the vector store
  Synthetic by default; swap in real embeddings via `WARM_BENCH_EMBEDDINGS`.
- `examples/langgraph_warm_agent.py` — runnable demo, no API keys required.
- `scripts/run_langgraph_benchmark.py` — CLI entrypoint for the benchmark.
- Claude Code skills under `.claude/skills/` covering integration,
  benchmarking, and extension/debugging.
- GitHub Actions CI running tests + both benchmarks on Python 3.11, 3.12, 3.13.
- PyPI publishing workflow (trusted publisher) triggered by GitHub Releases.
- `CITATION.cff`, `CHANGELOG.md`, README status badges.

### Changed

- Project distribution name: `WarmMemory` → `warm-memory` (PEP 503 normalized
  name for PyPI). Import path `warm_memory` is unchanged.
- `pyproject.toml`: added classifiers, keywords, project URLs, and a `[dev]`
  optional extra.

## [0.1.0] - 2026-05-12

### Added

- Initial release: `WarmMemoryBuffer`, `ImportanceScorer` ABC with
  `KeywordImportanceScorer`, `@remember_interaction` decorator,
  deterministic benchmark over `recency` / `relevance` / `fallback`
  strategies, HTML documentation.

[Unreleased]: https://github.com/vsingh45/WarmMemory/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/vsingh45/WarmMemory/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/vsingh45/WarmMemory/releases/tag/v0.1.0
