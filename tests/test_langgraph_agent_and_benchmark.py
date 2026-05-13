from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from langchain_core.language_models.fake_chat_models import FakeListChatModel

from warm_memory.langgraph import WarmStore, build_warm_memory_agent
from warm_memory.langgraph.benchmark import (
    LangGraphBenchmarkConfig,
    run_langgraph_benchmark,
)


class WarmMemoryAgentTests(unittest.TestCase):
    def test_agent_recalls_after_two_turns(self) -> None:
        model = FakeListChatModel(
            responses=[
                "Noted: you prefer concise answers.",
                "You asked for concise answers earlier.",
            ]
        )
        store = WarmStore(capacity=8)
        agent = build_warm_memory_agent(model=model, store=store)

        namespace = ("alice",)
        first = agent.invoke({"query": "I prefer concise answers.", "namespace": namespace})
        self.assertIn("concise", first["response"].lower())
        self.assertEqual(first.get("recalled"), [])

        second = agent.invoke({"query": "Remind me what response style I wanted?", "namespace": namespace})
        recalled_keys = [r["key"] for r in second.get("recalled") or []]
        self.assertIn("exchange-1", recalled_keys)
        self.assertEqual(store.size(namespace), 2)


class LangGraphBenchmarkTests(unittest.TestCase):
    def test_benchmark_runs_and_writes_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report_path = Path(tmp) / "langgraph_bench.md"
            results = run_langgraph_benchmark(
                config=LangGraphBenchmarkConfig(warm_capacity=4),
                report_path=report_path,
            )

            self.assertEqual(
                set(results.keys()), {"full-history", "vector-only", "warm-fallback"}
            )
            for name, result in results.items():
                self.assertGreater(result.summary["turns"], 0, f"{name} has no turns")
                self.assertIn("answer_accuracy", result.summary)

            self.assertTrue(report_path.exists())
            text = report_path.read_text()
            self.assertIn("WarmMemory + LangGraph Benchmark", text)
            self.assertIn("warm-fallback", text)


if __name__ == "__main__":
    unittest.main()
