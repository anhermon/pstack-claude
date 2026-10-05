# Keeping up with upstream

This repo is a fork of [`pstack/`](https://github.com/cursor/plugins/tree/main/pstack) in the `cursor/plugins` monorepo. It was seeded with `git subtree split --prefix=pstack`, so upstream commits and their authors are in this history unchanged. The adaptation commits sit on top of them.

The last upstream state merged is recorded in [`claude-code/upstream.env`](./claude-code/upstream.env):

- `UPSTREAM_MONOREPO_SHA`: the `cursor/plugins` commit.
- `UPSTREAM_SPLIT_SHA`: the matching commit of the split `pstack/` history. This is the merge base for the next sync.

## How the adaptation is layered

Each file belongs to one of three groups, which keeps upstream merges mechanical:

1. **Upstream files changed only by the codemod.** [`scripts/claude-code-adapt.py`](./scripts/claude-code-adapt.py) holds every Cursor-to-Claude-Code rename as an ordered regex rule. It also drops Cursor-only frontmatter, adds a one-line pointer to `claude-code/runtime.md` in affected skills, converts agent frontmatter, and moves Cursor-only skills to `cursor-only/`. It is idempotent. Never hand-edit these files: change a rule and re-run the script.
2. **Hand-owned upstream files.** These are listed in [`claude-code/hand-owned.txt`](./claude-code/hand-owned.txt) (`README.md`, `skills/setup-pstack/SKILL.md`). They were rewritten for Claude Code, and the codemod skips them.
3. **Fork-only files.** `.claude-plugin/`, `claude-code/`, `scripts/`, `hooks/`, `commands/`, `agents/read-only.md`, `cursor-only/README.md`, `automations/CLAUDE-CODE.md`, and this file. Upstream never touches them.

## Sync

```bash
scripts/sync-upstream.sh          # upstream main
scripts/sync-upstream.sh <ref>    # a specific cursor/plugins ref
```

The script:

1. Clones `cursor/plugins` and runs `git subtree split --prefix=pstack`.
2. Creates branch `upstream-sync-<sha>` and runs `git merge --no-ff --no-commit -X theirs` on the split. Upstream wins conflicting hunks. Those conflicts are almost always lines the codemod rewrote, and step 4 rewrites them again.
3. Restores hand-owned files to our side, and writes upstream's changes to them into `upstream-hand-owned.diff` so you can port them by hand.
4. Re-runs `scripts/claude-code-adapt.py` and updates `claude-code/upstream.env`.
5. Stops before committing. It never pushes, never force-pushes, and never skips hooks.

Then:

```bash
scripts/check.sh   # claude plugin validate --strict, frontmatter, codemod --check, --audit
```

- An `--audit` hit means upstream added new Cursor-specific wording. Add a rule to the codemod (or an allowlist entry with a reason) and re-run it.
- A modify/delete conflict (upstream deleted a file we changed) stops the script. Resolve it, then re-run the codemod.
- Update the upstream SHA in `README.md`, bump `version` in `.claude-plugin/plugin.json` (for example `0.15.11-cc.1`), and `git commit` to finish the merge.

## Doing it by hand

```bash
git clone https://github.com/cursor/plugins.git /tmp/plugins
git -C /tmp/plugins subtree split --prefix=pstack -b upstream-pstack
git fetch /tmp/plugins upstream-pstack
git switch -c upstream-sync
git merge --no-ff --no-commit -X theirs FETCH_HEAD
git checkout HEAD -- README.md skills/setup-pstack/SKILL.md
python3 scripts/claude-code-adapt.py
scripts/check.sh
git commit
```

## Why a new repo instead of a GitHub fork of cursor/plugins

`pstack/` is one subdirectory of a monorepo that holds many unrelated Cursor plugins. A GitHub fork would carry all of them and all of their history. A Claude Code marketplace needs `.claude-plugin/marketplace.json` at the repo root, so the fork would also have to restructure the monorepo root. A split repo keeps upstream authorship for `pstack/` and installs with one `/plugin marketplace add anhermon/pstack-claude`. The cost is that you can't open a PR to upstream straight from this repo. To send a fix upstream, apply it to a `cursor/plugins` clone under `pstack/`. `git subtree` can push a split branch back for that.
