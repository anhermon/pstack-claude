---
name: how
description: "Use for \"how does X work\", code walkthroughs before changing something, and placement / ownership / layering questions (\"where should this live\", \"which package owns this\", \"is this the right layer\"). Explains subsystem architecture, runtime flow, onboarding mental models. Use why for motivation."
---

# How

> **Claude Code:** read Cursor terms in this skill through [`claude-code/runtime.md`](${CLAUDE_PLUGIN_ROOT}/claude-code/runtime.md) (tools, subagents, models, transcripts).

Explore the codebase to answer "how does X work?" questions. Produce architectural explanations at the level of a senior engineer onboarding onto a subsystem, enough to build a working mental model, not so much that it reads like annotated source code.

Resolve each seat's explicit `model` and `effort` from delegation-kit's live routing table when its `Delegation routing (live` section is in context; otherwise use `pstack-models.md` and the defaults below. Map `auto`, `inherit-parent`, and `inherit` to `model: sonnet`, `effort: medium`. Always pass both parameters to `Agent`, including retries and resumes. For fan-outs of 3+ use sonnet/haiku seats, never opus. The main session owns final synthesis; any separately prescribed synthesizer runs alone after the fan-out.

## Step 1. Assess Complexity

If the scope is ambiguous, state your interpretation and explore. The user can redirect.

- **Simple** (a single module, a small utility, a narrow question such as "how does function X work"): no explorers. The main session explores and explains in a single pass. Go to Step 2b.
- **Complex** (a subsystem spanning multiple files or services, a cross-cutting feature, a full architectural overview): spawn parallel explorers first, then synthesize in the main session. Go to Step 2a.

When in doubt, take the simple path.

## Step 2a. Explore (complex questions only)

Decompose the question into 2 to 4 exploration angles, each a distinct slice of the subsystem. Spawn all explorers in a single message:

- `subagent_type`: `pstack:read-only`
- `model`: the `how explorer` line, default `sonnet`
- `effort`: explicitly pass the configured effort, default `low`
- read-only: enforced by `pstack:read-only` (no Edit/Write); still say "do not modify files" in the prompt

Each explorer gets the prompt in `references/explorer-prompt.md` with its angle filled in. Then go to Step 3.

## Step 2b. Direct Explain (simple questions)

The main session explores and explains directly; do not spawn an explainer. Follow `references/explainer-prompt.md` without the explorer-findings section. Go to Step 4.

## Step 3. Synthesize (complex questions only)

Once all explorers have returned, the main session synthesizes their findings. Follow `references/explainer-prompt.md` with every explorer's findings filled in.

## Step 4. Present

Present the main session's explanation to the user. Light edits for clarity or context from the conversation are fine. Do not substantially rewrite it.

## Output Format

The explanation uses the sections defined in `references/explainer-prompt.md`, dropping any that do not apply: Overview, Key Concepts, How It Works, Where Things Live, Gotchas.
