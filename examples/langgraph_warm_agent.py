"""
LangGraph agent backed by WarmMemory.

Run as-is (no API key required) to see the agent recall and reuse prior turns:

    python3 examples/langgraph_warm_agent.py

To use a real LLM, swap the `model` line for any LangChain chat model, e.g.:

    from langchain_anthropic import ChatAnthropic
    model = ChatAnthropic(model="claude-opus-4-7", temperature=0)

    from langchain_openai import ChatOpenAI
    model = ChatOpenAI(model="gpt-4o", temperature=0)

For semantic search, swap the scorer for an embeddings-based one:

    from langchain_openai import OpenAIEmbeddings
    from warm_memory.langgraph import EmbeddingsImportanceScorer
    store = WarmStore(scorer=EmbeddingsImportanceScorer(OpenAIEmbeddings()))
"""

from __future__ import annotations

from langchain_core.language_models.fake_chat_models import FakeListChatModel

from warm_memory.langgraph import WarmStore, build_warm_memory_agent


def main() -> None:
    canned_replies = [
        "Got it - I'll remember you prefer concise answers.",
        "Your March invoice is overdue; visit the billing portal to pay.",
        "Use the password reset link from your email within 15 minutes.",
        "Yes, you mentioned wanting concise answers earlier.",
        "Your demo trip is to Chicago next Friday.",
    ]
    model = FakeListChatModel(responses=canned_replies)
    store = WarmStore(capacity=8)
    agent = build_warm_memory_agent(model=model, store=store)

    turns = [
        "I prefer concise answers.",
        "My March invoice is overdue, what should I do?",
        "I cannot reset my password, the link expired.",
        "What response style did I ask for earlier?",
        "Where am I flying for the demo?",
    ]

    namespace = ("alice",)
    for turn in turns:
        result = agent.invoke({"query": turn, "namespace": namespace})
        recalled_keys = [r["key"] for r in result.get("recalled") or []]
        print(f"USER:      {turn}")
        print(f"RECALLED:  {recalled_keys or '(none)'}")
        print(f"ASSISTANT: {result['response']}")
        print()

    print(f"Warm buffer for {namespace}: {store.size(namespace)} items")
    print(f"Known namespaces: {store.namespaces()}")


if __name__ == "__main__":
    main()
