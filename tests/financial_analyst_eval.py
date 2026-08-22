"""Braintrust eval for the financial analyst agent.

Runs the eval dataset through the real agent and grades each response with
an autoevals LLMClassifier that respects per-case grading rules (behavioral
vs. factual, and any `grading_note` override).

Run with:
    uv run braintrust eval tests/financial_analyst_eval.py
"""

import asyncio
import json
import os
from pathlib import Path

from braintrust import Eval
from autoevals import LLMClassifier

from financial_analyst_agent.agent import build_agent, run_query

DATA_DIR = Path(__file__).parent
PROJECT_NAME = os.environ.get("BRAINTRUST_PROJECT", "financial-analyst-agent")
JUDGE_MODEL = os.environ.get("BRAINTRUST_JUDGE_MODEL", "gpt-4o")


def load_cases():
    cases = json.loads(
        (DATA_DIR / "financial_analyst_eval_dataset.json").read_text(encoding="utf-8")
    )

    case_id = os.environ.get("EVAL_CASE_ID")
    if case_id is not None:
        cases = [c for c in cases if str(c["id"]) == case_id]

    limit = os.environ.get("EVAL_LIMIT")
    if limit is not None:
        cases = cases[: int(limit)]

    return [
        {
            "input": c["question"],
            "expected": c["answer"],
            "tags": [
                f"category:{c['category']}",
                f"difficulty:{c.get('difficulty', 'unknown')}",
            ],
            "metadata": {
                "id": c["id"],
                "category": c["category"],
                "difficulty": c.get("difficulty"),
                "edge_case_type": c.get("edge_case_type"),
                "requires_tools": c.get("requires_tools", []),
                "source": c.get("source"),
                "grading_note": c.get("grading_note") or "",
                "is_behavioral": c.get("grading_type") == "behavioral",
            },
        }
        for c in cases
    ]


# --- Agent under test, built once and reused across cases ---

_agent = None
_agent_lock = asyncio.Lock()


async def get_agent():
    global _agent
    async with _agent_lock:
        if _agent is None:
            _agent = await build_agent()
    return _agent


async def task(input):
    agent = await get_agent()
    return await run_query(agent, input)


# --- Scorers ---

_FAILURE_STRINGS = (
    "Execution budget exceeded",
    "The agent returned no result.",
)


def answered(output, **_):
    ok = bool(output) and not any(s in output for s in _FAILURE_STRINGS)
    return {"name": "answered", "score": 1.0 if ok else 0.0}


JUDGE_PROMPT = """You are grading a financial-analyst AI agent's response.

Question:
{{input}}

Agent's answer:
{{output}}

Reference answer:
{{expected}}

{{#metadata.is_behavioral}}
This is a BEHAVIORAL test — there is no single correct factual answer. Grade whether the
agent behaved correctly (e.g. asked for clarification, declined rather than fabricated a
figure) as described in the reference answer above.
{{/metadata.is_behavioral}}

{{#metadata.grading_note}}
Grading note (follow exactly — this overrides your own default judgment):
{{metadata.grading_note}}
{{/metadata.grading_note}}

<numeric_tolerance_and_calculated_values>
Some figures in the reference answer reflect a value stated verbatim in the source document
(often a growth rate rounded to a whole percentage point in company prose, e.g. "revenue
increased 18%"). The agent may instead report a value it computed directly from raw reported
figures (e.g. deriving 17.8% from two absolute revenue values). These are NOT competing or
conflicting figures — they are typically the same underlying fact at different levels of
precision, not a factual disagreement.

Apply these rules when comparing such figures:
- If the agent's calculated value is mathematically consistent with the reference's own
  underlying reported figures (i.e., recomputing from the reference's absolute values
  produces the agent's number), treat it as EQUIVALENT to the reference figure — not as an
  error, and not as a "minor discrepancy." Do not lower the letter grade for this alone.
- This tolerance applies to figures that are conventionally rounded in company disclosures
  (YoY/QoQ growth rates, margin percentages). It does NOT apply to core reported values
  themselves (absolute revenue, net income, EPS, balance-sheet line items), which must
  match the reference to the precision given.
- If the agent explicitly labels a value as "calculated" versus directly reported, treat
  that as correct, transparent practice — not as a hedge that weakens the answer.
- Only treat a growth-rate or similar figure as a genuine discrepancy if it is inconsistent
  with the reference's own underlying reported values (i.e., recomputing does NOT reproduce
  the agent's number), or if it differs by more than what rounding convention explains
  (as a guideline, more than ~0.5 percentage points for growth/margin rates).
</numeric_tolerance_and_calculated_values>

<unrequested_but_relevant_information>
An agent may include additional correct, relevant figures beyond what the reference answer
covers (e.g. segment-level growth, net income, EPS, when the question asked about revenue).
This should never lower the grade. Conversely, omitting a figure that appears in the
reference but was not explicitly asked for in the question (e.g. constant-currency growth on
a question that only asked for revenue) should be treated as, at most, a minor omission —
not grounds for anything below (A) on its own, since the core answer to the question asked
was complete and correct.
</unrequested_but_relevant_information>

Grade the agent's answer against the reference answer (and any grading note above) using
this rubric. Select exactly one letter:

(A) Excellent — fully matches the reference (and grading note, if any) on the figures the
    question actually asked about. All required figures correct or equivalent per
    <numeric_tolerance_and_calculated_values> above, no fabrication, all parts of a
    multi-part question addressed. Additional unrequested-but-correct detail, or the
    absence of unrequested reference detail, does not prevent an (A).
(B) Good — mostly correct with only minor omissions or genuine discrepancies (i.e., not
    covered by the tolerance rule above) in a figure the question asked about.
(C) Partial — some parts of a multi-part question correct, others missing or wrong.
(D) Poor — largely incorrect or missing key elements, but not fabricated.
(E) Failing — fabricated figures, hallucinated data, or the agent ignored an explicit
    grading instruction in the grading note.

Respond with your reasoning, then end with a single letter (A, B, C, D, or E).
"""

llm_judge = LLMClassifier(
    name="llm_judge",
    prompt_template=JUDGE_PROMPT,
    choice_scores={"A": 1.0, "B": 0.75, "C": 0.5, "D": 0.25, "E": 0.0},
    model=JUDGE_MODEL,
    use_cot=True,
)


Eval(
    PROJECT_NAME,
    data=load_cases,
    task=task,
    scores=[llm_judge, answered],
    max_concurrency=3,
    metadata={"judge_model": JUDGE_MODEL},
)