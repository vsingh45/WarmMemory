from __future__ import annotations

import asyncio
import unittest

from langchain_core.embeddings import DeterministicFakeEmbedding
from langgraph.store.base import GetOp, PutOp, SearchOp

from warm_memory.langgraph import EmbeddingsImportanceScorer, WarmStore


class WarmStoreBasicsTests(unittest.TestCase):
    def test_put_then_get_round_trip(self) -> None:
        store = WarmStore(capacity=4)
        store.put(("alice",), "note1", {"text": "hello", "topic": "greet"})

        item = store.get(("alice",), "note1")
        self.assertIsNotNone(item)
        self.assertEqual(item.value, {"text": "hello", "topic": "greet"})
        self.assertEqual(item.namespace, ("alice",))
        self.assertEqual(item.key, "note1")

    def test_get_missing_returns_none(self) -> None:
        store = WarmStore(capacity=4)
        self.assertIsNone(store.get(("alice",), "nope"))

    def test_update_preserves_created_at_and_advances_updated_at(self) -> None:
        store = WarmStore(capacity=4)
        store.put(("alice",), "note1", {"text": "first"})
        first = store.get(("alice",), "note1")
        store.put(("alice",), "note1", {"text": "second"})
        second = store.get(("alice",), "note1")

        self.assertEqual(second.value, {"text": "second"})
        self.assertEqual(second.created_at, first.created_at)
        self.assertGreaterEqual(second.updated_at, first.updated_at)

    def test_delete_via_put_none_and_via_delete(self) -> None:
        store = WarmStore(capacity=4)
        store.put(("alice",), "note1", {"text": "first"})
        store.put(("alice",), "note2", {"text": "second"})

        store.delete(("alice",), "note1")
        self.assertIsNone(store.get(("alice",), "note1"))
        self.assertIsNotNone(store.get(("alice",), "note2"))

        store.batch([PutOp(("alice",), "note2", None)])
        self.assertIsNone(store.get(("alice",), "note2"))


class WarmStoreSearchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = WarmStore(capacity=16)
        self.store.put(("alice",), "n1", {"text": "reset my password", "topic": "auth", "priority": 1})
        self.store.put(("alice",), "n2", {"text": "billing invoice for March", "topic": "billing", "priority": 5})
        self.store.put(("alice",), "n3", {"text": "trip to Chicago next Friday", "topic": "travel", "priority": 3})

    def test_search_by_query_ranks_relevance(self) -> None:
        results = self.store.search(("alice",), query="password reset link")
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0].key, "n1")

    def test_search_exact_filter(self) -> None:
        results = self.store.search(("alice",), filter={"topic": "billing"})
        self.assertEqual([r.key for r in results], ["n2"])

    def test_search_operator_filter(self) -> None:
        results = self.store.search(("alice",), filter={"priority": {"$gte": 3}})
        keys = {r.key for r in results}
        self.assertEqual(keys, {"n2", "n3"})

    def test_search_query_plus_filter(self) -> None:
        results = self.store.search(
            ("alice",), query="password reset link", filter={"topic": "auth"}
        )
        self.assertEqual([r.key for r in results], ["n1"])

    def test_search_prefix_traverses_subnamespaces(self) -> None:
        self.store.put(("alice", "private"), "secret", {"text": "private note", "topic": "auth"})
        results = self.store.search(("alice",), filter={"topic": "auth"})
        keys = {r.key for r in results}
        self.assertEqual(keys, {"n1", "secret"})

    def test_unknown_filter_operator_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.store.search(("alice",), filter={"priority": {"$bogus": 1}})

    def test_comparison_operator_missing_field_excludes_row(self) -> None:
        # Row n2 has priority=5; n1 has priority=1; n3 has priority=3.
        # A filter for $gt on a non-existent field returns no rows
        # (graceful False rather than TypeError, even though the underlying
        # float() coercion would otherwise crash on None).
        results = self.store.search(("alice",), filter={"nonexistent_field": {"$gt": 0}})
        self.assertEqual(results, [])

    def test_negative_limit_returns_empty(self) -> None:
        self.assertEqual(self.store.search(("alice",), limit=-1), [])
        self.assertEqual(self.store.search(("alice",), limit=0), [])

    def test_negative_offset_treated_as_zero(self) -> None:
        positive = self.store.search(("alice",), limit=10, offset=0)
        negative = self.store.search(("alice",), limit=10, offset=-5)
        self.assertEqual([r.key for r in positive], [r.key for r in negative])

    def test_search_limit_and_offset(self) -> None:
        all_three = self.store.search(("alice",), limit=10)
        self.assertEqual(len(all_three), 3)
        first_two = self.store.search(("alice",), limit=2)
        self.assertEqual(len(first_two), 2)
        skip_one = self.store.search(("alice",), limit=2, offset=1)
        self.assertEqual([r.key for r in skip_one], [r.key for r in all_three[1:]])


