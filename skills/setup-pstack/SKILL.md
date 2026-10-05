---
name: setup-pstack
description: Configure which models pstack uses per role and at what reasoning budget. Detects your available Claude models and external CLIs (codex, gemini) and writes an always-loaded Claude Code rule that overrides the skill defaults. Use for /setup-pstack, "configure pstack models", "pstack budget", or changing pstack's model choices.
disable-model-invocation: true
---

# Setup pstack

Write `~/.claude/rules/pstack-models.md`, a user-level Claude Code rule that sets pstack's model per role. Claude Code loads every file in `~/.claude/rules/` into every session and every subagent, so the rule works like upstream's always-applied Cursor rule. Read [`claude-code/runtime.md`](${CLAUDE_PLUGIN_ROOT}/claude-code/runtime.md) for what each value means.

> Hand-maintained Claude Code port of upstream `setup-pstack`. The upstream version writes `~/.cursor/rules/pstack-models.mdc` with Cursor model slugs.

## Steps

### 1. Detect available models

- Claude models: the aliases `opus`, `sonnet`, and `haiku` always resolve. `fable` resolves only when the account has Fable enabled. Ask the user if unsure, or check `/model`. Full model IDs such as `claude-opus-5-5` are valid when the user names them. The `availableModels` allowlist in the user's settings, if set, limits what works, so read `~/.claude/settings.json` and drop anything it excludes.
- External CLIs: run `command -v codex` and `command -v gemini`. Offer `codex` or `gemini` as panel seats only when the CLI is present.
- The aliases `inherit`, `inherit-parent`, and `auto` are always valid. All three mean: omit `model`, so the subagent runs on the main conversation's model.

Never write a value you have not confirmed is available.

### 2. Load current state

The default role-to-model mapping is the rule shape shown in step 5 below. If `~/.claude/rules/pstack-models.md` already exists, read it and treat its `budget:` line and its role values as the current choices. Otherwise start from those defaults. A line whose role is not in step 5, such as `how critics`, is from a retired role. Drop it. If the user also has a Cursor rule at `~/.cursor/rules/pstack-models.mdc`, mention it, but do not copy Cursor slugs across.

### 3. Budget, map, and confirm

**(a) Ask for a budget.** Prefer `AskUserQuestion` over free text. Offer these four options with these exact labels, and name the current budget when the rule records one.

- `unlimited — max effort`
- `large — xhigh effort`
- `medium — high effort`
- `small — medium effort`

**(b) Apply it.** Claude Code subagents inherit the session's effort level, and the `Agent` tool has no per-call effort setting. So the budget does two things:

1. It records the target effort on the `budget:` line. Tell the user to set it with `/effort <level>`, which saves it as their default for the current model.
2. It picks model tiers. Keep any role the user changed on a previous run.

| Budget | judgment roles | code roles | panels |
|---|---|---|---|
| `unlimited` | `opus` (`fable` for `hardest tasks` if available) | `sonnet` | `opus, sonnet, haiku`, plus each detected CLI |
| `large` | `opus` | `sonnet` | `opus, sonnet, haiku` |
| `medium` | `opus` | `sonnet` | `opus, sonnet` |
| `small` | `sonnet` | `haiku` | `sonnet, haiku` |

Judgment roles are `judgment and prose`, `hardest tasks`, `how explainer`, `why synthesizer`, and `reflect judgment, divergent, synthesizer`. Code roles are the four code playbook lines, `how explorer`, `why investigators`, `reflect tooling`, and `swarm workers`. Panels are `arena runners`, `arena cross-judge pool`, `architect runners`, and `interrogate reviewers`.

**(c) Show the roles and confirm.** Show every role with its value, and mark any value not in the detected set as needing a choice. Also list each line step 2 dropped. Ask whether to accept as-is or change specific roles. Offer the detected aliases and CLIs plus `inherit` as options. Prefer `AskUserQuestion` over free text. For panel roles the value is a list, and one subagent runs per entry, `inherit` entries included, so the list length sets the count. `arena cross-judge pool` is also a list, but Arena picks one value from it, from a different model family than the parent's when possible. `codex` and `gemini` count as their own families. `swarm workers` is the default model for every worker unless a race or comparison assigns another model per arm.

### 4. Validate

Every value written must be in the detected set or be an `inherit` alias. If a chosen value is not available, stop and ask again.

### 5. Write the rule

Create `~/.claude/rules/` if needed. Write `~/.claude/rules/pstack-models.md` with a `budget:` line and one line per role, using the same labels poteto-mode uses. Overwrite the whole file so re-runs stay idempotent. Do not add a `paths` frontmatter field, because a path-scoped rule loads only for matching files. Shape (the `large` defaults):

```
# pstack model configuration (Claude Code)

Per-role models for pstack skills. Each value is the `model` parameter for the `Agent` tool. Delete a line to fall back to the skill default.
`inherit`, `inherit-parent`, or `auto`: omit `model`, so the role runs on the main conversation's model. `codex` or `gemini`: an external CLI seat (see pstack's claude-code/runtime.md). Each panel entry, aliases included, adds one subagent.

budget: large (xhigh effort)
feature, refactoring: sonnet
bug-fix: sonnet
perf-issue: sonnet
hillclimb: sonnet
judgment and prose: opus
hardest tasks: opus
how explorer: sonnet
how explainer: opus
why investigators: sonnet
why synthesizer: opus
reflect tooling: sonnet
reflect judgment, divergent, synthesizer: opus
arena runners: opus, sonnet, haiku
arena cross-judge pool: opus, sonnet, haiku
swarm workers: sonnet
architect runners: opus, sonnet, haiku
interrogate reviewers: opus, sonnet, haiku
```

Write the rule body as plain Markdown, with no code fence around it.

### 6. Optional: keep poteto-mode on (Custom Mode equivalent)

Ask once whether the user wants `/poteto-mode` applied on every new task in this project. On yes, tell them to run `/pstack:mode on`. It writes `.claude/pstack-mode`, and the plugin's `UserPromptSubmit` hook then injects the poteto-mode reminder on every turn. `/pstack:mode off` removes it. For a global default, `/pstack:mode on --global` writes `~/.claude/pstack-mode` instead.

### 7. Confirm

Tell the user the rule was written and that Claude Code loads it at session start, so it applies to new sessions. Re-running this skill updates it.

### 8. Offer a verification skill (optional)

Check whether the project has a way to drive the real app for proof (a `verify-*` skill, or an existing harness). If not, offer once: "want a project-local verification skill, so agents can drive the app the way a user does and prove changes work? I can generate one with /create-verification-skill." On yes, invoke `/pstack:create-verification-skill`. On no, move on without pushing.
