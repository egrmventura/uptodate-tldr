# Topic Timeline: sdk / subscription / tray

## May 2026–Jun 2026  (3 source(s))

**Agreement:**
  - All three sources confirm that Claude Code operates on a 5-hour rolling/session window rate-limit system for Pro/Max subscribers.
  - Sources 1 (claude-usage-tray) and 3 (LimitPing) both explicitly acknowledge a 7-day weekly cap in addition to the 5-hour window, treating these as two distinct limit tiers.
  - Sources 1 and 3 both treat Claude Code rate-limit management as a real operational pain point worth building tooling around, implying the limits are frequent enough to disrupt workflows.

**Contradictions:**
  - Source 1 describes the 5-hour window as a 'session window', implying it may be tied to a discrete session start, while Source 3 describes it as a '5-hour rolling window', implying it continuously slides — these are meaningfully different models of how the clock resets.
  - Source 3 groups Claude Code, Codex, and Spark together as sharing the same '5-hour rolling windows plus a weekly cap' limit structure, implying Codex and Spark follow identical mechanics. Sources 1 and 2 focus exclusively on Claude Code and make no such claim about other tools, leaving the cross-tool generalization unverified.

**Debunks:** *(none)*

**Unresolved:**
  - Neither Source 1 nor Source 3 clarifies definitively whether the 5-hour window is session-based (starts when you begin a session) or a true rolling window (resets 5 hours after first usage in that window) — the two tools appear to assume different models without resolving it.
  - Source 2 describes the internal lifecycle of a Claude Code session in detail (tool calls, agentic loop, etc.) but does not address rate-limit mechanics at all, leaving it unclear how the session lifecycle maps to the rate-limit window — e.g., does a long agentic session extend or consume the window faster?
  - It is unresolved whether the weekly cap is a hard token/request ceiling, a time-based restriction, or something else — none of the sources define its units or how it interacts with the 5-hour window resets.
  - Source 3's claim that Spark also shares these rate-limit mechanics is unverified by any other source in this set.

---

## Jun 2026  (2 source(s))

**Agreement:**
  - Both sources confirm that Anthropic announced in May a billing change that would move Claude Agent SDK, claude -p, and third-party apps built on the Agent SDK off subscription rate limits and onto a dedicated monthly credit.
  - Both sources confirm that Anthropic has paused this billing change — i.e., the change originally scheduled to take effect is not being implemented, at least for now.
  - Both sources identify the same scope of affected tooling: the Claude Agent SDK, the claude -p command (non-interactive/headless Claude Code), and third-party apps built on the Agent SDK.

**Contradictions:** *(none)*

**Debunks:** *(none)*

**Unresolved:**
  - Neither source clarifies why Anthropic paused the change — whether it was due to subscriber pushback, technical issues, pricing reconsideration, or some other reason.
  - Neither source specifies whether the pause is indefinite or tied to a revised future rollout date.
  - Neither source details what the dedicated monthly credit would have cost or how it compared to current subscription rate limits, leaving the financial impact of the original change unclear.
  - It is unresolved whether Anthropic intends to reintroduce a modified version of this billing change, or abandon it entirely.

---
