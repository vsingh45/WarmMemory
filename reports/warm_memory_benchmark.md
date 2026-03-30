# Warm Memory Benchmark Report

## Configuration

- capacity: 8
- top_k: 5
- long_term_limit: 8
- warm_hit_threshold: 0.34

## Summary

| strategy | turns | warm_hit_rate | fallback_rate | avg_prompt_tokens | avg_end_to_end_ms | p95_end_to_end_ms | answer_accuracy | memory_precision_at_k | repeated_tool_calls |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| recency | 12.0 | 0.9166666666666666 | 0.0 | 26.333333333333332 | 38.738979167382546 | 39.45956686105114 | 0.25 | 0.2222222222222222 | 1.0 |
| relevance | 12.0 | 0.3333333333333333 | 0.0 | 28.833333333333332 | 39.115281242365015 | 40.53663095788751 | 0.3333333333333333 | 0.23611111111111108 | 2.0 |
| fallback | 12.0 | 0.3333333333333333 | 0.6666666666666666 | 41.166666666666664 | 46.05512150791163 | 52.286544053243475 | 0.5833333333333334 | 0.27777777777777773 | 0.0 |

## Readout

- Lowest average latency: `recency`
- Highest answer accuracy: `fallback`
- Smallest prompt footprint: `recency`

## Interpretation

- `recency` shows the baseline cost of always trusting the latest interactions.
- `relevance` shows the effect of ranking and retaining the hottest working set.
- `fallback` shows a two-tier memory architecture where long-term retrieval is only used on warm misses.
