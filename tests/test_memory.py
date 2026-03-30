import unittest

from warm_memory import WarmMemoryBuffer, remember_interaction


class WarmMemoryBufferTests(unittest.TestCase):
    def test_sliding_window_keeps_last_n_interactions(self) -> None:
        memory = WarmMemoryBuffer(capacity=3)
        memory.add("user", "one")
        memory.add("assistant", "two")
        memory.add("user", "three")
        memory.add("assistant", "four")

        records = memory.recent(limit=10)

        self.assertEqual(len(records), 3)
        self.assertEqual(records["content"].tolist(), ["two", "three", "four"])

    def test_relevant_prefers_overlap_with_query(self) -> None:
        memory = WarmMemoryBuffer(capacity=6)
        memory.add("user", "Reset my password")
        memory.add("assistant", "Use the billing dashboard")
        memory.add("assistant", "You can reset the password in account settings")

        records = memory.relevant("password reset", limit=1)

        self.assertEqual(len(records), 1)
        self.assertIn("password", records.iloc[0]["content"].lower())

    def test_context_window_falls_back_to_recent_without_query(self) -> None:
        memory = WarmMemoryBuffer(capacity=4)
        memory.add("user", "a")
        memory.add("assistant", "b")

        records = memory.context_window(limit=2)

        self.assertEqual(records["content"].tolist(), ["a", "b"])

    def test_retain_relevant_compacts_live_buffer(self) -> None:
        memory = WarmMemoryBuffer(capacity=5)
        memory.add("user", "weather in chicago")
        memory.add("assistant", "billing invoice steps")
        memory.add("assistant", "download your invoice from billing")

        memory.retain_relevant("invoice billing", limit=2)

        self.assertEqual(len(memory), 2)
        contents = " ".join(memory.frame["content"].tolist()).lower()
        self.assertIn("invoice", contents)


class DecoratorTests(unittest.TestCase):
    def test_decorator_captures_input_and_output(self) -> None:
        memory = WarmMemoryBuffer(capacity=8)

        @remember_interaction(memory)
        def agent(prompt: str) -> str:
            return prompt.upper()

        result = agent("hello")

        self.assertEqual(result, "HELLO")
        self.assertEqual(len(memory), 2)
        self.assertEqual(memory.recent(2)["content"].tolist(), ["hello", "HELLO"])


if __name__ == "__main__":
    unittest.main()
