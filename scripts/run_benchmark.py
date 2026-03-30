from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from warm_memory.benchmark import BenchmarkConfig, run_benchmark


def main() -> None:
    report_path = Path("reports") / "warm_memory_benchmark.md"
    results = run_benchmark(config=BenchmarkConfig(), report_path=report_path)
    print(f"report={report_path}")
    for name, result in results.items():
        print(
            f"{name}: avg_latency_ms={result.summary['avg_end_to_end_ms']:.3f}, "
            f"accuracy={result.summary['answer_accuracy']:.3f}, "
            f"fallback_rate={result.summary['fallback_rate']:.3f}"
        )


if __name__ == "__main__":
    main()
