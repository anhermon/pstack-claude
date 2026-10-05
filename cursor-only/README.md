# Cursor-only skills

Skills here come from upstream pstack but depend on Cursor features that Claude Code doesn't have. They sit outside `skills/`, so the Claude Code plugin doesn't load them. They are kept, not deleted, so upstream merges keep applying to them (git follows the move as a rename) and so a later port has the source to start from.

| Skill | Why it is Cursor-only |
|---|---|
| [`make-bot-ui`](./make-bot-ui/SKILL.md) | Builds a local page whose buttons POST to a Cursor Automations webhook routine (`api2.cursor.sh/automations/webhook/<id>`). It creates the routine with Cursor's `update_state` tool and wakes a Cursor-hosted bot. Claude Code has no webhook-triggered routine API to call from a skill. A port would need a different backend, such as a GitHub Actions `workflow_dispatch` or a small server that runs `claude -p`. |
