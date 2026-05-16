# Community Contribution Drafts

This directory holds **drafts** of issues/posts targeting the LangGraph and
LangChain community. They are checked in so:

- the messaging stays in sync with the actual code and benchmark numbers,
- the LangGraph maintainers' contribution guidance is reflected in the
  drafts themselves,
- anyone (you, a collaborator, future-you) can post them without
  reconstructing them from memory.

## The maintainer-specified path

The LangGraph maintainer guidance for proposing a feature like this is
explicit and we follow it:

1. **Open an Issue titled "Proposal: Warm Memory Implementation"** on
   `langchain-ai/langgraph` with the architectural approach. Cover the
   four required sections: define the abstraction, give a usage pattern,
   describe performance and scaling, and explain integration with existing
   tools.
2. **Share a minimal reproducible example** in the proposal — a script
   demonstrating the memory implementation within a LangGraph workflow.
3. **Request review.** Once the abstraction is settled, open a draft Pull
   Request for implementation-level feedback.

The LangChain Forum (https://forum.langchain.com) is a good informal venue
to ask for early eyes on the proposal *before* opening the Issue. Discord
and Slack are deprecated for LangChain community engagement.

## Drafts

| File | Venue | Purpose |
|---|---|---|
| [`proposal.md`](proposal.md) | The canonical proposal document referenced from the Issue. Lives in this repo as the linkable source of truth. | Full four-section proposal with abstraction, usage pattern, scaling, and integration analysis |
| [`langgraph_discussion.md`](langgraph_discussion.md) | `langchain-ai/langgraph` Issues — title `Proposal: Warm Memory Implementation` | Short triage-friendly Issue body that links to `proposal.md` and the minimal example |
| [`langgraph_issue_third_party_stores.md`](langgraph_issue_third_party_stores.md) | `langchain-ai/langgraph` Issues | Separate Issue proposing a docs index for third-party `BaseStore` implementations |

## Suggested posting order

1. **Optional pre-step:** post a short thread on
   [forum.langchain.com](https://forum.langchain.com) asking for informal
   eyes on the proposal. Low stakes, fast feedback on framing.
2. **The Issue:** post the body from
   [`langgraph_discussion.md`](langgraph_discussion.md) on
   `langchain-ai/langgraph` Issues with the title
   **"Proposal: Warm Memory Implementation"**. This is the
   maintainer-specified entry point. Link to
   [`proposal.md`](proposal.md) and
   [`examples/minimal_langgraph_warm_memory.py`](../../examples/minimal_langgraph_warm_memory.py)
   from the body.
3. **Wait for maintainer guidance** on direction:
   - if they prefer it as a third-party package, the work is essentially
     done — they may suggest a docs link-out or a third-party-stores
     index page (which is the subject of
     [`langgraph_issue_third_party_stores.md`](langgraph_issue_third_party_stores.md)).
   - if they want it factored into the monorepo as
     `langgraph-store-warm`, that's a draft PR against
     `libs/store-warm/` following the `langgraph-checkpoint-postgres`
     pattern.
4. **If applicable:** open the third-party-stores Issue after the proposal
   has a green light.
5. **Open the draft PR** (docs or code, depending on maintainer steer)
   once the abstraction is agreed.

## Tone guidelines

- Lead with the user-facing benefit, not the implementation detail.
- Show the benchmark, but acknowledge it's synthetic — invite real-trace
  runs.
- End with explicit questions so the thread has an obvious next step for
  the maintainer (no "what do you think?" — instead "should this be a
  separate distribution or a third-party package?").
- Never overclaim: WarmStore is a useful warm-tier BaseStore, not a novel
  algorithm.
- Acknowledge orthogonality with checkpointers explicitly — that question
  is the most likely first review comment.
