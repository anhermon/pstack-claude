### Authoring or modifying a skill

> **Agent parameters:** every spawn, retry, resume, and nested delegate passes explicit `model` and `effort`. Resolve delegation-kit's live role table first, otherwise pstack's role pair: code `sonnet/medium`, exploration/low-risk `sonnet/low`. Inheritance aliases pin `sonnet/medium`. Fan-outs of 3+ use sonnet/haiku, never opus. The main session synthesizes; only a single judge after the fan-out may use `opus/medium`.

**You own the skill's voice.**

1. Use the `skill-creator` skill (Anthropic's, `/plugin install skill-creator@claude-plugins-official`; see pstack's `claude-code/runtime.md`).
2. Validate the skill: frontmatter has `name` and `description`, referenced files exist, cross-skill links resolve.
3. Test cases if structural. Skip if subjective.
4. Run **Opening a PR**.

When in doubt, delete. Keep only prose that changes a decision. Tell it to do the thing and skip the reason. Explain only when the rule is confusing without one. Match tone to scope. Point at structural sources (types, READMEs, config) per the **encode-lessons-in-structure** principle skill. Delegate to other skills by path. Don't restate. A workflow you keep hitting but isn't captured → propose a new skill.

**Reply:** summary of the skill, key design decisions, validation notes.