class WarmStoreNamespaceTests(unittest.TestCase):
    def test_list_namespaces_returns_known_namespaces(self) -> None:
        store = WarmStore(capacity=4)
        store.put(("alice",), "n1", {"text": "a"})
        store.put(("bob",), "n1", {"text": "b"})
        store.put(("bob", "private"), "n1", {"text": "bp"})

        all_ns = store.list_namespaces()
        self.assertIn(("alice",), all_ns)
        self.assertIn(("bob",), all_ns)
        self.assertIn(("bob", "private"), all_ns)

    def test_list_namespaces_prefix_filter(self) -> None:
        store = WarmStore(capacity=4)
        store.put(("alice",), "n1", {"text": "a"})
        store.put(("alice", "private"), "n1", {"text": "ap"})
        store.put(("bob",), "n1", {"text": "b"})

        result = store.list_namespaces(prefix=("alice",))
        self.assertIn(("alice",), result)
        self.assertIn(("alice", "private"), result)
        self.assertNotIn(("bob",), result)

    def test_list_namespaces_max_depth_truncates(self) -> None:
        store = WarmStore(capacity=4)
        store.put(("alice", "private", "deep"), "n1", {"text": "deep"})

        result = store.list_namespaces(max_depth=1)
        self.assertEqual(result, [("alice",)])

    def test_list_namespaces_suffix_filter(self) -> None:
        store = WarmStore(capacity=4)
        store.put(("alice", "v1"), "n1", {"text": "a"})
        store.put(("bob", "v1"), "n1", {"text": "b"})
        store.put(("alice", "v2"), "n1", {"text": "a2"})

        result = store.list_namespaces(suffix=("v1",))
        keys = set(result)
        self.assertIn(("alice", "v1"), keys)
        self.assertIn(("bob", "v1"), keys)
        self.assertNotIn(("alice", "v2"), keys)


class WarmStoreKeyGenerationTests(unittest.TestCase):
    def test_next_key_is_monotonic_per_namespace(self) -> None:
        store = WarmStore(capacity=4)
        self.assertEqual(store.next_key(("alice",)), "exchange-1")
        self.assertEqual(store.next_key(("alice",)), "exchange-2")
        self.assertEqual(store.next_key(("alice",)), "exchange-3")
        # separate counter per namespace
        self.assertEqual(store.next_key(("bob",)), "exchange-1")

    def test_next_key_supports_custom_prefix(self) -> None:
        store = WarmStore(capacity=4)
        self.assertEqual(store.next_key(("alice",), prefix="turn-"), "turn-1")
        self.assertEqual(store.next_key(("alice",), prefix="turn-"), "turn-2")

    def test_next_key_not_reset_by_eviction(self) -> None:
        # Regression test: with capacity=2 and 5 puts, the old `len(buffer)+1`
        # scheme produced colliding keys (overwrites instead of new entries).
        store = WarmStore(capacity=2)
        for _ in range(5):
            key = store.next_key(("alice",))
            store.put(("alice",), key, {"text": f"row {key}"})

        items = store.search(("alice",), limit=10)
        self.assertEqual({i.key for i in items}, {"exchange-4", "exchange-5"})


