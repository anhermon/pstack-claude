#!/usr/bin/env bash
# Everything CI or a human should run before pushing. Needs `claude` (Claude Code
# CLI) and `uv` (or a python3 that has PyYAML).
set -euo pipefail
cd "$(dirname "$0")/.."

echo "== claude plugin validate (marketplace + plugin + components)"
claude plugin validate . --strict
claude plugin validate .claude-plugin/plugin.json --strict
for d in skills agents commands; do claude plugin validate "./$d" --strict; done

echo "== frontmatter"
if command -v uv >/dev/null; then uv run -q --with pyyaml python3 scripts/check-frontmatter.py
else python3 scripts/check-frontmatter.py; fi

echo "== hooks"
python3 -m json.tool hooks/hooks.json >/dev/null && echo "hooks.json parses"
sh -n hooks/poteto-mode-reminder.sh && echo "poteto-mode-reminder.sh parses"

echo "== codemod is applied and idempotent"
python3 scripts/claude-code-adapt.py --check

echo "== leftover Cursor-only references"
python3 scripts/claude-code-adapt.py --audit
