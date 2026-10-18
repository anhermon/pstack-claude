# pstack for Claude Code

A Claude Code port of **[pstack](https://github.com/cursor/plugins/tree/main/pstack)**, the plugin by [poteto (Lauren Tan)](https://x.com/poteto) published in [`cursor/plugins`](https://github.com/cursor/plugins). All of the skills, playbooks, principles, and prose are poteto's. This fork changes only what is tied to Cursor, so the same workflows install and run in Claude Code.

> "fork it. improve it. make it yours." (upstream README)

**Based on upstream:** `cursor/plugins@4e5b1cf2ccb0ea3716f08c8ee0a5856b5ab93536` (pstack 0.15.10, split-history commit `5db8d91e90d6063efd7754c11c11c5fd8df6e68d`, 2026-10-04). [UPSTREAM.md](./UPSTREAM.md) explains how to pull later upstream changes.

> if you want to go fast, go deep first. pstack helps you write less, but higher quality code. rigorous agent workflows you can parallelize with confidence. (poteto)

## Install

In Claude Code:

```text
/plugin marketplace add anhermon/pstack-claude
/plugin install pstack@pstack-claude
```

Or from a shell:

```bash
claude plugin marketplace add anhermon/pstack-claude
claude plugin install pstack@pstack-claude
claude plugin details pstack     # Skills (51) = 50 skills + the mode command; Agents (3); Hooks (1)
```

Requirements: Claude Code, and `git` with access to GitHub. `bun` is needed only for the poteto-mode helper CLIs (`watch-pr`, `orch`); on first run they install their one dependency (`commander`) from the lockfile, which needs network. `gh` is needed for the PR playbooks. Installing the plugin does not edit `~/.claude/settings.json` beyond the plugin entries Claude Code itself records.

To try a local checkout for one session: `claude --plugin-dir /path/to/pstack-claude`.

## Get started

1. Run `/pstack:setup-pstack`. With delegation-kit installed, pstack defers to its live routing table and does not write a competing model rule. Otherwise pick a budget and explicit model/effort pairs per role; setup writes `~/.claude/rules/pstack-models.md` for new sessions and subagents.
2. Use `/pstack:poteto-mode <task>` for anything that needs rigor. It matches the task to one of 23 playbooks and runs the other skills as the steps need them. Bare names such as `/poteto-mode` also work when no other command uses them.
3. Optional: `/pstack:mode on` keeps poteto-mode applying across turns in this project. This replaces Cursor's Custom Mode.

New here? Ask `/pstack:poteto-help`. The [pstack guide](./docs/guide/README.md) is upstream's Cursor guide. The workflows are the same, and [`claude-code/runtime.md`](./claude-code/runtime.md) translates the Cursor parts.

```text
/pstack:poteto-mode this pr has a subtle bug where the scroll drifts every 750ms even when idle. repro first, then fix and verify.
/pstack:how do we cancel runs? do we have an n+1 when we look up every run to cancel?
/pstack:interrogate review this pr.
```

## What's in it

- **`poteto-mode`** with 23 playbooks: investigation, bug fix, perf, hillclimb, runtime and trace forensics, feature, refactoring, prototype, visual parity, authoring a skill, eval, babysit, shipping, autonomous run, orchestrate, autopilot-full, autopilot-stack, session pickup, pause safely, multi-phase plan, worktree cleanup, and opening a PR.
- **Workflow skills:** `how`, `why`, `teach`, `architect`, `arena`, `swarm`, `interrogate`, `reflect`, `recall`, `figure-it-out`, `blast-radius`, `correct`, `tdd`, `benchmark-checklist`, `show-me-your-work`, `create-verification-skill`, `maintain-verification-skill`, `automate-me`, `no-comments`, `unslop`, `technical-writing`, `typescript-best-practices`, `bro`, `poteto-help`, `setup-pstack`.
- **24 `principle-*` skills** that poteto-mode cites (prove-it-works, fix-root-causes, model-the-domain, and others).
- **Agents:** `pstack:poteto-agent`, `pstack:comment-sicko`, and the fork-only `pstack:read-only`.
- **Command:** `/pstack:mode on|off|status [--global]`, fork-only.
- **Hook:** a `UserPromptSubmit` hook that prints the poteto-mode reminder only while the mode flag is on. It adds nothing to context otherwise.

## What changed from upstream

The adaptation is a small layer on top of upstream: a re-runnable codemod, one runtime mapping doc, two hand-rewritten files, and a few fork-only files. [UPSTREAM.md](./UPSTREAM.md) lists which file belongs to which group.

| Area | Upstream (Cursor) | This port (Claude Code) |
|---|---|---|
| Manifest | `.cursor-plugin/plugin.json` | `.claude-plugin/plugin.json`, plus `.claude-plugin/marketplace.json`, which makes this repo a single-plugin marketplace. `.cursor-plugin/` is left as is. |
| Skill frontmatter | `disable-model-invocation: true` on 52 skills; `mode`, `icon`, `color`, `reminder` on poteto-mode; display names with spaces | Keep the flag only on explicit-only leaves: `setup-pstack`, `blast-radius`, `bro`, `correct`, `recall`, `teach`, `maintain-verification-skill`. It hard-blocks the Skill tool, so all routed skills, including `poteto-mode`, `poteto-help`, and `automate-me`, remain auto-invocable. Cursor-only keys are dropped; names match directories. |
| Subagent calls | `Task` tool, `subagent_type: generalPurpose`, `readonly: true`, `environment: "cloud"` | `Agent` tool with explicit `model` AND `effort` on every spawn, retry, resume, and nested delegate; `general-purpose`, `pstack:read-only`, `isolation: "worktree"` |
| Agents | `poteto-agent` (`is_background`), `Comment Sicko` | `poteto-agent`: `background: true`, skill preload, `sonnet/medium`; `comment-sicko`: `haiku/low`; `read-only`: `sonnet/low`. Both model and effort are pinned in frontmatter. |
| Models | `claude-opus-5-5-max`, `gpt-5.6-sol-max`, `grok-4.7-xhigh-fast`; panel opus 5.5 / sol / grok | Code defaults to `sonnet/medium`, explorers to `sonnet/low`, panels to `sonnet/medium, haiku/low, sonnet/medium`. No opus in fan-outs of 3+; one later judge may use `opus/medium`. The main session synthesizes. External codex/gemini seats prefer delegation-kit (`codex`/`agy` harnesses), then CLI wrappers with explicit `haiku/low`. See [runtime.md](./claude-code/runtime.md#models). |
| Model config | `/setup-pstack` writes `~/.cursor/rules/pstack-models.mdc` | With delegation-kit, use its `Delegation routing (live` table and skip writing a pstack rule; `/pstack:mode` remains available. Otherwise write `~/.claude/rules/pstack-models.md` with model/effort pairs per role. Inheritance aliases normalize to explicit `sonnet/medium`. |
| Effort | Encoded in model slugs | `Agent` accepts explicit `effort: low\|medium\|high\|xhigh\|max`; budgets choose effort per role/seat, passed alongside model. |
| Custom mode (option+enter) | Keeps poteto-mode in context every turn | `/pstack:mode on` and the `UserPromptSubmit` hook, or `claude --agent pstack:poteto-agent` |
| `/loop` | Cursor built-in | Claude Code's bundled `/loop` (same name, same role) |
| `create-skill`, built-in `babysit` | Cursor built-ins | Anthropic's `skill-creator` plugin. Babysit is the playbook only. |
| Transcripts | `~/.cursor/projects/<slug>/agent-transcripts/` | `~/.claude/projects/<project>/<session>.jsonl` (recall, reflect, automate-me, eval, session-pickup, show-me-your-work, worktree-audit.sh) |
| MCP discovery (`why`) | Cursor's `mcps/` directory | `mcp__<server>__<tool>` tools and `claude mcp list` |
| Skill paths | `.cursor/skills/`, `~/.cursor/skills/` | `.claude/skills/`, `~/.claude/skills/` |

### Skills, agents, and automations

- **Ported with mechanical edits (49 skills):** every skill under `skills/` except the two below. The codemod changes tool names, model aliases, config and transcript paths, and frontmatter. The prose is otherwise upstream's.
- **Rewritten (1 skill):** `setup-pstack`. It defers to delegation-kit's live routing when present; otherwise it detects models and external runners, maps the budget to model/effort pairs, writes the Claude Code rule, and offers `/pstack:mode`.
- **Edited in place:** `poteto-help`, where the paragraphs on Cursor, Custom Modes, and cloud agents are replaced through codemod rules. `docs/guide/` gets a banner plus path and model renames. The guide is otherwise Cursor prose.
- **Dropped (Cursor-only, kept in [`cursor-only/`](./cursor-only/README.md)):** `make-bot-ui`. It drives Cursor Automations webhooks and a Cursor-hosted bot.
- **Not ported:** the [benny automation pack](./automations/benny/) (Slack-triggered Cursor Automations). It was never loaded as plugin skills, and it is left unchanged. [automations/CLAUDE-CODE.md](./automations/CLAUDE-CODE.md) sketches a headless `claude -p` port.
- **Agents:** `poteto-agent` and `comment-sicko` converted, plus the new `read-only`.
- **Kept, conditional on your setup:** Origin (`origin` CLI, used only when `command -v origin` succeeds, otherwise `gh`), Bugbot triage (it applies to any review bot's PR comments), and `cursor-team-kit` references (`/deslop`, `control-ui`, `control-cli`). [runtime.md](./claude-code/runtime.md#not-available-in-claude-code) says what to do without them.

### Caveats

- The default panel repeats sonnet alongside haiku, giving less independent signal than upstream's three vendors. Add `codex` or `gemini` seats through delegation-kit or installed CLIs.
- Seven explicit-only leaf skills keep `disable-model-invocation` to avoid loading their descriptions on every turn. Routed skills keep their descriptions available so the Skill tool and poteto-mode routing work; Claude may load them when their descriptions match. The adapter and frontmatter check enforce the same seven-skill allowlist.
- The agent preload `skills: [pstack:poteto-mode]` uses the plugin-scoped skill name. If your Claude Code version expects another form, the agent still reads the file through its `${CLAUDE_PLUGIN_ROOT}` path.
- `orchestrate`, `autopilot-*`, and `swarm` were designed around Cursor cloud agents. Here they run as local background subagents in git worktrees, capped by Claude Code's concurrent-subagent limit (20 by default), and they stop when the session ends.

## Development

```bash
python3 scripts/claude-code-adapt.py           # re-apply the codemod (idempotent)
python3 scripts/claude-code-adapt.py --audit   # list leftover Cursor-only references
scripts/check.sh                               # validate --strict, frontmatter, codemod check, audit
scripts/sync-upstream.sh                       # merge upstream pstack, then re-adapt
```

## Attribution and license

- pstack: © 2026 Lauren Tan ([poteto](https://github.com/poteto)), from [`cursor/plugins`](https://github.com/cursor/plugins/tree/main/pstack), MIT. The upstream commit history and authorship are kept in this repo.
- Claude Code adaptation: Angel Hermon ([@anhermon](https://github.com/anhermon)), under the same MIT license.

See [LICENSE](./LICENSE). This port is unofficial and not affiliated with or endorsed by Cursor, Anysphere, or Anthropic.
