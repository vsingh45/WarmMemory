# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.1] - 2026-05-16

### Fixed

- `build_warm_memory_agent` previously generated exchange keys as
  `f"exchange-{store.size(namespace) + 1}"`. Once a namespace hit its
  capacity, `size` stayed pinned and every subsequent put silently
  overwrote an earlier exchange instead of creating a new one. Now uses
  `WarmStore.next_key()`, a per-namespace monotonic counter that is
  never reset by eviction.
- `respond` node now flattens `AIMessage.content` when newer LangChain
  chat models return content as a list of blocks (e.g.,
  `[{"type": "text", "text": "..."}]`) — previously the list-repr was
  stored in warm memory, breaking keyword/embedding scoring.
- `WarmStore` filter operators `$gt`/`$gte`/`$lt`/`$lte` now use
  `float()` coercion to match `InMemoryStore` semantics, with a
  graceful `False` return on uncoercible values (rows missing the field
  no longer crash the comparison).
- `WarmStore.search` clamps negative `limit` / `offset` to zero instead
  of returning surprising slices.

### Added

- `WarmStore.next_key(namespace, prefix=...)` — public, documented API.
- `EmbeddingsImportanceScorer` now has a **bounded LRU cache**
  (default 4096 entries; configurable via `cache_size=`, set to `0` to
  disable). New `cache_clear()` and `cache_size()` helpers.
- `WarmMemoryBuffer.find_index_by_metadata`,
  `WarmMemoryBuffer.drop_at`, `WarmMemoryBuffer.iter_rows` — small
  public mutation/iteration helpers that replace the previous
  `_frame`-private-attribute leak from `WarmStore` into the buffer.

### Changed

- CI workflow: added `concurrency:` group (cancel in-progress on new
  pushes) and `timeout-minutes: 15` per job. Explicit
  `permissions: contents: read`.
- Publish workflow: pinned `pypa/gh-action-pypi-publish` to commit SHA
  (`cef221092ed1bacb1cc03d23a2d87d1d172e277b`, v1.14.0) for supply-chain
  hardening. Added a `twine check` validation step before upload.
  `workflow_dispatch` now requires `dry_run=false` **and** a `v*` tag
  ref to actually publish — blocks an accidental "ship from main."
  Manual `dry_run` default flipped to `"true"`.
- `pyproject.toml`: SPDX-style `license = "MIT"` (requires
  `setuptools>=77`). Removed the now-redundant license classifier.
  Capped open dependency ranges (`pandas<3`, `langgraph<2`,
  `langchain-core<2`).
- `WarmStore` removed the declared-but-unused `asyncio.Lock()` slot
  (was misleading about thread safety).

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

[Unreleased]: https://github.com/vsingh45/WarmMemory/compare/v0.2.1...HEAD
[0.2.1]: https://github.com/vsingh45/WarmMemory/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/vsingh45/WarmMemory/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/vsingh45/WarmMemory/releases/tag/v0.1.0
