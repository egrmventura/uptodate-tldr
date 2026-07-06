# Topic Timeline: sdk / tray / windows

## May 2026–Jun 2026  (2 source(s))

**Agreement:**
  - Both sources confirm that Claude Code operates on a 5-hour rolling session window rate-limit structure, plus a weekly cap, for Pro/Max subscription users.
  - Both tools are designed to help users manage or monitor Claude Code rate limits, indicating a shared understanding of the pain point: users losing track of when windows reset.
  - Both are open-source projects shared via Hacker News 'Show HN' posts, targeting developer audiences dealing with Claude Code subscription limits.

**Contradictions:**
  - Scope of supported tools: claude-usage-tray is exclusively focused on Claude Code, while LimitPing explicitly supports multiple tools — Claude Code, Codex, and Spark — suggesting a broader target use case.
  - Approach to the problem: claude-usage-tray is a passive monitoring/display tool (shows current rate-limit usage in a Windows system tray), whereas LimitPing is an active automation tool (triggers the next rate-limit window the moment the previous one resets, keeping windows continuous).
  - Platform targeting: claude-usage-tray is explicitly a Windows system-tray application, while LimitPing's description does not specify a Windows-only constraint, implying potentially broader platform support.

**Debunks:** *(none)*

**Unresolved:**
  - Whether the 5-hour window is truly 'rolling' (sliding from last activity) or a fixed reset timer — both sources use the term loosely and neither clarifies the exact reset mechanism definitively.
  - LimitPing mentions checking 'whether' something before starting the next window (excerpt is cut off), leaving it unclear what condition it checks — e.g., whether usage was actually exhausted vs. just time-elapsed.
  - Neither source clarifies how they obtain rate-limit state data — whether via an official API, local file parsing of Claude Code state, or screen-scraping — which matters for reliability and future compatibility.
  - The weekly cap structure is acknowledged by both but neither elaborates on how their tool handles or surfaces it differently from the 5-hour window.

---

## Jun 2026  (2 source(s))

**Agreement:**
  - Both sources confirm that Anthropic sent a communication to subscribers announcing a pause on a previously announced billing change.
  - Both sources agree the paused change involved the Claude Agent SDK, the `claude -p` command (non-interactive/headless Claude Code usage), and third-party apps built on the Agent SDK.
  - Both sources agree the original change was announced in May and would have moved these developer-tool usages away from subscription rate limits to a dedicated monthly credit.
  - Both sources confirm the change was paused, not permanently cancelled ('for now' language appears in both).

**Contradictions:** *(none)*

**Debunks:** *(none)*

**Unresolved:**
  - Neither source clarifies why Anthropic paused the change — whether due to subscriber backlash, technical issues, pricing recalibration, or other reasons.
  - Neither source specifies when or whether the billing change will eventually be reinstated, or what the dedicated monthly credit amount/pricing would have been.
  - It is unclear from either source whether subscribers who were already affected by any partial rollout will be retroactively adjusted.

---
