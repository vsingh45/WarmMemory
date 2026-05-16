# Community Contribution Drafts

This directory holds **drafts** of posts targeting the LangChain / LangGraph
community. They are checked in so:

- the messaging stays in sync with the actual code and benchmark numbers,
- the LangGraph contribution path is reflected in the drafts themselves,
- anyone (you, a collaborator, future-you) can post them without
  reconstructing them from memory.

## The actual contribution path (as of May 2026)

The `langchain-ai/langgraph` GitHub issue tracker **does not currently
accept feature / proposal issues** — the "Create issue" UI offers only Bug
Report, Privileged (maintainer-only), security, and Documentation
templates. The `LangChain Forum` tile on that page funnels everything else
to https://forum.langchain.com, which is the canonical entry for
proposals, RFCs, and architectural discussions.

The contribution path is therefore:

1. **Post the proposal on the LangChain Forum**
   (https://forum.langchain.com) — that's the maintainer-specified entry
   for non-bug discussions. Use the body of
   [`langgraph_forum_post.md`](langgraph_forum_post.md).
2. **Wait for maintainer feedback.** A maintainer engaging on the Forum
   may:
   - Direct you to open a draft PR (docs or code) once the abstraction is
     settled.
   - Convert the Forum thread into a tracking Issue themselves (they have
     a "Privileged" template the public can't use).
   - Suggest changes to the framing before any code work happens.
3. **Open a draft PR** if/when greenlit — docs PR for a third-party-stores
   link, or a code PR factoring out `langgraph-store-warm` into the
   monorepo, depending on which path maintainers prefer.

## What about a GitHub Issue?

The "Bug Report" template on `langchain-ai/langgraph` is **not** the right
fit for this proposal — it isn't a bug. The
[`langgraph_issue_third_party_stores.md`](langgraph_issue_third_party_stores.md)
draft is preserved for if/when a maintainer says "yes, open an issue for
the third-party-stores index page." Until then it stays as a draft.

## Drafts

| File | Venue | Purpose |
|---|---|---|
| [`proposal.md`](proposal.md) | This repo — linked from the Forum thread | Full four-section proposal with abstraction, usage pattern, scaling, and integration analysis |
| [`langgraph_forum_post.md`](langgraph_forum_post.md) | https://forum.langchain.com | Triage-friendly Forum thread body that links to `proposal.md` and the minimal example |
| [`langgraph_issue_third_party_stores.md`](langgraph_issue_third_party_stores.md) | `langchain-ai/langgraph` Issues — only if a maintainer asks for it | Draft of an Issue proposing a docs index for third-party `BaseStore` implementations |

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
