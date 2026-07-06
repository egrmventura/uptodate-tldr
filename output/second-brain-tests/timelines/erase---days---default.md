# Topic Timeline: erase / days / default

## Jun 2026  (2 source(s))

**Agreement:**
  - Both sources confirm that Claude Code has a default retention period of 30 days, after which session/transcript data is deleted. Source 1 states 'Claude Code sessions erase after 30 days by default'; Source 2 identifies the specific config parameter `cleanupPeriodDays` defaulting to 30 as the mechanism.
  - Both sources agree this behavior affects local stored session data — Source 1 references sessions generally, Source 2 specifically identifies `~/.claude/projects//*.jsonl` files deleted on startup.

**Contradictions:** *(none)*

**Debunks:** *(none)*

**Unresolved:**
  - Source 2 claims 'Anthropic won't fix it', implying this is a known issue that has been reported and dismissed, but neither source clarifies whether this is intentional product design (privacy/storage hygiene) or an oversight — the documentation in Source 1 presents it neutrally as a default setting without flagging it as a potential data loss risk.
  - Source 2 shows only 14 sessions remaining in `~/.claude/history.jsonl` as evidence of deletion, but neither source clarifies whether the history.jsonl and the per-project .jsonl files are subject to the same cleanup logic or different retention rules.
  - Neither source specifies what user action or documentation path would allow a user to set `cleanupPeriodDays` to a higher value or disable cleanup entirely, leaving the mitigation path unresolved.
  - Source 2's claim that 'Anthropic won't fix it' is unsubstantiated by any quoted Anthropic response in the excerpt — the severity and finality of that claim is not corroborated.

---
