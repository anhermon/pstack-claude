#!/bin/sh
# Behavior test for hooks/poteto-mode-reminder.sh: silent without a flag file,
# prints the reminder with a project flag or a global flag, even when the path has spaces.
set -eu
hook="$(cd "$(dirname "$0")/.." && pwd)/hooks/poteto-mode-reminder.sh"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/my proj/.claude" "$tmp/home/.claude"
run() { HOME="$tmp/home" CLAUDE_PROJECT_DIR="$tmp/my proj" "$hook"; }

[ -z "$(run)" ] || { echo "FAIL: output without a flag" >&2; exit 1; }
touch "$tmp/my proj/.claude/pstack-mode"
run | grep -q "pstack mode is on" || { echo "FAIL: no output with project flag" >&2; exit 1; }
rm "$tmp/my proj/.claude/pstack-mode"
touch "$tmp/home/.claude/pstack-mode"
run | grep -q "pstack mode is on" || { echo "FAIL: no output with global flag" >&2; exit 1; }
echo "hook behavior ok"