class WarmStoreCapacityTests(unittest.TestCase):
    def test_per_namespace_eviction_does_not_cross_tenants(self) -> None:
        store = WarmStore(capacity=2)
        for idx in range(5):
            store.put(("alice",), f"a{idx}", {"text": f"alice {idx}"})
        store.put(("bob",), "b1", {"text": "bob alone"})

        alice_items = store.search(("alice",), limit=10)
        self.assertEqual(len(alice_items), 2)
        self.assertEqual({r.key for r in alice_items}, {"a3", "a4"})

        bob_items = store.search(("bob",), limit=10)
        self.assertEqual(len(bob_items), 1)
        self.assertEqual(bob_items[0].key, "b1")

    def test_size_per_namespace(self) -> None:
        store = WarmStore(capacity=3)
        store.put(("alice",), "a1", {"text": "x"})
        store.put(("alice",), "a2", {"text": "y"})
        store.put(("bob",), "b1", {"text": "z"})
        self.assertEqual(store.size(("alice",)), 2)
        self.assertEqual(store.size(("bob",)), 1)
        self.assertEqual(store.size(("carol",)), 0)


class WarmStoreBatchAndAsyncTests(unittest.TestCase):
    def test_batch_executes_mixed_ops_in_order(self) -> None:
        store = WarmStore(capacity=4)
        results = store.batch(
            [
                PutOp(("alice",), "n1", {"text": "first"}),
                GetOp(("alice",), "n1"),
                SearchOp(("alice",), query="first"),
            ]
        )
        self.assertIsNone(results[0])
        self.assertEqual(results[1].value, {"text": "first"})
        self.assertEqual(results[2][0].key, "n1")

    def test_abatch_routes_through_sync_path(self) -> None:
        store = WarmStore(capacity=4)

        async def run() -> None:
            await store.aput(("alice",), "n1", {"text": "asynchello"})
            item = await store.aget(("alice",), "n1")
            self.assertEqual(item.value, {"text": "asynchello"})
            results = await store.asearch(("alice",), query="asynchello")
            self.assertEqual(results[0].key, "n1")

        asyncio.run(run())


class WarmStoreEmbeddingsScorerTests(unittest.TestCase):
    def test_embeddings_scorer_drives_search_ranking(self) -> None:
        embeddings = DeterministicFakeEmbedding(size=64)
        scorer = EmbeddingsImportanceScorer(embeddings)
        store = WarmStore(capacity=8, scorer=scorer)

        store.put(("alice",), "n1", {"text": "the cat sat on the mat"})
        store.put(("alice",), "n2", {"text": "completely unrelated grocery list"})
        store.put(("alice",), "n3", {"text": "feline animal on a rug"})

        results = store.search(("alice",), query="the cat sat on the mat")
        self.assertEqual(results[0].key, "n1")

    def test_embedding_cache_is_bounded_lru(self) -> None:
        embeddings = DeterministicFakeEmbedding(size=8)
        scorer = EmbeddingsImportanceScorer(embeddings, cache_size=3)

        # Prime the cache with 5 distinct strings; LRU should keep the last 3.
        for i in range(5):
            scorer._embed(f"content-{i}")

        self.assertEqual(scorer.cache_size(), 3)

    def test_embedding_cache_can_be_disabled(self) -> None:
        embeddings = DeterministicFakeEmbedding(size=8)
        scorer = EmbeddingsImportanceScorer(embeddings, cache_size=0)
        scorer._embed("hello")
        scorer._embed("world")
        self.assertEqual(scorer.cache_size(), 0)

    def test_negative_cache_size_rejected(self) -> None:
        embeddings = DeterministicFakeEmbedding(size=8)
        with self.assertRaises(ValueError):
            EmbeddingsImportanceScorer(embeddings, cache_size=-1)


class AgentMessageContentTests(unittest.TestCase):
    def test_flatten_list_of_text_blocks(self) -> None:
        from warm_memory.langgraph.agent import _flatten_message_content

        content = [
            {"type": "text", "text": "Hello"},
            {"type": "text", "text": "world"},
        ]
        self.assertEqual(_flatten_message_content(content), "Hello\nworld")

    def test_flatten_string_passthrough(self) -> None:
        from warm_memory.langgraph.agent import _flatten_message_content

        self.assertEqual(_flatten_message_content("plain text"), "plain text")

    def test_flatten_ignores_non_text_blocks(self) -> None:
        from warm_memory.langgraph.agent import _flatten_message_content

        content = [
            {"type": "text", "text": "first"},
            {"type": "tool_use", "input": {"x": 1}},
            {"type": "text", "text": "second"},
        ]
        self.assertEqual(_flatten_message_content(content), "first\nsecond")


if __name__ == "__main__":
    unittest.main()
