"""
Run the LangGraph-backed WarmMemory benchmark.

Default: fully synthetic, no API keys, deterministic embeddings.

Drop in real embeddings via WARM_BENCH_EMBEDDINGS=openai (set OPENAI_API_KEY)
or by importing this module and passing `embeddings=...`.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from warm_memory.langgraph.benchmark import run_langgraph_benchmark


def _build_embeddings():
    provider = os.environ.get("WARM_BENCH_EMBEDDINGS", "").lower()
    if provider == "openai":
        from langchain_openai import OpenAIEmbeddings  # type: ignore[import-not-found]
        return OpenAIEmbeddings()
    if provider == "huggingface":
        from langchain_huggingface import HuggingFaceEmbeddings  # type: ignore[import-not-found]
        return HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    return None  # fall back to DeterministicFakeEmbedding inside the benchmark


def main() -> None:
    report_path = REPO_ROOT / "reports" / "warm_memory_langgraph_benchmark.md"
    results = run_langgraph_benchmark(
        embeddings=_build_embeddings(),
        report_path=report_path,
    )
    print(f"Wrote {report_path}\n")
    for name, result in results.items():
        print(f"== {name} ==")
        for metric, value in result.summary.items():
            print(f"  {metric}: {value:.3f}")
        print()


if __name__ == "__main__":
    main()
