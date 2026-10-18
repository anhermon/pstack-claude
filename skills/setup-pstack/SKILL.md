---
name: setup-pstack
description: Configure which models pstack uses per role and at what reasoning budget. Detects your available Claude models and external CLIs (codex, gemini) and writes an always-loaded Claude Code rule that overrides the skill defaults. Use for /setup-pstack, "configure pstack models", "pstack budget", or changing pstack's model choices.
disable-model-invocation: true
---

# Setup pstack

Configure explicit model/effort pairs per role. Without delegation-kit, write `~/.claude/rules/pstack-models.md`, a user-level rule loaded into every session and subagent. Read [`claude-code/runtime.md`](${CLAUDE_PLUGIN_ROOT}/claude-code/runtime.md) for what each value means.

> Hand-maintained Claude Code port of upstream `setup-pstack`. The upstream version writes `~/.cursor/rules/pstack-models.mdc` with Cursor model slugs.

## Steps

### 0. Respect delegation-kit routing

If the prompt section `Delegation routing (live` appears in context, delegation-kit is installed and owns model/effort routing. Defer to that live table per role. Do NOT write `~/.claude/rules/pstack-models.md`. Tell the user that delegation-kit's live routing will be used, still offer `/pstack:mode on` (step 6), and stop model configuration here. Otherwise continue below.

### 1. Detect available models

- Claude models: the aliases `opus`, `sonnet`, and `haiku` always resolve. `fable` resolves only when the account has Fable enabled. Ask the user if unsure, or check `/model`. Full model IDs such as `claude-opus-5-5` are valid when the user names them. The `availableModels` allowlist in the user's settings, if set, limits what works, so read `~/.claude/settings.json` and drop anything it excludes.
- External runners: load ToolSearch `select:mcp__delegation-kit__delegate` when available; codex uses harness `codex`, gemini uses harness `agy`. Otherwise run `command -v codex` and `command -v gemini` and offer only installed CLI seats. Follow the runtime's worktree and `wait: true` contract; fallback wrapper agents pass explicit `model: haiku`, `effort: low`.
- Normalize the legacy aliases `inherit`, `inherit-parent`, and `auto` to explicit `model: sonnet`, `effort: medium`. Never omit either parameter.

Never write a value you have not confirmed is available.

### 2. Load current state

The default role-to-model mapping is the rule shape shown in step 5 below. If `~/.claude/rules/pstack-models.md` already exists, read it and treat its `budget:` line and its role values as the current choices. Otherwise start from those defaults. A line whose role is not in step 5, such as `how critics`, is from a retired role. Drop it. If the user also has a Cursor rule at `~/.cursor/rules/pstack-models.mdc`, mention it, but do not copy Cursor slugs across.

### 3. Budget, map, and confirm

**(a) Ask for a budget.** Prefer `AskUserQuestion` over free text. Offer these four options with these exact labels, and name the current budget when the rule records one.

- `unlimited — max effort`
- `large — xhigh effort`
- `medium — high effort`
- `small — medium effort`

**(b) Apply it.** The `Agent` tool accepts explicit `model` and `effort` (`low|medium|high|xhigh|max`). Record both for every seat. Pass them on every spawn, retry, resume, and nested delegation.

The budget maps to per-role effort below. Keep prior role choices that satisfy the fan-out policy. Explorers and low-risk helpers stay `sonnet/low`; haiku seats stay `haiku/low`. The main session handles explanation and final synthesis. Only a single non-parallel judge after the fan-out may use opus, always with explicit effort. Fan-outs of 3+ use sonnet/haiku seats, never opus, including configured and retry seats.

| Budget | single judge | code roles | panels (model/effort per seat) |
|---|---|---|---|
| `unlimited` | `opus/max` | `sonnet/max` | `sonnet/max, haiku/low, sonnet/max`, plus detected external seats |
| `large` | `opus/xhigh` | `sonnet/xhigh` | `sonnet/xhigh, haiku/low, sonnet/xhigh` |
| `medium` | `opus/high` | `sonnet/high` | `sonnet/high, haiku/low, sonnet/high` |
| `small` | `sonnet/medium` | `sonnet/medium` | `sonnet/medium, haiku/low, sonnet/medium` |

