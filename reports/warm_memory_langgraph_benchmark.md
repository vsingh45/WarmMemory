# WarmMemory + LangGraph Benchmark

Compares three retrieval strategies driven through the LangGraph BaseStore API.

## Configuration

- warm_capacity: 8
- top_k: 5
- embedding_dims: 64
- warm_hit_threshold: 0.34

## Summary

| strategy | turns | warm_hit_rate | fallback_rate | avg_prompt_tokens | avg_end_to_end_ms | p95_end_to_end_ms | answer_accuracy | memory_precision_at_k |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| full-history | 12.0 | 0.0 | 0.0 | 52.0 | 41.68 | 47.548 | 0.5833333333333334 | 0.225 |
| vector-only | 12.0 | 0.0 | 1.0 | 35.416666666666664 | 47.82794774117258 | 49.330564315976574 | 0.4166666666666667 | 0.19583333333333333 |
| warm-fallback | 12.0 | 0.5 | 0.5 | 35.25 | 44.36801407405796 | 49.92959819765202 | 0.5 | 0.25 |

## Readout

- Lowest average latency: `full-history`
- Highest answer accuracy: `full-history`
- Smallest prompt footprint: `warm-fallback`

## Strategies

- `full-history` is the naive baseline: every prior turn is in the prompt.
- `vector-only` uses LangGraph's InMemoryStore with an embedding index.
- `warm-fallback` puts WarmStore in front of the vector store; the vector store
  is only consulted when warm relevance falls below `warm_hit_threshold`.
