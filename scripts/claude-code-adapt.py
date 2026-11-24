#!/usr/bin/env python3
"""Re-apply the Claude Code adaptation to the upstream pstack tree.

Run it from the repo root after every upstream sync:

    python3 scripts/claude-code-adapt.py            # rewrite files in place
    python3 scripts/claude-code-adapt.py --check    # exit 1 if a rewrite is pending
    python3 scripts/claude-code-adapt.py --audit    # list leftover Cursor-only terms

The script is idempotent, so a second run changes nothing. It edits only files
that come from upstream. Files listed in claude-code/hand-owned.txt are skipped,
because they are maintained by hand in this fork.
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGIN = "pstack"

# Directories whose upstream skills are dropped from the Claude Code plugin.
# They move to cursor-only/ so `git merge` can follow upstream edits as renames.
CURSOR_ONLY_SKILLS = ["make-bot-ui"]

RUNTIME_POINTER = (
    "> **Claude Code:** read Cursor terms in this skill through "
    "[`claude-code/runtime.md`](${CLAUDE_PLUGIN_ROOT}/claude-code/runtime.md) "
    "(tools, subagents, models, transcripts)."
)


@dataclass
class Rule:
    name: str
    pattern: str
    repl: str
    files: tuple[str, ...] = ("skills/**/*.md", "agents/*.md", "docs/**/*.md")
    flags: int = 0


# Order matters: specific phrasings first, generic renames last.
RULES: list[Rule] = [
    # --- Models: upstream Cursor slugs -> Claude Code aliases ---------------
    Rule("reflect tooling seat",
         r"(\| Tooling \| `reflect tooling` \| )`gpt-5\.6-sol-max`", r"\1`sonnet`"),
    Rule("slug: grok", r"`?grok-4\.7-xhigh-fast`?", "`sonnet`"),
    Rule("slug: opus", r"`?claude-opus-5-5-max`?", "`opus`"),
    Rule("slug: sol", r"`?gpt-5\.6-sol-max`?", "`haiku`"),
    Rule("model families",
         r"Families go by prefix: `claude-\*`, `gpt-\*`, and `grok-\*`\.",
         "Families are Claude (`opus`, `sonnet`, `haiku`, `fable`, `claude-*`), `codex`, and `gemini`; see pstack's `claude-code/runtime.md`."),
    Rule("default panel prose", r"opus 5\.5 / sol / grok", "opus / sonnet / haiku"),
    Rule("code to grok prose", r"go to grok, while", "go to sonnet, while"),
    Rule("opus 5.5 prose", r"\bopus 5\.5\b", "opus"),

    # --- Config location ------------------------------------------------------
    Rule("rule path", r"~/\.cursor/rules/pstack-models\.mdc", "~/.claude/rules/pstack-models.md"),
    Rule("rule file", r"pstack-models\.mdc", "pstack-models.md"),

    # --- Subagent tool syntax -------------------------------------------------
    Rule("readonly true -> read-only agent",
         r"- `subagent_type`: `generalPurpose`\n((?:- .*\n)*?)- `readonly`: `true`",
         "- `subagent_type`: `pstack:read-only`\n\\1- read-only: enforced by `pstack:read-only` (no Edit/Write); still say \"do not modify files\" in the prompt"),
    Rule("why investigators readonly false",
         r"- `readonly`: `false` \(agent mode\)\. \*\*Do not use readonly/Ask mode\.\*\* It strips MCP access, which disables MCP-backed investigators entirely\.",
         "- tools: full (`general-purpose`, never `pstack:read-only` or `Explore`). Investigators need every MCP tool."),
    Rule("why synthesizer readonly false",
         r"- `readonly`: `false` \(agent mode\)\. The synthesizer's quality check spot-verifies citations, which can require MCP access\. Readonly/Ask mode strips MCPs and defeats that\.",
         "- tools: full (`general-purpose`). The synthesizer's quality check spot-verifies citations, which can require MCP access."),
    Rule("reflect agent mode", r"agent mode \(`readonly: false`\)", "full tool access (`general-purpose`, MCP included)"),
    Rule("poteto-mode agent mode", r"agent mode \(readonly strips MCP\)",
         "full tool access (`general-purpose` or `pstack:poteto-agent`, MCP included)"),
    Rule("generalPurpose", r"\bgeneralPurpose\b", "general-purpose"),
    Rule("poteto-agent subagent_type", r'subagent_type: "(?!pstack:)poteto-agent"', 'subagent_type: "pstack:poteto-agent"'),
    Rule("swarm cloud workers", r"parallel cloud workers", "parallel workers, each in its own git worktree"),
    Rule("swarm concurrency", r"not the cloud concurrency limit", "not the concurrent subagent limit"),
    Rule("environment cloud", r'`environment: "cloud"`', '`isolation: "worktree"`'),
    Rule("environment local",
         r'Use `environment: "local"` only when the worker needs access to something on the user\'s computer\.',
         "Omit `isolation` only when the worker must share the parent's checkout."),
    Rule("cloud_base_branch",
         r"When a worker must start from a non-default pushed branch, pass `cloud_base_branch`\.",
         "When a worker must start from a non-default pushed branch, tell it to fetch and check out that branch inside its worktree."),
    Rule("Task schema environment", r"full Task schema including `environment`", "full `Agent` schema including `isolation`"),
    Rule("Task tool", r"\bTask tool\b", "`Agent` tool"),
    Rule("Task subagent", r"\bTask subagent", "`Agent` subagent"),
    Rule("Task call", r"`Task` call", "`Agent` call"),
    Rule("Task model", r"Task `model`", "`Agent` `model`"),
    Rule("Task response", r"`Task` response", "`Agent` response"),
    Rule("Task calls", r"`Task` calls", "`Agent` calls"),
    Rule("AskQuestion", r"\bAskQuestion\b", "AskUserQuestion"),

    # --- Cursor built-ins -----------------------------------------------------
    Rule("create-skill builtin",
         r"the \*\*create-skill\*\* skill \(Cursor's built-in for authoring SKILL\.md files\)",
         "the `skill-creator` skill (Anthropic's, `/plugin install skill-creator@claude-plugins-official`; see pstack's `claude-code/runtime.md`)"),
    Rule("create-skill builtin 2", r"Cursor's built-in `create-skill`( skill)?",
         "the `skill-creator` skill (see pstack's `claude-code/runtime.md`)"),
    Rule("babysit builtin", r"not Cursor's built-in babysit skill, whose description matches the same words",
         "not any other installed babysit skill whose description matches the same words"),
    Rule("babysit builtin 2", r"This playbook replaces Cursor's built-in babysit skill for these requests",
         "This playbook replaces any other babysit skill for these requests"),
    Rule("loop builtin", r"Cursor's `/loop` command \(a built-in, not a pstack skill\)",
         "Claude Code's `/loop` bundled skill (not a pstack skill)"),
    Rule("cursor restart", r"a Cursor restart", "a Claude Code restart"),
    Rule("after cursor restart", r"After a Cursor restart", "After a Claude Code restart"),
    Rule("cursor dashboard", r"the cloud agent's status in the Cursor dashboard", "`/tasks`"),

    Rule("cursor cloud agent per PR", r"One Cursor cloud agent per PR", 'One background subagent per PR (`isolation: "worktree"`)'),
    Rule("each a cursor cloud agent", r"each a Cursor cloud agent,", 'each in its own worktree (`isolation: "worktree"`),'),
    Rule("loop hunt", r"Cursor's `/loop` command", "Claude Code's `/loop` bundled skill"),
    Rule("cloud agents local store",
         r"Cloud agents cannot read the local store, so their briefs inline",
         "Worktree agents do not see the coordinator's uncommitted state, so their briefs inline"),
    Rule("cursor worktrees example", r"`\.cursor/worktrees/myrepo/x`", "`.claude/worktrees/x`"),
    Rule("guide: loop builtin", r"`/loop` is Cursor's built-in wake mechanism", "`/loop` is Claude Code's bundled wake mechanism",
         files=("docs/**/*.md",)),

    Rule("live lane cloud VM", r"Each live lane runs on its own cloud VM at the PR head\.",
         'Each live lane runs in its own worktree (`isolation: "worktree"`) at the PR head.'),
    Rule("cloud-agent URL", r"\ba cloud-agent URL\b", "a Claude Code session id"),
    Rule("cloud-agent URL 2", r"cloud-agent URL,", "session id,"),
    Rule("plugin cache path", r"~/\.cursor/plugins/", "~/.claude/plugins/"),

    Rule("public copy URL", r"`https://github\.com/cursor/plugins/blob/main/pstack/`",
         "`https://github.com/anhermon/pstack-claude/blob/main/`"),

    # --- MCP discovery --------------------------------------------------------
    Rule("mcp discovery",
         r"list the available MCPs from the Cursor environment\. Use the available-tools map when present\. Otherwise inspect the `mcps/` directory Cursor exposes for enabled MCP servers\.",
         "list the available MCP servers. Their tools appear in your tool list as `mcp__<server>__<tool>`. `claude mcp list` in Bash also lists configured servers."),

    # --- Skill and transcript locations --------------------------------------
    Rule("user skills dir", r"~/\.cursor/skills/", "~/.claude/skills/"),
    Rule("project skills dir", r"(?<![~\w])\.cursor/skills/", ".claude/skills/"),
    Rule("transcript layout",
         r"`~/\.cursor/projects/<slug>/agent-transcripts/<uuid>/<uuid>\.jsonl`, where `<slug>` is the workspace path with the leading slash dropped and each \"/\" turned into \"-\" \(so `/Users/you/proj` becomes `Users-you-proj`\)",
         "`~/.claude/projects/<slug>/<uuid>.jsonl` (subagents under `<uuid>/subagents/`), where `<slug>` is the workspace path with each \"/\" (and other non-alphanumeric characters) turned into \"-\" (so `/Users/you/proj` becomes `-Users-you-proj`)"),
    Rule("transcripts glob", r"~/\.cursor/projects/\*/", "~/.claude/projects/*/"),
    Rule("system prompt names path (paren)", r"\(the system prompt names (?:this|the) path\)", "(see pstack's `claude-code/runtime.md`)"),
    Rule("system prompt names path (paren, open)", r"\(the system prompt names (?:this|the) path\.", "(see pstack's `claude-code/runtime.md`."),
    Rule("system prompt names dir",
         r"The system prompt names (?:the active workspace's|the workspace's) `agent-transcripts/` directory\.",
         "Claude Code keeps it under `~/.claude/projects/<project>/` (see pstack's `claude-code/runtime.md`)."),
    Rule("agent-transcripts dir", r"`agent-transcripts/` directory", "transcript directory (`~/.claude/projects/<project>/`)"),
    Rule("agent-transcripts placeholder", r"<agent-transcripts>", "~/.claude/projects/<project>"),
    Rule("agent-transcripts bare", r"local transcripts under `agent-transcripts/`", "local transcripts under `~/.claude/projects/`"),

    # --- worktree-audit.sh transcript lookup ----------------------------------
    Rule("audit transcripts comment",
         r"# Transcripts dir: ~/\.cursor/projects/<slugified-repo-path>/agent-transcripts\.",
         "# Transcripts dir: ~/.claude/projects/<repo-path with non-alphanumerics as ->.",
         files=("skills/poteto-mode/scripts/worktree-audit.sh",)),
    Rule("audit slug", r"sed 's#\^/##; s#/#-#g'", "sed 's#[^A-Za-z0-9]#-#g'",
         files=("skills/poteto-mode/scripts/worktree-audit.sh",)),
    Rule("audit transcripts dir", r'"\$HOME/\.cursor/projects/\$slug/agent-transcripts"', '"$HOME/.claude/projects/$slug"',
         files=("skills/poteto-mode/scripts/worktree-audit.sh",)),

    # --- poteto-help: Cursor-specific paragraphs ------------------------------
    Rule("help: built for cursor",
         r"pstack is built for Cursor\. Its skills use the Agent Skills format, so other tools can read them\. But most workflow skills, including `/poteto-mode`, `/how`, `/why`, and `/teach`, spawn Cursor subagents with per-role models, and Custom Modes and `/loop` are Cursor features, so those parts may not work there\.",
         "This is the Claude Code port of pstack (upstream is built for Cursor). Skills run as `/pstack:<name>`. Subagents use Claude model aliases per role, and `codex` or `gemini` seats when those CLIs are installed. [`claude-code/runtime.md`](../../claude-code/runtime.md) maps every Cursor term."),
    Rule("help: mode bullets",
         r"- Option\+Enter on Mac or Alt\+Enter on Windows, or Use as Mode from the skill entry, makes it a Custom Mode\. It stays in context every turn until the user exits the mode, and it stays out of casual turns\.\n- Cursor's docs list Custom Modes in the Agents Window and the CLI\. Elsewhere, start each new task with `/poteto-mode`\.\n\nLink \[Cursor's skills docs\]\(https://cursor\.com/docs/skills\) when this comes up\.",
         "- Claude Code has no Custom Modes. `/pstack:mode on` writes `.claude/pstack-mode`, and the plugin's hook then reminds every turn to apply `/poteto-mode` when a playbook matches. `/pstack:mode off` turns it off.\n- `claude --agent pstack:poteto-agent` runs a whole session as the poteto agent.\n\nLink [Claude Code's skills docs](https://code.claude.com/docs/en/skills) when this comes up."),
    Rule("help: not in pstack loop",
         r"- `/loop` and `/create-skill` are Cursor built-ins\.",
         "- `/loop` is a Claude Code bundled skill. Cursor's `/create-skill` maps to Anthropic's `skill-creator` plugin.\n- `make-bot-ui` and the benny automations are Cursor-only and are not in this port."),
    Rule("help: make-bot-ui row",
         r"\| Build a page whose buttons wake a Grok Bot over a webhook \| \[`/make-bot-ui`\]\(\.\./make-bot-ui/SKILL\.md\) \|\n",
         ""),
    Rule("help: cursor own skill", r"can start Cursor's own skill for the same job instead", "can start another installed skill for the same job instead"),
    Rule("help: plan mode", r"Cursor's Plan Mode works alongside it\.", "Claude Code's plan mode works alongside it."),
    Rule("help: custom mode fix",
         r"It was started with Enter\. Start it as a Custom Mode, or start each task with `/poteto-mode`\.",
         "Skill content fades as the chat grows. Run `/pstack:mode on`, or start each task with `/poteto-mode`."),
    Rule("help: rule applies", r"The rule from `/setup-pstack` applies to new chats\. Start one\.",
         "The rule from `/setup-pstack` loads at session start. Start a new session."),
    Rule("help: skill loading",
         r"Only `/setup-pstack` and `/poteto-help` load from the user's words\. The others load when the user types them or when `/poteto-mode` runs them, and it doesn't run every skill\.",
         "In Claude Code every pstack skill except `/setup-pstack` can load from the user's words, but Claude decides from each skill's description. Type the skill, or run `/poteto-mode`, to be sure."),
    Rule("help: cloud agents", r"or run them as cloud agents, which each get their own machine",
         "or spawn them with `isolation: \"worktree\"`"),
    Rule("help: swarm cloud", r"Run parallel checks over slices, or race workers, as cloud agents",
         "Run parallel checks over slices, or race workers, in isolated worktrees"),

    # --- Plugin-relative links into Cursor-only skills ------------------------
    Rule("README make-bot-ui link", r"\(\./skills/make-bot-ui/SKILL\.md\)", "(./cursor-only/make-bot-ui/SKILL.md)",
         files=("docs/**/*.md",)),

    # --- delegation-kit compatibility ---------------------------------------
    # These run AFTER the Cursor/tool/model renames above, on both fresh
    # upstream content and an already adapted checkout. Each replacement
    # consumes its old wording so a second pass has no pending rewrites.
    Rule("explicit spawn routing",
         r"(?:Each spawn below names|Each reviewer and the synthesizer name) a role line in the `pstack-models\.md` rule and a default\.[^\n]+",
         "Resolve each seat's explicit `model` and `effort` from delegation-kit's live routing table when its `Delegation routing (live` section is in context; otherwise use `pstack-models.md` and the defaults below. Map `auto`, `inherit-parent`, and `inherit` to `model: sonnet`, `effort: medium`. Always pass both parameters to `Agent`, including retries and resumes. For fan-outs of 3+ use sonnet/haiku seats, never opus. The main session owns final synthesis; any separately prescribed synthesizer runs alone after the fan-out."),
    Rule("swarm worker pins",
         r"4\. Pick the worker model[^\n]+",
         "4. Resolve the `swarm workers` model/effort pair from the live delegation-kit table when present, otherwise from `~/.claude/rules/pstack-models.md`; default `model: sonnet`, `effort: medium`. Map `auto`, `inherit-parent`, and `inherit` to that explicit pair. Fan-outs of 3+ use sonnet/haiku seats, never opus. Pass both fields on every call and retry. Name each race arm's pair up front.",
         files=("skills/swarm/SKILL.md",)),
    Rule("swarm spawn fields",
         r"and the step 4 model, left unset for `auto` or `inherit-parent`",
         "and explicit `model` plus `effort` from step 4"),
    Rule("reflect reviewer effort",
         r"with `model` set as below,",
         "with explicit `model` and `effort` set as below,"),
    Rule("reflect table effort header",
         r"\| Default `model` \| Prompt template \|",
         "| Default `model` / `effort` | Prompt template |"),
    Rule("reflect judgment seats",
         r"(\| (?:Judgment|Divergent) \| `reflect judgment, divergent, synthesizer` \| )`opus`",
         r"\1`sonnet` / `high`"),
    Rule("reflect tooling effort",
         r"(\| Tooling \| `reflect tooling` \| )`sonnet`( \|)",
         r"\1`sonnet` / `medium`\2"),
    Rule("reflect single synthesizer",
         r"with `model` from the `reflect judgment, divergent, synthesizer` line \(default `opus`\)",
         "with explicit `model` and `effort` from the `reflect judgment, divergent, synthesizer` line (single-seat default `opus` / `medium`, after all reviewers finish)"),
    Rule("arena runner pins",
         r"3\. Pick the runners\.[^\n]+",
         "3. Resolve the `arena runners` seats from delegation-kit's live table when present, otherwise `~/.claude/rules/pstack-models.md`. Default to `sonnet/medium`, `haiku/low`, `sonnet/medium`. Pass each pair as explicit `model` and `effort` parameters. Map `auto`, `inherit-parent`, and `inherit` to `sonnet/medium`; unsupported entries fall back to `sonnet/medium` and are reported. Fan-outs of 3+ use sonnet/haiku, never opus. External `codex`/`gemini` seats use the delegate routing in `claude-code/runtime.md`. Spawn more when the arena covers multiple design directions; repeated models are valid.",
         files=("skills/arena/SKILL.md",)),
    Rule("arena fanout fields",
         r"Spawn all N subagents in one message with `run_in_background: true`,",
         "Spawn all N subagents in one message with `subagent_type: general-purpose`, explicit `model` and `effort` from Phase A, `run_in_background: true`,"),
    Rule("arena single judge pins",
         r"Spawn one readonly judge subagent on that model\.",
         "Spawn one judge with `subagent_type: pstack:read-only`, explicit `model` set to that choice and explicit `effort: medium` (or the configured effort). Normalize inheritance aliases to `sonnet/medium`. The default single judge is `opus/medium`; external seats follow the runtime delegate routing."),
    Rule("architect runner pins",
         r"If the rule or that line is missing, use `opus`, `haiku`, `sonnet`\.",
         "If the rule or that line is missing, use `sonnet/medium`, `haiku/low`, `sonnet/medium`, passing explicit `model` and `effort` for each seat. Delegation-kit's live routing table takes precedence. Fan-outs of 3+ never use opus."),
    Rule("interrogate table effort",
         r"\| Default model \|", "| Default model / effort |",
         files=("skills/interrogate/SKILL.md",)),
    Rule("interrogate seats",
         r"\| Reviewer ([ABC]) \| `(opus|haiku|sonnet)` \|",
         # A and C have the same default; B stays the inexpensive seat.
         r"| Reviewer \1 | `\2` / `medium` |"),
    Rule("interrogate opus seat",
         r"\| Reviewer A \| `opus` / `medium` \|",
         "| Reviewer A | `sonnet` / `medium` |"),
    Rule("interrogate haiku effort",
         r"\| Reviewer B \| `haiku` / `medium` \|",
         "| Reviewer B | `haiku` / `low` |"),
    Rule("interrogate reviewer fields",
         r"- `model`: the configured `interrogate reviewers` entry[^\n]+",
         "- `model` and `effort`: resolve each `interrogate reviewers` pair from the live delegation-kit table when present, otherwise the rule or table defaults. Pass both explicitly. Normalize `auto`, `inherit-parent`, and `inherit` to `sonnet/medium`. Fan-outs of 3+ use sonnet/haiku, never opus."),
    Rule("explorer effort",
         r"(- `model`: the `how explorer` line, default `sonnet`)\n(?!- `effort`:)",
         r"\1\n- `effort`: explicitly pass the configured effort, default `low`\n"),
    Rule("investigator effort",
         r"(- `model`: the `why investigators` line, default `sonnet`)\n(?!- `effort`:)",
         r"\1\n- `effort`: explicitly pass the configured effort, default `medium`\n"),
    Rule("how simple main session",
         r"no explorers\. One explainer explores and explains in a single pass\.",
         "no explorers. The main session explores and explains in a single pass."),
    Rule("how complex main session",
         r"spawn parallel explorers first, then hand off to the explainer\.",
         "spawn parallel explorers first, then synthesize in the main session."),
    Rule("how direct explanation",
         r"Spawn one `Agent` subagent that explores and explains in one pass:\n\n- `subagent_type`: `pstack:read-only`\n- `model`: the `how explainer` line, default `opus`\n- read-only:[^\n]+\n\nBuild its prompt from",
         "The main session explores and explains directly; do not spawn an explainer. Follow"),
    Rule("how main synthesis",
         r"Once all explorers have returned, spawn one `Agent` subagent to synthesize their findings into one explanation:\n\n- `subagent_type`: `pstack:read-only`\n- `model`: the `how explainer` line, default `opus`\n- read-only:[^\n]+\n\nBuild its prompt from",
         "Once all explorers have returned, the main session synthesizes their findings. Follow"),
    Rule("how present main answer", r"Present the explainer's output to the user\.",
         "Present the main session's explanation to the user."),
    Rule("why main synthesis",
         r"Spawn one synthesizer subagent:\n\n- `subagent_type`: `general-purpose`\n- `model`: the `why synthesizer` line, default `opus`\n- tools:[^\n]+\n\nThe synthesizer gets:",
         "The main session synthesizes after all investigators finish; do not spawn another synthesizer. Spot-verify citations using the available tools. Use:"),
    Rule("no-comments agent",
         r'Spawn `Task` with `subagent_type: "Comment Sicko"`\.',
         'Spawn `Agent` with `subagent_type: "pstack:comment-sicko"`, explicit `model: haiku`, and `effort: low`.'),
    Rule("trail reviewer pins",
         r"Before handing back, spawn a subagent on a different model family from the one that did the work\.",
         "Before handing back, run one reviewer on a different model family when available: external codex/gemini seats follow the delegate routing in `claude-code/runtime.md`; otherwise spawn `Agent` with `subagent_type: pstack:read-only`, explicit `model: sonnet` and `effort: medium`. Resolve overrides from the live delegation-kit table when present, normalizing inheritance aliases to `sonnet/medium`."),
    Rule("recall cheap fanout pins",
         r"Spawn parallel subagents on a fast, cheap model,",
         "Spawn parallel `Agent` subagents with `subagent_type: pstack:read-only`, explicit `model: sonnet` and `effort: low` (or explicit sonnet/haiku pairs from the live delegation-kit table),"),
    Rule("poteto explicit subagent type",
         r'Use `subagent_type: "pstack:poteto-agent"` for any subagent',
         'Use `subagent_type: "pstack:poteto-agent"`, explicit `model: sonnet` and `effort: medium` (exploration/low-risk: `sonnet/low`, or the resolved role pair below) for any subagent'),
    Rule("poteto spawn defaults",
         r"\*\*Defaults for every `Agent` call\.\*\*[^\n]+",
         "**Required fields for every `Agent` call.** Pass explicit `model` AND `effort`, including retries, resumes, and nested delegates; effort is one of `low|medium|high|xhigh|max`. Default code roles and workers to `sonnet/medium`, exploration and low-risk helpers to `sonnet/low`. Fan-outs of 3+ use sonnet/haiku seats, never opus. The main session owns synthesis and judgment; opus is reserved for a single non-parallel judge with explicit effort (default `opus/medium`). Use `run_in_background: true`, full tool access (MCP included), and file pointers rather than inlined context. Resolve code roles from `feature, refactoring`, `bug-fix`, `perf-issue`, or `hillclimb`; other roles use their named lines. Map `auto`, `inherit-parent`, and `inherit` to explicit `sonnet/medium`.\n\n**Delegation-kit precedence.** If `Delegation routing (live` appears in context, defer to that live table for agent type, model and effort per role (for example `delegation-kit:implementer` or `delegation-kit:verifier`) instead of writing a competing configuration; use `pstack:poteto-agent` only when no such table or role fits. Do NOT write `~/.claude/rules/pstack-models.md`; tell the user delegation-kit owns routing and stop model configuration, while still offering `/pstack:mode on`. Without delegation-kit, `/setup-pstack` writes explicit model/effort pairs. Routed skills must also resolve the live table first."),
    Rule("playbook exploration effort",
         r"and an explicit model per the Subagents section",
         "and explicit `model: sonnet`, `effort: low` per the Subagents section"),
    Rule("playbook code role effort",
         r"using your configured (bug-fix|feature|refactoring|perf-issue|hillclimb) model \(default `sonnet`\)",
         r"using your configured \1 model/effort pair (default explicit `model: sonnet`, `effort: medium`, `subagent_type: pstack:poteto-agent`)"),
    Rule("multi-phase lane effort",
         r"on the `swarm workers` model \(default `sonnet`\)",
         "with explicit `model` and `effort` from `swarm workers` (default `sonnet/medium`)"),
    Rule("multi-phase verification effort",
         r"Ten lanes on `<swarm workers model>`",
         "Ten lanes with explicit `model` and `effort` from `<swarm workers model/effort>` (default `sonnet/medium`)"),
    Rule("cleanup fanout effort",
         r"fan subagents out to read the transcripts",
         "fan `Agent` subagents out with `subagent_type: pstack:read-only`, explicit `model: sonnet`, `effort: low` to read the transcripts"),
    Rule("opening PR agent pins",
         r"Multiple `Agent` calls on the same branch",
         "Multiple `Agent` calls (each with `subagent_type: pstack:poteto-agent`, explicit `model: sonnet`, `effort: medium`, or resolved role pair) on the same branch"),
    Rule("eval candidate pins",
         r"\*\*Spawn N parallel candidates\*\* on different models",
         "**Spawn N parallel candidates** with explicit `model` and `effort` per seat (default `sonnet/medium`, `haiku/low`, `sonnet/medium`; no opus in fan-outs of 3+)"),
    Rule("eval judge pins",
         r"\*\*Spawn one blinded judge\*\* on a different model family",
         "**Spawn one blinded judge** after all candidates finish, with explicit `model` and `effort` (default single seat `opus/medium`), preferring a different model family"),
    Rule("orchestrate spawn pins",
         r"Every spawn and every resume carries the standing orders verbatim\.",
         "Every spawn and resume passes explicit `model` and `effort` and carries the standing orders verbatim. Resolve each role from delegation-kit's live table when present, otherwise the pstack rule; default workers/sub-coordinators to `sonnet/medium`, low-risk verifiers/explorers to `sonnet/low`. Map inheritance aliases to `sonnet/medium`. Fan-outs of 3+ use sonnet/haiku, never opus. The main session synthesizes; a separate single judge may use `opus/medium` only after the wave finishes."),
    Rule("help leaf invocation policy",
         r"In Claude Code every pstack skill except `/setup-pstack` can load from the user's words,[^\n]+",
         "Routed pstack skills can load from the user's words or the Skill tool. The explicit-only leaf skills are `setup-pstack`, `blast-radius`, `bro`, `correct`, `recall`, `teach`, and `maintain-verification-skill`. Type those directly. `/poteto-mode`, `/poteto-help`, and `/automate-me` remain auto-invocable."),
    Rule("playbook agent contract",
         r"\A(#{1,6} [^\n]+\n)(?!\n> \*\*Agent parameters:)",
         r"\1\n> **Agent parameters:** every spawn, retry, resume, and nested delegate passes explicit `model` and `effort`. Resolve delegation-kit's live role table first, otherwise pstack's role pair: code `sonnet/medium`, exploration/low-risk `sonnet/low`. Inheritance aliases pin `sonnet/medium`. Fan-outs of 3+ use sonnet/haiku, never opus. The main session synthesizes; only a single judge after the fan-out may use `opus/medium`.\n",
         files=("skills/poteto-mode/playbooks/*.md",)),
    Rule("help direct poteto spawn pins",
         r'spawn it with `subagent_type: "pstack:poteto-agent"`\.',
         'spawn it with `subagent_type: "pstack:poteto-agent"`, explicit `model: sonnet` and `effort: medium` (or the resolved live role pair).'),
    Rule("help isolation spawn pins",
         r'or spawn them with `isolation: "worktree"`\.',
         'or spawn them with `isolation: "worktree"`, explicit `model: sonnet` and `effort: medium` (or resolved role pairs; sonnet/haiku for fan-outs of 3+).'),
    Rule("source playbook investigator pins",
         r"The why skill spawns one investigator per available evidence category,",
         "The why skill spawns one investigator per available evidence category with explicit `model: sonnet` and `effort: medium` (or the resolved live role pair),"),
]

# Drop Cursor-only keys. Keep disable-model-invocation only on explicit-only
# leaves; it blocks the Skill tool, so routed skills and poteto-mode must omit it.
DROP_SKILL_KEYS = {"mode", "icon", "color", "reminder"}
KEEP_DISABLE_MODEL_INVOCATION = {
    "setup-pstack", "blast-radius", "bro", "correct", "recall", "teach",
    "maintain-verification-skill",
}

AGENT_FRONTMATTER = {
    "agents/poteto-agent.md": {
        "rename": {"is_background": "background"},
        "set": {"model": "sonnet", "effort": "medium"},
        "add": [("skills", "\n  - pstack:poteto-mode"), ("model", " sonnet"), ("effort", " medium")],
    },
    "agents/comment-sicko.md": {
        "set": {"name": "comment-sicko", "model": "haiku", "effort": "low"},
        "add": [("tools", " Read, Grep, Glob, Edit, Bash, Skill, Agent"), ("model", " haiku"), ("effort", " low")],
    },
}
AGENT_BODY = {
    "agents/poteto-agent.md": [
        ("Spawn a fresh `poteto-agent` for each new task",
         "Spawn a fresh `poteto-agent` with explicit `model=sonnet` and `effort=medium` for each new task"),
        ("Read the `poteto-mode` skill's `SKILL.md` in full before doing any work",
         "Read the `poteto-mode` skill's `SKILL.md` (`${CLAUDE_PLUGIN_ROOT}/skills/poteto-mode/SKILL.md`, preloaded when available) in full before doing any work"),
    ],
}

FM_RE = re.compile(r"\A---\n(.*?)\n---\n", re.S)


def hand_owned() -> set[str]:
    path = ROOT / "claude-code" / "hand-owned.txt"
    lines = path.read_text().splitlines() if path.exists() else []
    return {l.strip() for l in lines if l.strip() and not l.startswith("#")}


def target_files(globs: tuple[str, ...], skip: set[str]) -> list[Path]:
    seen: dict[Path, None] = {}
    for g in globs:
        for p in sorted(ROOT.glob(g)):
            rel = p.relative_to(ROOT).as_posix()
            if p.is_file() and rel not in skip and not rel.startswith("cursor-only/") \
                    and "node_modules" not in p.parts:
                seen[p] = None
    return list(seen)


def fix_skill_frontmatter(path: Path, text: str) -> str:
    m = FM_RE.match(text)
    if not m:
        return text
    skill = path.parent.name
    out = []
    lines = m.group(1).split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        key = line.split(":", 1)[0] if re.match(r"^[A-Za-z_-]+:", line) else None
        if key in DROP_SKILL_KEYS or (key == "disable-model-invocation" and skill not in KEEP_DISABLE_MODEL_INVOCATION):
            i += 1
            while i < len(lines) and lines[i].startswith((" ", "\t")):
                i += 1
            continue
        if key == "name" and line.split(":", 1)[1].strip() != skill:
            line = f"name: {skill}"
        if key == "disable-model-invocation" and skill in KEEP_DISABLE_MODEL_INVOCATION:
            line = "disable-model-invocation: true"
        out.append(line)
        i += 1
    if skill in KEEP_DISABLE_MODEL_INVOCATION and not any(l.startswith("disable-model-invocation:") for l in out):
        out.append("disable-model-invocation: true")
    body = text[m.end():]
    if "**Claude Code:** read Cursor terms" not in body and needs_pointer(body):
        heading = re.search(r"^# .*\n", body, re.M)
        if heading:
            body = body[: heading.end()] + "\n" + RUNTIME_POINTER + "\n" + body[heading.end():]
        else:
            body = RUNTIME_POINTER + "\n\n" + body
    return "---\n" + "\n".join(out) + "\n---\n" + body


def needs_pointer(body: str) -> bool:
    return bool(re.search(r"subagent_type|`Agent`|pstack-models|AskUserQuestion|transcript|isolation|runtime\.md", body))


def fix_agent(rel: str, text: str) -> str:
    spec = AGENT_FRONTMATTER.get(rel)
    m = FM_RE.match(text)
    if spec and m:
        lines = m.group(1).split("\n")
        keys = {l.split(":", 1)[0] for l in lines if ":" in l and not l.startswith(" ")}
        new = []
        for l in lines:
            k = l.split(":", 1)[0]
            if k in spec.get("rename", {}):
                l = spec["rename"][k] + ":" + l.split(":", 1)[1]
            if k in spec.get("set", {}):
                l = f"{k}: {spec['set'][k]}"
            new.append(l)
        for k, v in spec.get("add", []):
            if k not in keys:
                new.append(f"{k}:{v}")
        text = "---\n" + "\n".join(new) + "\n---\n" + text[m.end():]
    for old, new in AGENT_BODY.get(rel, []):
        if new not in text:
            text = text.replace(old, new)
    return text


DOCS_BANNER = (
    "> **Claude Code port:** this guide is upstream's Cursor guide. Install with "
    "`/plugin marketplace add anhermon/pstack-claude` and `/plugin install pstack@pstack-claude`, "
    "run skills as `/pstack:<name>`, and read Cursor-only features (Custom Modes, cloud agents, "
    "`/add-plugin`) through [`claude-code/runtime.md`](../../claude-code/runtime.md)."
)


def add_docs_banner(get) -> list[str]:
    p = ROOT / "docs" / "guide" / "README.md"
    if not p.exists() or "Claude Code port:" in get(p):
        return []
    text = get(p)
    heading = re.search(r"^# .*\n", text, re.M)
    at = heading.end() if heading else 0
    return [(p, text[:at] + "\n" + DOCS_BANNER + "\n" + text[at:])]


def move_cursor_only(write: bool) -> list[str]:
    moved = []
    for name in CURSOR_ONLY_SKILLS:
        src, dst = ROOT / "skills" / name, ROOT / "cursor-only" / name
        if src.exists():
            moved.append(f"skills/{name} -> cursor-only/{name}")
            if write:
                dst.parent.mkdir(exist_ok=True)
                if dst.exists():
                    shutil.rmtree(dst)
                if subprocess.run(["git", "mv", str(src), str(dst)], cwd=ROOT, capture_output=True).returncode:
                    shutil.move(str(src), str(dst))
    return moved


def adapt(write: bool) -> list[str]:
    skip = hand_owned()
    changes = move_cursor_only(write)
    contents: dict[Path, str] = {}

    def get(p: Path) -> str:
        if p not in contents:
            contents[p] = p.read_text()
        return contents[p]

    for rule in RULES:
        rx = re.compile(rule.pattern, rule.flags)
        for p in target_files(rule.files, skip):
            if not write and any(r in p.as_posix() for r in CURSOR_ONLY_SKILLS):
                continue
            new, n = rx.subn(rule.repl, get(p))
            if n:
                contents[p] = new
                changes.append(f"{p.relative_to(ROOT)}: {rule.name} x{n}")

    for p in target_files(("skills/*/SKILL.md",), skip):
        new = fix_skill_frontmatter(p, get(p))
        if new != get(p):
            contents[p] = new
            changes.append(f"{p.relative_to(ROOT)}: frontmatter/pointer")

    for p, new in add_docs_banner(get):
        contents[p] = new
        changes.append(f"{p.relative_to(ROOT)}: docs banner")

    for rel in AGENT_FRONTMATTER:
        p = ROOT / rel
        if p.exists() and rel not in skip:
            new = fix_agent(rel, get(p))
            if new != get(p):
                contents[p] = new
                changes.append(f"{rel}: agent frontmatter")

    if write:
        for p, text in contents.items():
            if p.exists() and p.read_text() != text:
                p.write_text(text)
    return changes


# Terms that should not survive in loaded plugin content, with the reason a
# surviving match is acceptable. Anything not allowlisted fails --audit.
AUDIT_TERMS = re.compile(
    r"\bcursor|grok|gpt-5|\bsol\b|generalPurpose|readonly`|\bAskQuestion\b|\.mdc\b|option\+enter|alt\+enter|environment: \"|cloud agent|agent-transcripts",
    re.I,
)
AUDIT_ALLOW = [
    (r"cursor-team-kit", "optional companion plugin; runtime.md says how to cope without it"),
    (r"upstream is built for Cursor|maps every Cursor term|Cursor terms in this skill|Cursor's `/create-skill`|Cursor-only", "port notes"),
    (r"\bcursor(?: = | location|\))", "the word cursor as a text/pagination cursor"),
    (r">= cursor|login: \"cursor\"|endCursor|let cursor|const cursor|cursor = |cursor_automation_id|CURSOR_AUTOMATION_ID|author === \"cursor\"", "code identifiers in bundled scripts"),
    (r"@cursor-skill/", "npm package name of bundled scripts"),
    (r"Grok Bot", "Grok Bot is the operator's assistant name in examples"),
    (r"github\.com/cursor/plugins|`cursor/plugins`", "upstream attribution"),
    (r"Bugbot", "review bot whose PR comments the babysit playbook triages"),
    (r"Application Support/Cursor", "disk-cleanup hint for users who also run the Cursor app"),
    (r'verifier: "sol"', "test fixture string in bundled orch tests"),
]


# Files written for this fork. They mention Cursor only to say what they replace.
FORK_FILES = {"agents/read-only.md", "commands/mode.md", "hooks/hooks.json", "hooks/poteto-mode-reminder.sh"}


def audit() -> int:
    bad = 0
    globs = ("skills/**/*", "agents/*.md", "commands/*.md", "hooks/*")
    for p in target_files(globs, hand_owned() | FORK_FILES):
        if p.suffix in {".png", ".jpg", ".lock"}:
            continue
        for i, line in enumerate(p.read_text(errors="ignore").splitlines(), 1):
            for m in AUDIT_TERMS.finditer(line):
                window = line[max(0, m.start() - 60): m.end() + 60]
                if any(re.search(a, window) for a, _ in AUDIT_ALLOW):
                    continue
                bad += 1
                print(f"{p.relative_to(ROOT)}:{i}: {m.group(0)!r}: {line.strip()[:160]}")
    print(f"audit: {bad} unexplained Cursor-only reference(s) in loaded plugin content")
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="report pending rewrites, change nothing")
    ap.add_argument("--audit", action="store_true", help="list leftover Cursor-only references")
    args = ap.parse_args()
    if args.audit:
        return audit()
    changes = adapt(write=not args.check)
    for c in changes:
        print(c)
    if args.check:
        print(f"check: {len(changes)} pending rewrite(s)")
        return 1 if changes else 0
    print(f"applied {len(changes)} rewrite(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