Code roles are the four code playbook lines, `hardest tasks`, `why investigators`, `reflect tooling`, and `swarm workers`. `how explorer` uses `sonnet/low`. `judgment and prose`, `how explainer`, and `why synthesizer` run in the main session. The shared `reflect judgment, divergent, synthesizer` line uses sonnet for parallel reviewers (default effort `high`) and the single-judge pair only for the later synthesizer. Panels are `arena runners`, `architect runners`, and `interrogate reviewers`. `arena cross-judge pool` lists choices for just one later judge, never a fan-out.

**(c) Show the roles and confirm.** Show every role with its model/effort pair (or `main session`), marking unavailable models as needing a choice. List retired lines dropped in step 2. Ask whether to accept or change specific roles, offering detected models and external seats. Prefer `AskUserQuestion`. Each panel entry adds one seat; `arena cross-judge pool` instead selects one later judge, preferably from a different family. `codex` and `gemini` are separate families. `swarm workers` sets each worker's pair unless a race assigns explicit pairs per arm.

### 4. Validate

Every agent seat must have an available model and a valid explicit effort. Normalize legacy inheritance aliases to `sonnet/medium`. Validate the fan-out limits above. If a chosen model is unavailable, stop and ask again.

### 5. Write the rule

Create `~/.claude/rules/` if needed. Write `~/.claude/rules/pstack-models.md` with a `budget:` line and one line per role, using the same labels poteto-mode uses. Overwrite the whole file so re-runs stay idempotent. Do not add a `paths` frontmatter field, because a path-scoped rule loads only for matching files. Shape (the `large` defaults):

```
# pstack model configuration (Claude Code)

Per-role model/effort pairs for pstack skills. Pass both explicit parameters to `Agent`. Delete a line to use the runtime default.
Normalize `inherit`, `inherit-parent`, or `auto` to explicit `sonnet/medium`. `codex` or `gemini` uses the runtime's delegate routing (harness codex or agy), falling back to a CLI wrapper with explicit haiku/low. Every panel entry adds one seat. No opus in fan-outs of 3+; opus is only for one later judge. Main session roles never spawn another agent.

budget: large (xhigh effort)
feature, refactoring: sonnet/xhigh
bug-fix: sonnet/xhigh
perf-issue: sonnet/xhigh
hillclimb: sonnet/xhigh
judgment and prose: main session
hardest tasks: sonnet/xhigh
how explorer: sonnet/low
how explainer: main session
why investigators: sonnet/xhigh
why synthesizer: main session
reflect tooling: sonnet/xhigh
reflect judgment, divergent, synthesizer: reviewers sonnet/high; single synthesizer opus/xhigh
arena runners: sonnet/xhigh, haiku/low, sonnet/xhigh
arena cross-judge pool: opus/xhigh, sonnet/xhigh, haiku/low
swarm workers: sonnet/xhigh
architect runners: sonnet/xhigh, haiku/low, sonnet/xhigh
interrogate reviewers: sonnet/xhigh, haiku/low, sonnet/xhigh
```

Write the rule body as plain Markdown, with no code fence around it.

### 6. Optional: keep poteto-mode on (Custom Mode equivalent)

Ask once whether the user wants `/poteto-mode` applied on every new task in this project. On yes, tell them to run `/pstack:mode on`. It writes `.claude/pstack-mode`, and the plugin's `UserPromptSubmit` hook then injects the poteto-mode reminder on every turn. `/pstack:mode off` removes it. For a global default, `/pstack:mode on --global` writes `~/.claude/pstack-mode` instead.

### 7. Confirm

Tell the user the rule was written and that Claude Code loads it at session start, so it applies to new sessions. Re-running this skill updates it.

### 8. Offer a verification skill (optional)

Check whether the project has a way to drive the real app for proof (a `verify-*` skill, or an existing harness). If not, offer once: "want a project-local verification skill, so agents can drive the app the way a user does and prove changes work? I can generate one with /create-verification-skill." On yes, invoke `/pstack:create-verification-skill`. On no, move on without pushing.
