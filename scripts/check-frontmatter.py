#!/usr/bin/env python3
"""Parse every skill, agent, and command frontmatter as YAML and check the
fields Claude Code relies on. `claude plugin validate` does not flag broken
YAML inside skills/, so this fills that gap. Needs PyYAML
(`uv run --with pyyaml scripts/check-frontmatter.py`)."""
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
FM = re.compile(r"\A---\n(.*?)\n---\n", re.S)
SKILL_KEYS = {"name", "description", "disable-model-invocation", "paths", "argument-hint", "allowed-tools", "model", "user-invocable"}
AGENT_KEYS = {"name", "description", "tools", "disallowedTools", "model", "background", "skills", "effort", "isolation", "color", "maxTurns", "memory"}
COMMAND_KEYS = {"description", "argument-hint", "disable-model-invocation", "allowed-tools", "model"}

errors = []


def load(p: Path):
    m = FM.match(p.read_text())
    if not m:
        errors.append(f"{p}: no frontmatter")
        return None
    try:
        data = yaml.safe_load(m.group(1))
    except yaml.YAMLError as e:
        errors.append(f"{p}: YAML error: {e}")
        return None
    if not isinstance(data, dict):
        errors.append(f"{p}: frontmatter is not a map")
        return None
    return data


for p in sorted(ROOT.glob("skills/*/SKILL.md")):
    d = load(p)
    if d is None:
        continue
    if d.get("name") != p.parent.name:
        errors.append(f"{p}: name {d.get('name')!r} != directory {p.parent.name!r}")
    if not str(d.get("description", "")).strip():
        errors.append(f"{p}: missing description")
    if len(str(d.get("description", ""))) > 1536:
        errors.append(f"{p}: description over 1536 chars (Claude Code truncates)")
    for k in set(d) - SKILL_KEYS:
        errors.append(f"{p}: unexpected key {k!r}")
    if d.get("disable-model-invocation") and p.parent.name != "setup-pstack":
        errors.append(f"{p}: disable-model-invocation blocks routing from poteto-mode")

for p in sorted(ROOT.glob("agents/*.md")):
    d = load(p)
    if d is None:
        continue
    if not re.fullmatch(r"[a-z0-9-]+", str(d.get("name", ""))):
        errors.append(f"{p}: agent name {d.get('name')!r} is not kebab-case")
    if not str(d.get("description", "")).strip():
        errors.append(f"{p}: missing description")
    for k in set(d) - AGENT_KEYS:
        errors.append(f"{p}: unexpected key {k!r}")

for p in sorted(ROOT.glob("commands/*.md")):
    d = load(p)
    if d is not None:
        for k in set(d) - COMMAND_KEYS:
            errors.append(f"{p}: unexpected key {k!r}")

for e in errors:
    print(e)
n = len(list(ROOT.glob("skills/*/SKILL.md"))) + len(list(ROOT.glob("agents/*.md"))) + len(list(ROOT.glob("commands/*.md")))
print(f"frontmatter: {n} files, {len(errors)} problem(s)")
sys.exit(1 if errors else 0)
