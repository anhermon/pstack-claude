#!/bin/sh
# Claude Code stand-in for running /poteto-mode as a Cursor Custom Mode.
# When the flag file exists, print the poteto-mode reminder. Claude Code adds
# UserPromptSubmit stdout to the turn's context. Without the flag, print nothing.
# Toggle with /pstack:mode on|off [--global].
project="${CLAUDE_PROJECT_DIR:-$PWD}"
if [ -f "$project/.claude/pstack-mode" ] || [ -f "$HOME/.claude/pstack-mode" ]; then
	echo "pstack mode is on. New task? Playbook match or rigor needed -> apply /pstack:poteto-mode (invoke the poteto-mode skill if it is not already loaded). Casual turn or user opts out -> don't."
fi
exit 0
