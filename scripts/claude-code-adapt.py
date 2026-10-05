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
]

# Frontmatter keys that only Cursor reads. `disable-model-invocation` is dropped
# because in Claude Code it blocks the Skill tool outright, which breaks
# poteto-mode's routing into how/why/interrogate/principle-* and stops
# poteto-agent from preloading poteto-mode.
DROP_SKILL_KEYS = {"mode", "icon", "color", "reminder"}
KEEP_DISABLE_MODEL_INVOCATION = {"setup-pstack"}

AGENT_FRONTMATTER = {
    "agents/poteto-agent.md": {
        "rename": {"is_background": "background"},
        "add": [("skills", "\n  - pstack:poteto-mode")],
    },
    "agents/comment-sicko.md": {
        "set": {"name": "comment-sicko"},
        "add": [("tools", " Read, Grep, Glob, Edit, Bash, Skill, Agent"), ("model", " inherit")],
    },
}
AGENT_BODY = {
    "agents/poteto-agent.md": [
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
        out.append(line)
        i += 1
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
