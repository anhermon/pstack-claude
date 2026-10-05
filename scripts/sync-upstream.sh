#!/usr/bin/env bash
# Merge the latest upstream pstack (cursor/plugins, subdirectory pstack/) into
# this fork, then re-apply the Claude Code adaptation.
#
#   scripts/sync-upstream.sh          # sync to upstream main
#   scripts/sync-upstream.sh <ref>    # sync to a specific monorepo ref
#
# It leaves an uncommitted merge on a new branch for you to review. It never
# pushes, never force-pushes, and never skips hooks.
set -euo pipefail
cd "$(dirname "$0")/.."
root=$PWD
# shellcheck disable=SC1091
source claude-code/upstream.env
ref=${1:-main}

if [ -n "$(git status --porcelain)" ]; then
	echo "working tree is not clean; commit or stash first" >&2
	exit 1
fi

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
echo "cloning $UPSTREAM_URL (full history is needed for subtree split)"
git clone --quiet "$UPSTREAM_URL" "$work/plugins"
git -C "$work/plugins" checkout --quiet "$ref"
monorepo_sha=$(git -C "$work/plugins" rev-parse HEAD)
split_sha=$(git -C "$work/plugins" subtree split --prefix="$UPSTREAM_PREFIX" 2>/dev/null | tail -1)
git -C "$work/plugins" branch --quiet --force upstream-pstack "$split_sha"

if [ "$split_sha" = "$UPSTREAM_SPLIT_SHA" ]; then
	echo "already at upstream $UPSTREAM_PREFIX $split_sha (monorepo $monorepo_sha)"
	exit 0
fi

git fetch --quiet "$work/plugins" upstream-pstack
branch="upstream-sync-${split_sha:0:7}"
git switch --quiet -c "$branch"
echo "merging upstream $split_sha into $branch"

# Upstream wins conflicting hunks. The conflicts are almost always lines the
# codemod rewrote, and re-running the codemod below rewrites them again.
git merge --no-ff --no-commit -X theirs FETCH_HEAD || true

# Hand-owned files keep our side. Save what upstream changed so it can be
# ported by hand.
report="$work/hand-owned-upstream.diff"
: > "$report"
while IFS= read -r f; do
	case "$f" in ''|'#'*) continue ;; esac
	git diff "$UPSTREAM_SPLIT_SHA" "$split_sha" -- "$f" >> "$report" || true
	git checkout HEAD -- "$f" 2>/dev/null || true
done < claude-code/hand-owned.txt

unmerged=$(git diff --name-only --diff-filter=U)
if [ -n "$unmerged" ]; then
	echo "unresolved paths (usually modify/delete). Resolve them, then run" >&2
	echo "  python3 scripts/claude-code-adapt.py && scripts/check.sh" >&2
	echo "and update claude-code/upstream.env to $split_sha by hand:" >&2
	echo "$unmerged" | sed 's/^/  /' >&2
	[ -s "$report" ] && cp "$report" "$root/upstream-hand-owned.diff"
	exit 1
fi

python3 scripts/claude-code-adapt.py
sed -i.bak \
	-e "s/^UPSTREAM_MONOREPO_SHA=.*/UPSTREAM_MONOREPO_SHA=$monorepo_sha/" \
	-e "s/^UPSTREAM_SPLIT_SHA=.*/UPSTREAM_SPLIT_SHA=$split_sha/" \
	claude-code/upstream.env && rm -f claude-code/upstream.env.bak
version=$(python3 -c 'import json;print(json.load(open(".cursor-plugin/plugin.json"))["version"])' 2>/dev/null || echo "")
[ -n "$version" ] && sed -i.bak "s/^UPSTREAM_VERSION=.*/UPSTREAM_VERSION=$version/" claude-code/upstream.env && rm -f claude-code/upstream.env.bak
git add -A

if [ -s "$report" ]; then
	cp "$report" "$root/upstream-hand-owned.diff"
	echo
	echo "upstream changed hand-owned files. Port by hand, then delete upstream-hand-owned.diff:"
	grep '^diff --git' "$root/upstream-hand-owned.diff" | sed 's/^/  /'
fi
cat <<MSG

next:
  1. scripts/check.sh   (validate, frontmatter, codemod --check, --audit)
  2. fix any --audit hit by adding a rule to scripts/claude-code-adapt.py, re-run it
  3. update the upstream SHA in README.md, bump .claude-plugin/plugin.json version
  4. git commit   (completes the merge; hooks run as usual)
MSG
