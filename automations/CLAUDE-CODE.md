# benny on Claude Code: not ported

The benny pack is a pair of **Cursor Automations**: Slack-triggered cloud agents that triage issue reports and reproduce and fix confirmed bugs. Setup copies the pack into `.cursor/automations/benny/` and enables pstack through `.cursor/settings.json`. Neither the trigger nor the hosting exists in Claude Code, so this fork leaves the pack unchanged and the plugin doesn't load it (it never did: these files are not under `skills/`).

The skills inside (`triage-issue-reports`, `reproduce-and-fix-issues`, `setup-benny`) are plain instructions. A Claude Code port would keep them and replace the runtime:

- **Trigger:** a Slack app or workflow that, on a new top-level message in the source channel, runs a job with the thread coordinates.
- **Runner:** that job runs headless Claude Code with this plugin loaded, for example:
  `claude -p --plugin-dir /path/to/pstack-claude "Follow automations/benny/skills/triage-issue-reports/SKILL.md for thread <channel>/<ts>"`,
  or the Claude Code GitHub Action triggered by `repository_dispatch`.
- **Tools:** a Slack MCP server for thread reads and replies, the tracker's MCP server, and `gh` for draft PRs.
- **Config:** keep `templates/configuration.example.yaml` and the feature map outside the pack, as upstream does.

Treat this as a sketch, not a supported path. It hasn't been built or tested.
