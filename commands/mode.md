---
description: Turn pstack mode on or off. When on, every turn is reminded to apply /poteto-mode, the Claude Code equivalent of running poteto-mode as a Cursor Custom Mode.
argument-hint: "on|off|status [--global]"
disable-model-invocation: true
allowed-tools: Bash(mkdir -p *), Bash(touch *), Bash(rm -f *), Bash(ls *)
---

Arguments: `$ARGUMENTS`

pstack mode is a flag file that the pstack `UserPromptSubmit` hook checks on every prompt. While the flag exists, the hook adds this reminder to each turn: "New task? Playbook match or rigor needed -> apply /pstack:poteto-mode. Casual turn or user opts out -> don't."

The flag lives in `${CLAUDE_PROJECT_DIR}/.claude/pstack-mode` for this project, or in `~/.claude/pstack-mode` when the arguments include `--global`.

- `on`: run `mkdir -p` on the flag's directory, then `touch` the flag. If the project flag is new, suggest adding `.claude/pstack-mode` to `.gitignore` unless the team wants it shared. Then load the poteto-mode skill for the current task if one is in progress.
- `off`: `rm -f` the flag.
- `status` or no argument: run `ls` on both flag paths and report which ones exist.

Reply with one line saying the resulting state and which flag file you changed.
