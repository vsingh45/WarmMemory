# Contributing

Contributions are welcome, especially in the following areas:

- stronger importance scoring methods,
- benchmark realism and workload quality,
- production-oriented storage backends,
- evaluation metrics and reporting,
- integration examples with real agent frameworks.

## Contribution Principles

- Keep claims technically accurate.
- Preserve the distinction between architecture experiments and algorithmic novelty.
- Prefer measurable changes over speculative complexity.
- Add tests for new behavior.

## Development Workflow

1. Install the project in editable mode.
2. Make changes in `warm_memory/`.
3. Run the full test suite.
4. If you change benchmark behavior, regenerate the benchmark report.
5. Update documentation when public-facing behavior changes.

## Commands

```bash
python3 -m pip install -e .
python3 -m unittest discover -s tests -v
python3 scripts/run_benchmark.py
```

## Good First Contributions

- add a new `ImportanceScorer` implementation
- add a new benchmark workload
- improve memory-quality metrics
- add charts or visualization output
- add integration examples for common agent stacks
