from __future__ import annotations

import asyncio
import unittest

from langchain_core.embeddings import DeterministicFakeEmbedding
from langgraph.store.memory import InMemoryStore

from warm_memory.langgraph import (
    EmbeddingsImportanceScorer,
    TwoTierStore,
    WarmStore,
)


def _make_stores(*, warm_capacity: int = 16, embed_dims: int = 32):
    """Helper: build a (warm, durable, two_tier) trio with deterministic embeddings."""
    embeddings = DeterministicFakeEmbedding(size=embed_dims)
    warm = WarmStore(
        capacity=warm_capacity,
        scorer=EmbeddingsImportanceScorer(embeddings),
    )
    durable = InMemoryStore(
        index={"embed": embeddings, "dims": embed_dims, "fields": ["text"]}
    )
    return warm, durable, TwoTierStore(warm=warm, durable=durable, warm_hit_threshold=0.34)


class TwoTierStoreReadPathTests(unittest.TestCase):
    def test_warm_hit_short_circuits_durable(self) -> None:
        warm, durable, two_tier = _make_stores()

        # Put only into warm — durable has nothing.
        warm.put(("alice",), "n1", {"text": "the quick brown fox"})

        results = two_tier.search(("alice",), query="the quick brown fox")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].key, "n1")

    def test_warm_miss_falls_back_to_durable(self) -> None:
        warm, durable, two_tier = _make_stores()

        # Put only into durable.
        durable.put(("alice",), "d1", {"text": "specific durable content"})

        results = two_tier.search(("alice",), query="specific durable content")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].key, "d1")

    def test_miss_populates_warm_on_the_way_back(self) -> None:
        warm, durable, two_tier = _make_stores()

        durable.put(("alice",), "d1", {"text": "populate me into warm"})

        # First search: warm is empty, falls through to durable.
        self.assertEqual(warm.size(("alice",)), 0)
        two_tier.search(("alice",), query="populate me into warm")
        # After the fallback, warm should be populated.
        self.assertEqual(warm.size(("alice",)), 1)

    def test_populate_warm_on_miss_can_be_disabled(self) -> None:
        warm, durable, _ = _make_stores()
        two_tier = TwoTierStore(
            warm=warm, durable=durable, populate_warm_on_miss=False
        )

        durable.put(("alice",), "d1", {"text": "do not cache me"})
        two_tier.search(("alice",), query="do not cache me")
        self.assertEqual(warm.size(("alice",)), 0)

    def test_get_warm_first_then_durable(self) -> None:
        warm, durable, two_tier = _make_stores()

        durable.put(("alice",), "k1", {"text": "from durable"})

        item = two_tier.get(("alice",), "k1")
        self.assertIsNotNone(item)
        self.assertEqual(item.value, {"text": "from durable"})
        # warm should be populated after the durable get
        self.assertIsNotNone(warm.get(("alice",), "k1"))

    def test_warm_hit_threshold_governs_short_circuit(self) -> None:
        warm, durable, _ = _make_stores()

        # Put one item in warm with a topic only loosely related to the query.
        warm.put(("alice",), "w1", {"text": "completely unrelated topic"})
        durable.put(("alice",), "d1", {"text": "exact match query content"})

        # High threshold: warm hit fails, falls through to durable.
        two_tier = TwoTierStore(
            warm=warm, durable=durable, warm_hit_threshold=0.99
        )
        results = two_tier.search(("alice",), query="exact match query content")
        # Should have fallen through to durable
        keys = {r.key for r in results}
        self.assertIn("d1", keys)


class TwoTierStoreWritePathTests(unittest.TestCase):
    def test_put_mirrors_to_both_stores(self) -> None:
        warm, durable, two_tier = _make_stores()

        two_tier.put(("alice",), "k1", {"text": "mirror me"})

        self.assertIsNotNone(warm.get(("alice",), "k1"))
        self.assertIsNotNone(durable.get(("alice",), "k1"))

    def test_delete_mirrors_to_both_stores(self) -> None:
        warm, durable, two_tier = _make_stores()

        two_tier.put(("alice",), "k1", {"text": "to be deleted"})
        two_tier.delete(("alice",), "k1")

        self.assertIsNone(warm.get(("alice",), "k1"))
        self.assertIsNone(durable.get(("alice",), "k1"))

    def test_write_through_disabled_skips_warm(self) -> None:
        warm, durable, _ = _make_stores()
        two_tier = TwoTierStore(warm=warm, durable=durable, write_through=False)

        two_tier.put(("alice",), "k1", {"text": "durable only"})

        self.assertIsNone(warm.get(("alice",), "k1"))
        self.assertIsNotNone(durable.get(("alice",), "k1"))


