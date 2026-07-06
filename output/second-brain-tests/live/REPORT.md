# Live Loop Report — Scrape → Summarize → Group

_Ran 24 iterations at a 15-minute cadence over 6.1 hours (2026-07-02 04:56 → 2026-07-02 11:05 UTC)._

## Totals
- **Articles collected:** 66 (every record retains its `url` for citing)
- **Full-text scraped:** 57/66 (86%); rest fell back to HN excerpt
- **Topic groups formed:** 24 (TF-IDF cosine vs running centroids, threshold 0.15)
- **Queries used:** 23 factual keywords from the 7-step category walk (data/keywords.json), 3/iteration rotating
- Dedupe by URL held across iterations — repeat fetches added 0 duplicates.

## Groups (size >= 3), with citations

### g000: build / prompt / thing  (19 articles)
- [Show HN: 1ShotGen – From rough idea to full build prompt in 1 shot](https://1shotgen.com/) — 1 pts, via `claude copilot`
- [Show HN: Afair – Self-organizing memory shared across your AI tools](https://github.com/afairai/afair) — 1 pts, via `claude copilot`
- [Show HN: WtfisMyRepo – Use Claude to understand most complex codebases in mins](https://github.com/nandnijaiswal/wtfismyrepo) — 2 pts, via `claude skills`
- [Recursive AI Research Skill for Claude Code / OpenClaw / Codex](https://github.com/Toadoum/ai-research-skill) — 3 pts, via `claude skills`
- [Self-learning skill for Claude: let the agent capture its own hard-won patterns](https://github.com/Kulaxyz/self-learning-skills) — 3 pts, via `claude skills`
- [3 dangers of being locked into a harness. Your context layer is true freedom](https://news.ycombinator.com/item?id=48745664) — 1 pts, via `claude remote`
- [What's hiding in your Claude Code config files? I mined mine-found 22 patterns](https://astgl.com/p/skill-mining-claude-code-config-patterns) — 1 pts, via `claude file`
- [Show HN: Capacitor – shared mem for Claude Code, Cursor and other coding agents](https://capacitor.kurrent.io/) — 2 pts, via `claude file`
- [Snap to AI – One-Keystroke Screenshots to Claude, ChatGPT, etc. (macOS)](https://snaptoai.app) — 3 pts, via `claude macos`
- [Show HN: Agentic Orchestrator, a TUI for long-running coding agents](https://github.com/doordash-oss/agentic-orchestrator) — 19 pts, via `claude macos`
- [Show HN: Autoharness – a self-learning, maintaining skill layer for Claude Code](https://github.com/tigerless-labs/autoharness) — 3 pts, via `claude skill`
- [Show HN: fenic – LLMs as dataframe operators, query meaning and structure](https://github.com/typedef-ai/fenic) — 3 pts, via `claude skill`
- [AgentWire: Orchestrating many Claude Code sessions via tmux and voice-control](https://github.com/dotdevdotdev/agentwire-dev) — 1 pts, via `claude sessions`
- [Show HN: Agent Sessions – A model agnostic Claude managed agents alternative](https://www.agentsessions.dev/) — 2 pts, via `claude sessions`
- [Show HN: Second opinion – A skill to query different models](https://github.com/kmcheung12/second-opinion) — 4 pts, via `claude sessions`
- [Show HN: Reference MCP – let your AI agents search each other's past sessions](https://github.com/kuberwastaken/reference) — 5 pts, via `claude sessions`
- [Show HN: Google's OKF now has a framework to maintain and verify agent memory](https://kage-core.com/) — 3 pts, via `claude file`
- [Open Memory Protocol – One Memory Store for Claude, ChatGPT, Curso](https://github.com/SMJAI/open-memory-protocol) — 33 pts, via `claude github`
- [VPSMaxxing – Migrate Your Codex, Claude Code and Other Agents to a VPS](https://github.com/Kuberwastaken/VPSmaxxing) — 3 pts, via `claude github`

### g002: claude / code / network  (12 articles)
- [Using network namespaces to discover how Claude Code scrapes](https://patrickmccanna.net/inspecting-claude-codes-network-traffic-with-linux-namespaces-and-mitm-proxying-part-1/) — 3 pts, via `claude linux`
- [Claude Desktop is now available on Linux (in beta)](https://code.claude.com/docs/en/desktop-linux) — 50 pts, via `claude linux`
- [Claude Desktop is now available on Linux (in beta)](https://twitter.com/ClaudeDevs/status/2071988881717871065) — 2 pts, via `claude linux`
- [Claude Code Skills: 98 AI architectures, Haiku at 93% of Fable 5 quality](https://github.com/GPire/claude-skills-swarm) — 2 pts, via `claude skills`
- [Show HN:Earned vs. Burned, Claude skill for measuring AI delivery value](https://github.com/harveer10x/earned-vs-burned-skill) — 2 pts, via `claude skills`
- [Stop wasting tokens everytime you continue a Claude Code session](https://recallplugin.dev) — 2 pts, via `claude sessions`
- [Show HN: Claudoro, Pomodoro timer embedded in the Claude Code statusline](https://github.com/emson/claudoro) — 1 pts, via `claude terminal`
- [Show HN: CI/Lock – signed evidence of what your CI ran](https://cilock.dev/) — 1 pts, via `claude change`
- [Claude Code session URL is leaking into your Git history as of v2.1.179](https://twitter.com/samelldev/status/2070213157357072794) — 1 pts, via `claude sessions`
- [Show HN: Claude Desktop Switcher for separating the whole Claude Desktop suite](https://matsumotory.github.io/claude-desktop-switcher/) — 2 pts, via `claude github`
- [Beware, Claude Code deletes >30 day old transcripts. Anthropic won't fix it](https://github.com/anthropics/claude-code/issues/62476) — 29 pts, via `claude github`
- [Show HN: Statuslin.es – a community library of custom Claude Code status lines](https://statuslin.es) — 4 pts, via `claude github`

### g020: typescript / lsp / claude  (6 articles)
- [Show HN: TypeScript7 LSP Claude Code Plugin](https://github.com/mjn298/ts7-lsp-plugin/tree/main) — 3 pts, via `claude plugin`
- [SpecManager – a full agile team for founders, as a Claude Code plugin](https://github.com/joanseg/specmanager) — 1 pts, via `claude plugin`
- [Show HN: Claude Code plugin to draw feedback and send it back into the session](https://github.com/tomreinert/claude-annotate) — 1 pts, via `claude plugin`
- [An AI trading desk built as a team of sub-agents (Claude Code and Robinhood MCP)](https://github.com/LoganYangBo/rh-trading-agent) — 1 pts, via `claude teams`
- [Show HN: Self-hosted Slack bot Claude Tag alternative](https://github.com/acip/slack-claude-agent) — 1 pts, via `claude github`
- [Show HN: I Made TS Compiler Graph MCP: 10x Fewer Tokens in Claude Code and Codex](https://github.com/samchon/ttsc/tree/master/packages/graph) — 3 pts, via `claude github`

### g001: ouijit / terminal / agent  (3 articles)
- [Show HN: Ouijit, command terminals running coding agents](https://github.com/ouijit/ouijit) — 4 pts, via `claude linux`
- [Show HN: Matrix, an open-source cloud computer for coding agents](https://matrix-os.com) — 1 pts, via `claude thinking`
- [Vibe Coding to Agentic Engineering: A Three-Phase Workflow with Claude Code](https://www.apimatic.io/blog/agentic-engineering-claude-code) — 2 pts, via `claude engineering`

### g005: openatp / theorem / lean  (3 articles)
- [Show HN: OpenATP: A platform for automated theorem proving in Lean](https://github.com/henryrobbins/open-atp) — 3 pts, via `claude remote`
- [Show HN: The open-source alternative to Claude Tag](https://www.agent-swarm.dev) — 3 pts, via `claude change`
- [Show HN: Open-source sandbox for your product team](https://news.ycombinator.com/item?id=48750459) — 14 pts, via `claude change`

### g009: across / every / running  (3 articles)
- [Show HN: Run AI chat, image gen, vision, and voice offline on your Mac](https://github.com/off-grid-ai) — 10 pts, via `claude windows`
- [Show HN: An Open Source Codex App that works across provider](https://github.com/ymichael/bb) — 1 pts, via `claude development`
- [Show HN: AMA2, messenger built for AI agent](https://ama2.me/) — 5 pts, via `claude engineering`

## Observations
- New-article rate decayed as expected: ~6/iteration early → 0-1 once the 3-day lookback was exhausted, with fresh posts still caught (e.g. iters 13, 19, 21).
- The F1-fixed `HackerNewsSource` served every fetch with explicit date windows.
- Group count stabilized at 24 by iteration ~15 — centroid grouping absorbs new articles into existing topics once coverage saturates.
- Context stayed far below the 85% compaction trigger throughout (single-line iteration output by design).
