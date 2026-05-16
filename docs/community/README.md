# Community Contribution Drafts

This directory holds **drafts** of posts/issues meant for the wider LangChain
and LangGraph community. They are checked in so:

- the messaging is reviewable and version-controlled,
- the benchmark numbers and code claims stay in sync with the repo, and
- anyone (you, a collaborator, a future-me) can post them without reconstructing them.

Each draft starts with a "Where to post" header. Open that URL, paste the
body, edit lightly for current context, post.

## Drafts

| File | Venue | Purpose |
|---|---|---|
| [`langgraph_discussion.md`](langgraph_discussion.md) | `langchain-ai/langgraph` Discussions (Show and tell) | Introduce WarmStore to the community, share benchmark, invite feedback |
| [`langgraph_issue_third_party_stores.md`](langgraph_issue_third_party_stores.md) | `langchain-ai/langgraph` Issues | Propose an index/docs page for third-party `BaseStore` implementations |

## Suggested posting order

1. **First:** post `langgraph_discussion.md` as a Discussion (low-friction,
   conversational). Wait a day or two for any replies.
2. **Then:** post `langgraph_issue_third_party_stores.md` as an Issue, linking
   back to the Discussion. The Issue is more committal and benefits from
   having the Discussion as social proof.
3. **If the Issue gets a green light:** open a docs PR adding the third-party
   stores page; include `warm-memory` plus the obvious built-ins.

## Tone guidelines

- Lead with the user-facing benefit, not the implementation.
- Show the benchmark, but acknowledge it's synthetic — invite real-trace runs.
- Ask explicit questions at the end so the thread has an obvious next step.
- Never overclaim: WarmMemory is a useful warm tier, not a novel algorithm.
