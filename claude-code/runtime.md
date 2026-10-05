# pstack on Claude Code: runtime mapping

pstack's skills were written for Cursor. This port keeps their prose and rewrites only the Cursor-specific parts, mostly through `scripts/claude-code-adapt.py`. When a skill still says something that only makes sense in Cursor, read it through this table. This file wins over any leftover Cursor wording.

## Tools

| Skill text says | In Claude Code |
|---|---|
| `Task` tool, `Task` call | The `Agent` tool. Pass `subagent_type`, `description`, `prompt`, and optionally `model`, `run_in_background`, `isolation`. |
| `subagent_type: generalPurpose` | `subagent_type: general-purpose` (built in, inherits every tool, MCP included). |
| `readonly: true` | `subagent_type: pstack:read-only`, this plugin's agent with `Edit`, `Write`, and `NotebookEdit` removed. Bash stays, so the prompt must still say "do not modify files". |
| `readonly: false` / agent mode | `general-purpose` or `pstack:poteto-agent`. Do not set `tools`, so MCP tools stay available. |
| `subagent_type: "poteto-agent"` | `subagent_type: "pstack:poteto-agent"` (plugin agents are namespaced). |
| `environment: "cloud"` | `isolation: "worktree"`: each worker gets its own temporary git worktree. Claude Code subagents always run on this machine, so a worker can read local files and transcripts. |
| `environment: "local"` | Omit `isolation`. |
| `cloud_base_branch` | Tell the worker in its brief to `git fetch` and check out that branch inside its worktree. |
| `AskQuestion` | `AskUserQuestion`. |
| todo list | `TodoWrite`, or the task tools when the session has them. |
| Cursor's built-in `create-skill` | Anthropic's `skill-creator` skill if installed (`/plugin install skill-creator@claude-plugins-official`). Otherwise follow the Claude Code skills docs: `SKILL.md` with `name` and `description` frontmatter. |
| Cursor's built-in `/babysit` | Claude Code has none. The Babysit playbook is the only one. |
| `/loop` | Claude Code ships a `/loop [interval] [prompt]` bundled skill with the same role: `/loop 1h <tick prompt>`, or `/loop <prompt>` to let Claude pick the interval. It lives only while the session stays open. For unattended runs that outlive the terminal, use cloud routines or `claude -p` from cron or CI. |
| Custom mode (option+enter) | No direct equivalent. Run `/pstack:mode on` (writes `.claude/pstack-mode`). The plugin's `UserPromptSubmit` hook then re-injects the poteto-mode reminder every turn. `/pstack:mode off` removes it. |
| Cursor Plan Mode | Claude Code plan mode (Shift+Tab). |
| Cursor dashboard, cloud agent status | `/tasks` shows running subagents and background tasks. |
| Cursor restart | Claude Code restart or `/clear`. Background subagents die with the session. |
| Cursor's `mcps/` directory or available-tools map | MCP tools appear as `mcp__<server>__<tool>` in your tool list. `claude mcp list` in Bash lists configured servers. |

## Transcripts

Cursor keeps transcripts under `~/.cursor/projects/<slug>/agent-transcripts/`. Claude Code keeps them under `~/.claude/projects/<project>/`:

- `<session-id>.jsonl` is one chat, one JSON object per line.
- `<session-id>/subagents/agent-<id>.jsonl` holds that chat's subagents.
- `<project>` is the working directory with each `/` (and other non-alphanumeric characters) turned into `-`, so `/Users/you/proj` becomes `-Users-you-proj`. If unsure, `ls -t ~/.claude/projects/ | head` and match on the path.

Read only the active project's directory unless the user names another one.

## Models

`/setup-pstack` writes `~/.claude/rules/pstack-models.md`. Claude Code loads every file in `~/.claude/rules/` into every session and subagent, which is how Cursor's always-applied `~/.cursor/rules/pstack-models.mdc` worked. Each role line holds a value for the `Agent` tool's `model` parameter.

| Value | Meaning |
|---|---|
| `opus`, `sonnet`, `haiku`, `fable` | Claude model aliases. `fable` is the largest model and may not be enabled on every account. |
| a full model id, such as `claude-opus-5-5` | That exact model. |
| `inherit`, `inherit-parent`, `auto` | Omit `model`, so the subagent runs on the main conversation's model. |
| `codex`, `gemini` | An external CLI runner. See below. |

Defaults, used when the rule or a line is missing:

| Role | Default | Upstream Cursor default |
|---|---|---|
| code roles (`feature, refactoring`, `bug-fix`, `perf-issue`, `hillclimb`), `how explorer`, `why investigators`, `swarm workers`, `reflect tooling` | `sonnet` | grok / gpt (sol) |
| `judgment and prose`, `hardest tasks`, `how explainer`, `why synthesizer`, `reflect judgment, divergent, synthesizer` | `opus` | opus 5.5 |
| panels: `arena runners`, `arena cross-judge pool`, `architect runners`, `interrogate reviewers` | `opus, sonnet, haiku` | opus 5.5, sol, grok |

**Model families.** Where a skill says to fall back "within the family" or to pick "a different family", the families are: Claude (`opus`, `sonnet`, `haiku`, `fable`, `claude-*`), `codex` (OpenAI), and `gemini` (Google). With only Claude aliases, a panel is three different Claude models. That is less diverse than upstream's three vendors, so agreement means less. Add `codex` or `gemini` to a panel line when those CLIs are installed.

**Effort.** Upstream encodes reasoning effort in the model slug (`-max`, `-xhigh`). Claude Code subagents inherit the session's effort level (`/effort`). The setup budget picks model tiers and records the effort to use. It does not rewrite slugs.

### External CLI runners (`codex`, `gemini`)

A panel or role entry of `codex` or `gemini` means "run this seat on that vendor's CLI". Use it only when `command -v codex` or `command -v gemini` succeeds. Otherwise drop the seat and say so. To run the seat, spawn an `Agent` with `subagent_type: general-purpose` and `model: haiku`. For a seat that writes code, also pass `isolation: "worktree"`. Its whole job is:

1. Write the seat's brief to a temp file, unchanged from the brief the Claude seats get.
2. Run the CLI non-interactively from the seat's working directory:
   - Codex, read-only seat (reviewer, judge): `codex exec --sandbox read-only "$(cat brief.md)"`
   - Codex, writing seat (arena or architect runner): `codex exec --sandbox workspace-write "$(cat brief.md)"`
   - Gemini, read-only seat: `gemini -p "$(cat brief.md)"`
   - Gemini, writing seat: `gemini --yolo -p "$(cat brief.md)"`. Only run this inside the worktree.
3. Return the CLI's final answer word for word, plus `git diff` for a writing seat. The wrapper must not add its own review.

CLI flags change between releases. If one fails, run `codex exec --help` or `gemini --help` and adjust, rather than dropping the seat without trying.

## Not available in Claude Code

- `cursor-team-kit` skills (`/deslop`, `control-cli`, `control-ui`). Use them if you have installed a port. Otherwise do the step by hand: deslop means re-reading the diff for slop with **unslop** and **no-comments**, and a control skill means driving the real app through Bash, a browser MCP, or the project's `verify-*` skill.
- Origin (`origin` CLI). The playbooks already check `command -v origin` and fall back to `gh`.
- Cursor Automations and their webhooks (`make-bot-ui`, the benny pack). See the README.
- Bugbot is Cursor's PR review bot. The triage reference applies to any review bot's PR comments, so it stays.
