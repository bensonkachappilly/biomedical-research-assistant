import asyncio
import json
from datetime import datetime
from pathlib import Path
from agent_traced import run, in_scope
from core import extract_pmids

EVAL_CASES = [
    {"q": "Does vitamin D deficiency increase the risk of depression?", "scope": "in"},
    {"q": "Is metformin associated with reduced cancer risk in type 2 diabetes?", "scope": "in"},
    {"q": "What are the cardiovascular effects of intermittent fasting?", "scope": "in"},
    {"q": "Does omega-3 supplementation improve cognition in older adults?", "scope": "in"},
    {"q": "Write me a poem about the ocean.", "scope": "out"},
    {"q": "What is the capital of France?", "scope": "out"},
    {"q": "Recommend a good pizza recipe.", "scope": "out"},
    # add more over time — aim for ~15-20
]

async def evaluate():
    """Run all eval cases and collect per-case metric dictionaries.

    Args:
        No arguments.

    Returns:
        list[dict]: One dict per eval case containing at minimum ``question``,
            ``expected_scope``, and ``scope_correct``. In-scope cases also include
            ``retrieved_any``, ``has_citations``, and ``no_hallucinated_citations``.
    """
    results = []
    for case in EVAL_CASES:
        q, expected = case["q"], case["scope"]
        m = {"question": q, "expected_scope": expected,
             "scope_correct": in_scope(q) == (expected == "in")}
        if expected == "in":
            answer, refs, _ = await run(q)
            cited, retrieved = extract_pmids(answer), set(refs.keys())
            m["retrieved_any"] = len(retrieved) > 0
            m["has_citations"] = len(cited) > 0
            m["no_hallucinated_citations"] = cited.issubset(retrieved)
        results.append(m)
        print(f"  done: {q[:50]}")
    return results

def summarise(results):
    """Aggregate per-case eval results into a summary of pass-rates.

    Args:
        results (list[dict]): The list of per-case metric dicts returned by ``evaluate()``.

    Returns:
        dict: Aggregated metrics with keys ``n_cases``, ``scope_accuracy``,
            ``retrieved_any_rate``, ``has_citations_rate``, and
            ``no_hallucinated_citations_rate``. Rates are floats in [0, 1] or
            ``None`` if no cases supplied a value for that key.
    """
    def rate(key):
        """Compute the mean of a boolean metric across cases that have it.

        Args:
            key (str): Metric key to average over the results list.

        Returns:
            float | None: Mean value rounded to 2 decimal places, or ``None`` if
                no case contained the key.
        """
        vals = [r[key] for r in results if key in r]
        return round(sum(vals) / len(vals), 2) if vals else None
    return {"n_cases": len(results),
            "scope_accuracy": rate("scope_correct"),
            "retrieved_any_rate": rate("retrieved_any"),
            "has_citations_rate": rate("has_citations"),
            "no_hallucinated_citations_rate": rate("no_hallucinated_citations")}

if __name__ == "__main__":
    results = asyncio.run(evaluate())
    summary = summarise(results)
    print("\n" + json.dumps(summary, indent=2))

    Path("eval_reports").mkdir(exist_ok=True)
    Path(f"eval_reports/{datetime.now():%Y%m%d_%H%M%S}.json").write_text(
        json.dumps({"summary": summary, "results": results}, indent=2))

    # These thresholds turn quality into a pass/fail signal.
    assert summary["scope_accuracy"] == 1.0, "Scope guard misclassified a case!"
    assert summary["no_hallucinated_citations_rate"] == 1.0, "Hallucinated citation detected!"
    print("\nAll eval thresholds met.")