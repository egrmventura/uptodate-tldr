# Topic Timeline: improve / guessing / baseline

## Jun 2026  (2 source(s))

**Agreement:**
  - Both sources use Claude Code as a primary subject for automated agent engineering/improvement experiments.
  - Both sources treat 'baseline traces' or training data as a variable in agent optimization, implying that improvement over a baseline is the core experimental goal.
  - Both sources originate from the same author (Andrew Jesson) and share an underlying research agenda: understanding when and how coding agents can autonomously improve other agents.

**Contradictions:**
  - Source 1 implicitly treats baseline data (100 traces) as a necessary input for agent improvement — the experimental setup provides traces as part of the optimization task. Source 2 explicitly claims 'Claude Code can often improve another agent with no training data at all,' suggesting data is not a prerequisite, directly contradicting the framing of Source 1's methodology.
  - Source 1 evaluates both Claude Code and Codex as capable agents for this task, treating them comparably. Source 2 focuses exclusively on Claude Code, leaving the generalizability of its findings to Codex (or other agents) unaddressed — a scope difference that creates an implicit conflict in how broadly the conclusions apply.

**Debunks:** Source 2 partially debunks the implicit assumption in Source 1 that baseline trace data is what enables agent improvement. Source 2 argues data only helps 'where Claude Code's own prior knowledge of the task runs out,' meaning the improvement observed in Source 1's data-rich setup may be attributable to Claude Code's priors rather than the provided traces.

**Unresolved:**
  - Whether the 'drift' metric described in Source 2 (measuring how far Claude Code's guesses diverge from real data) would have predicted which of Source 1's five simulated applications benefited from the provided baseline traces versus which ones Claude Code could have improved without them.
  - Source 2 identifies drift as a diagnostic signal for when data helps, but neither source resolves how to act on high-drift cases where Claude Code's priors are insufficient and data is unavailable.
  - The role of Codex: Source 1 includes Codex as a co-equal subject, but Source 2 ignores it entirely. Whether Codex exhibits the same prior-knowledge-driven improvement pattern as Claude Code — or whether it is more data-dependent — remains completely open.
  - Neither source addresses whether the 'improvement' achieved (metric optimization) generalizes beyond the simulated agent applications used in experiments, leaving ecological validity unresolved.

---

## Jul 2026  (2 source(s))

**Agreement:**
  - Both sources agree that AI agents in data engineering must go beyond code generation — the core challenge is trustworthiness and correctness, not just writing code that runs.
  - Both sources frame agentic data engineering as a structured, multi-stage process rather than a single LLM call, analogous to how human data teams operate.
  - Both sources acknowledge that raw AI output is insufficient for production and that additional layers (verification, deterministic checks, or validation stages) are required to ship reliable data pipelines.

**Contradictions:**
  - Revos frames the solution as an end-to-end agentic pipeline that replicates the full human data team workflow ('driven by intent instead of tickets'), implying broad autonomous scope. Altimate argues AI agents should be scoped specifically to a 'correctness layer' with a deterministic core, suggesting narrower, more constrained autonomy is the right architecture — a direct tension in how much agency to grant.
  - Revos implicitly positions the AI agent as a replacement or substitute for the data team workflow. Altimate explicitly warns against over-reliance on any single model and emphasizes that better tooling reduces model dependency — a different philosophy on the role of the model itself.

**Debunks:** Altimate's argument that agents should be confined to a 'correctness layer' with a deterministic core implicitly refutes Revos's premise that an intent-driven agentic pipeline can be trusted end-to-end without such structural constraints — i.e., Altimate challenges the sufficiency of Revos's approach.

**Unresolved:**
  - Neither source resolves where exactly the boundary of agent autonomy should be drawn in practice — Revos says 'full pipeline,' Altimate says 'correctness layer,' but neither provides empirical evidence for which approach produces better outcomes at scale.
  - The sources do not address how these architectures perform when upstream data schemas change unexpectedly, leaving open whether intent-driven or correctness-layer approaches are more robust to data drift.
  - Neither source clarifies how human oversight is maintained (or when it should intervene) in their respective architectures — a critical gap for production trust.
  - It remains unresolved whether the 'three levels of AI agents' taxonomy in Altimate is compatible with or contradictory to the pipeline stages described by Revos — the sources use different frameworks without cross-referencing.

---
