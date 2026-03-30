import tempfile
import unittest
from pathlib import Path

from warm_memory.benchmark import BenchmarkConfig, run_benchmark


class BenchmarkTests(unittest.TestCase):
    def test_benchmark_runs_all_strategies_and_writes_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = Path(tmpdir) / "report.md"
            results = run_benchmark(
                config=BenchmarkConfig(capacity=6, top_k=4, long_term_limit=6),
                report_path=report_path,
            )

            self.assertEqual(set(results), {"recency", "relevance", "fallback"})
            self.assertTrue(report_path.exists())
            self.assertIn("WarmMemory Benchmark Report", report_path.read_text(encoding="utf-8"))

            for result in results.values():
                self.assertGreater(len(result.turn_log), 0)
                self.assertIn("avg_end_to_end_ms", result.summary)
                self.assertIn("answer_accuracy", result.summary)


if __name__ == "__main__":
    unittest.main()
