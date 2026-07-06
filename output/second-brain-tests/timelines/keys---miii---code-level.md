# Topic Timeline: keys / miii / code-level

## May 2026  (2 source(s))

**Agreement:** *(none)*

**Contradictions:** {'sources': ['hackernews/miii-cli', 'hackernews/sieve'], 'description': "The two sources take opposing stances on API key exposure in AI terminal/coding workflows. Miii explicitly advertises 'no API keys' as a feature — implying keys are unnecessary or absent by design. Sieve exists precisely because API keys *do* get leaked into AI chat histories (Cursor, Claude, Cline, etc.), treating key exposure as an active, common risk in these workflows. These represent directly conflicting implicit claims about whether API keys are a real concern in Claude/AI code-level tooling."}

**Debunks:** *(none)*

**Unresolved:**
  - {'description': "It is unclear whether Miii's 'no API keys' claim means it runs a local model entirely offline, proxies through some key-free endpoint, or simply bundles credentials internally — the excerpt does not specify the mechanism. If credentials exist under the hood, Sieve's threat model would still apply."}
  - {'description': "Sieve scans Cursor and Claude chat history but does not mention Miii specifically. Whether Miii generates scannable chat history artifacts (and thus falls within Sieve's threat scope) is unresolved."}
  - {'description': 'The pricing and trust model differ sharply — Miii is an npm package (free/open distribution) while Sieve is a $9.99 Mac App Store app. Neither source clarifies how either handles the data it processes, raising unanswered privacy questions for security-sensitive users.'}

---