class TwoTierStoreAsyncTests(unittest.TestCase):
    def test_async_put_writes_to_both_stores(self) -> None:
        warm, durable, two_tier = _make_stores()

        async def run() -> None:
            await two_tier.aput(("alice",), "k1", {"text": "async mirror"})

        asyncio.run(run())

        self.assertIsNotNone(warm.get(("alice",), "k1"))
        self.assertIsNotNone(durable.get(("alice",), "k1"))

    def test_async_search_warm_hit(self) -> None:
        warm, durable, two_tier = _make_stores()
        warm.put(("alice",), "w1", {"text": "async search me"})

        async def run() -> list:
            return await two_tier.asearch(("alice",), query="async search me")

        results = asyncio.run(run())
        self.assertEqual(results[0].key, "w1")

    def test_async_get_falls_through_and_populates(self) -> None:
        warm, durable, two_tier = _make_stores()
        durable.put(("alice",), "k1", {"text": "from durable async"})

        async def run() -> object:
            return await two_tier.aget(("alice",), "k1")

        item = asyncio.run(run())
        self.assertIsNotNone(item)
        self.assertIsNotNone(warm.get(("alice",), "k1"))

    def test_async_parallel_writes_total_latency_ge_max_not_sum(self) -> None:
        """
        Verify the async write path actually runs warm and durable writes
        concurrently. We mock both stores with controllable delays and assert
        the total wall-clock is closer to max(warm_delay, durable_delay) than
        to the sum.
        """
        import time

        class SlowStore:
            """Minimal BaseStore-ish double — only aput is needed for this test."""
            def __init__(self, delay: float) -> None:
                self.delay = delay
                self.calls: list[tuple] = []

            async def aput(self, namespace, key, value, **kwargs):
                await asyncio.sleep(self.delay)
                self.calls.append((namespace, key, value))

            async def adelete(self, namespace, key):
                await asyncio.sleep(self.delay)

        warm_slow = SlowStore(delay=0.05)
        durable_slow = SlowStore(delay=0.05)
        two_tier = TwoTierStore(warm=warm_slow, durable=durable_slow)

        async def run() -> float:
            start = time.perf_counter()
            await two_tier._ado_put(
                # Build a PutOp manually
                __import__("langgraph.store.base", fromlist=["PutOp"]).PutOp(
                    ("alice",), "k1", {"text": "hi"}, index=None, ttl=None,
                )
            )
            return time.perf_counter() - start

        elapsed = asyncio.run(run())
        # Sequential would be ~0.10s; parallel should be ~0.05s. Allow ample
        # slack (0.085s) for scheduler jitter on slow CI machines while still
        # proving the writes ran concurrently.
        self.assertLess(
            elapsed,
            0.085,
            f"Expected parallel writes (~0.05s); got {elapsed:.3f}s — looks sequential",
        )
        self.assertEqual(len(warm_slow.calls), 1)
        self.assertEqual(len(durable_slow.calls), 1)


class TwoTierStoreErrorSemanticsTests(unittest.TestCase):
    def test_warm_error_is_tolerated_by_default(self) -> None:
        class FailingWarm:
            def put(self, namespace, key, value, **kwargs):
                raise RuntimeError("warm is sad")

            def delete(self, namespace, key):
                raise RuntimeError("warm is sad")

            def get(self, namespace, key):
                return None

            def search(self, *args, **kwargs):
                return []

            async def aput(self, namespace, key, value, **kwargs):
                raise RuntimeError("warm is sad async")

            async def aget(self, namespace, key):
                return None

            async def asearch(self, *args, **kwargs):
                return []

            async def adelete(self, namespace, key):
                raise RuntimeError("warm is sad async")

        durable = InMemoryStore()
        two_tier = TwoTierStore(warm=FailingWarm(), durable=durable)

        # Sync: should not raise.
        two_tier.put(("alice",), "k1", {"text": "hi"})
        self.assertIsNotNone(durable.get(("alice",), "k1"))

        # Async: should not raise either.
        async def run() -> None:
            await two_tier.aput(("alice",), "k2", {"text": "hi async"})

        asyncio.run(run())
        self.assertIsNotNone(durable.get(("alice",), "k2"))

    def test_durable_error_propagates(self) -> None:
        class FailingDurable:
            def put(self, namespace, key, value, **kwargs):
                raise RuntimeError("durable is unreachable")

            def get(self, namespace, key):
                return None

            def search(self, *args, **kwargs):
                return []

            def delete(self, namespace, key):
                raise RuntimeError("durable is unreachable")

            async def aput(self, namespace, key, value, **kwargs):
                raise RuntimeError("durable is unreachable async")

            async def aget(self, namespace, key):
                return None

            async def asearch(self, *args, **kwargs):
                return []

            async def adelete(self, namespace, key):
                raise RuntimeError("durable is unreachable async")

        warm = WarmStore(capacity=4)
        two_tier = TwoTierStore(warm=warm, durable=FailingDurable())

        with self.assertRaises(RuntimeError):
            two_tier.put(("alice",), "k1", {"text": "hi"})

        async def run_async() -> None:
            await two_tier.aput(("alice",), "k2", {"text": "hi async"})

        with self.assertRaises(RuntimeError):
            asyncio.run(run_async())

    def test_fail_on_warm_error_strict_mode(self) -> None:
        class FailingWarm:
            def put(self, *args, **kwargs):
                raise RuntimeError("strict mode")

            def get(self, *args, **kwargs):
                return None

            def search(self, *args, **kwargs):
                return []

            def delete(self, *args, **kwargs):
                pass

            async def aput(self, *args, **kwargs):
                raise RuntimeError("strict mode async")

            async def aget(self, *args, **kwargs):
                return None

            async def asearch(self, *args, **kwargs):
                return []

            async def adelete(self, *args, **kwargs):
                pass

        durable = InMemoryStore()
        two_tier = TwoTierStore(
            warm=FailingWarm(),
            durable=durable,
            fail_on_warm_error=True,
        )

        with self.assertRaises(RuntimeError):
            two_tier.put(("alice",), "k1", {"text": "hi"})


if __name__ == "__main__":
    unittest.main()
