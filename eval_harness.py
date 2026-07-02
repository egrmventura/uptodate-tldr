"""Offline evaluation harness for grouper and analyst LLM output.

Scores the parsing/structuring layer of the LLM stages against a small set of
*recorded* model responses with known-correct expectations. No live API calls —
the recorded responses stand in for what the model returned, so the harness runs
deterministically in CI and exercises the same `_parse_*` code paths the pipeline
uses in production (including markdown-fence stripping).

Two modules are scored:

- **grouper**: does a recorded assignments response parse into the expected
  index→canonical-label mapping? (`grouper._parse_assignments`)
- **analyst**: does a recorded analysis response parse and populate all four
  fields — agreements, contradictions, debunks, unresolved? (`analyst._parse_response`)

Run standalone:  python eval_harness.py
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from grouper import _parse_assignments
from analyst import _parse_response


@dataclass
class EvalCase:
    name: str
    raw: str  # the recorded raw LLM response
    check: Callable[[object], bool]  # returns True if parsed output is correct


@dataclass
class ModuleResult:
    module: str
    passed: int = 0
    failed: int = 0
    failures: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.passed + self.failed


# ---------- GROUPER CASES ----------
# Recorded responses cover: clean JSON, fenced JSON (the model's intermittent
# habit), a singleton the grouper must surface, and malformed JSON.

_GROUPER_CASES: list[EvalCase] = [
    EvalCase(
        name="clean_two_way_group",
        raw='{"assignments": [{"index": 0, "topic": "Anthropic MCP"}, '
            '{"index": 1, "topic": "Anthropic MCP"}]}',
        check=lambda out: out == {0: "Anthropic MCP", 1: "Anthropic MCP"},
    ),
    EvalCase(
        name="fenced_json_stripped",
        raw='```json\n{"assignments": [{"index": 0, "topic": "OpenAI o3"}, '
            '{"index": 1, "topic": "OpenAI o3"}]}\n```',
        check=lambda out: out == {0: "OpenAI o3", 1: "OpenAI o3"},
    ),
    EvalCase(
        name="singleton_labeled",
        raw='{"assignments": [{"index": 0, "topic": "__singleton__"}, '
            '{"index": 1, "topic": "Vector DBs"}]}',
        check=lambda out: out.get(0) == "__singleton__" and out.get(1) == "Vector DBs",
    ),
    EvalCase(
        name="malformed_json_yields_empty",
        raw="Sure! Here are the groups: (not valid json)",
        check=lambda out: out == {},
    ),
]


# ---------- ANALYST CASES ----------
# Recorded responses cover: full four-field analysis, fenced JSON, empty-but-valid
# categories, and a missing-field response the analyst must reject.

_ANALYST_CASES: list[EvalCase] = [
    EvalCase(
        name="full_four_fields",
        raw='{"agreements": ["Both confirm MCP is stable"], '
            '"contradictions": ["HN says wide adoption; arXiv finds <5%"], '
            '"debunks": ["arXiv refutes the 90% claim"], '
            '"unresolved": ["Overhead at scale unknown"]}',
        check=lambda out: out is not None
        and out["agreements"] == ["Both confirm MCP is stable"]
        and len(out["contradictions"]) == 1
        and len(out["debunks"]) == 1
        and len(out["unresolved"]) == 1,
    ),
    EvalCase(
        name="fenced_json_stripped",
        raw='```json\n{"agreements": ["A"], "contradictions": [], '
            '"debunks": [], "unresolved": ["Q"]}\n```',
        check=lambda out: out is not None
        and out["agreements"] == ["A"]
        and out["unresolved"] == ["Q"],
    ),
    EvalCase(
        name="empty_categories_valid",
        raw='{"agreements": [], "contradictions": [], "debunks": [], "unresolved": []}',
        check=lambda out: out is not None and all(
            out[k] == [] for k in ("agreements", "contradictions", "debunks", "unresolved")
        ),
    ),
    EvalCase(
        name="missing_field_rejected",
        raw='{"agreements": ["only one field present"]}',
        check=lambda out: out is None,
    ),
]


def _score(module: str, cases: list[EvalCase], parse: Callable[[str], object]) -> ModuleResult:
    result = ModuleResult(module=module)
    for case in cases:
        try:
            parsed = parse(case.raw)
            ok = bool(case.check(parsed))
        except Exception as exc:  # a parse path that raises is itself a failure
            ok = False
            case_detail = f"{case.name}: raised {exc!r}"
        else:
            case_detail = case.name
        if ok:
            result.passed += 1
        else:
            result.failed += 1
            result.failures.append(case_detail)
    return result


def run_eval() -> list[ModuleResult]:
    """Score every module and return per-module results."""
    return [
        _score("grouper", _GROUPER_CASES, lambda raw: _parse_assignments(raw, n_items=2)),
        _score("analyst", _ANALYST_CASES, _parse_response),
    ]


def main() -> int:
    print("\n=== uptodate-tldr LLM Output Eval (offline) ===\n")
    results = run_eval()
    total_pass = total = 0
    for r in results:
        total_pass += r.passed
        total += r.total
        print(f"[{r.module}] {r.passed}/{r.total} passed")
        for f in r.failures:
            print(f"  FAIL: {f}")
    rate = (total_pass / total * 100) if total else 0.0
    print(f"\n{'=' * 46}")
    print(f"Overall: {total_pass}/{total} ({rate:.1f}%)")
    print(f"{'=' * 46}")
    return 0 if total_pass == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
