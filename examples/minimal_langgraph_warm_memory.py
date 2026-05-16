"""
Minimal reproducible example for the LangGraph WarmStore proposal.

Demonstrates the warm-memory recall pattern inside a LangGraph workflow with
zero API keys: FakeListChatModel for the LLM, KeywordImportanceScorer for
ranking. Swap either for a real LangChain component to graduate this to a
production agent.

Run:
    pip install -e ".[langgraph]"
    python examples/minimal_langgraph_warm_memory.py

Expected output: turn 2 recalls turn 1's exchange from the warm store and
includes it in the prompt before the model responds.
"""

from langchain_core.language_models.fake_chat_models import FakeListChatModel

from warm_memory.langgraph import WarmStore, build_warm_memory_agent


def main() -> None:
    store = WarmStore(capacity=8)
    agent = build_warm_memory_agent(
        model=FakeListChatModel(
            responses=[
                "Noted: you prefer concise answers.",
                "Yes, you asked for concise answers earlier.",
            ]
        ),
        store=store,
    )

    namespace = ("alice",)

    # Turn 1 — fact captured into warm memory.
    agent.invoke({"query": "I prefer concise answers.", "namespace": namespace})

    # Turn 2 — prior turn recalled from the warm store and inserted into the prompt.
    result = agent.invoke(
        {
            "query": "What response style did I ask for?",
            "namespace": namespace,
        }
    )

    print("recalled:", result["recalled"])
    print("response:", result["response"])
    print(f"warm buffer size for {namespace}: {store.size(namespace)}")


if __name__ == "__main__":
    main()
