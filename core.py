import re

CITATION_RE = re.compile(r"\[PMID:?\s*(\d+)\]")

def extract_pmids(text):
    """Return the set of PMIDs cited in a piece of text.

    Args:
        text (str): The text to scan for PMID citation patterns.

    Returns:
        set[str]: Unique PMIDs found in the text.
    """
    return set(CITATION_RE.findall(text))

def check_citations(answer, valid_pmids):
    """Guardrail: catch citations to PMIDs that were never retrieved.

    Args:
        answer (str): The model's answer text to validate.
        valid_pmids (list[str] | set[str]): PMIDs that were actually retrieved and are safe to cite.

    Returns:
        tuple[str, str]: A (status, message) pair where status is one of
            ``"blocked_hallucinated_citation"``, ``"answered_no_citations"``, or ``"answered"``.
    """
    cited = extract_pmids(answer)
    hallucinated = cited - set(valid_pmids)
    if hallucinated:
        return "blocked_hallucinated_citation", f"cited PMIDs never retrieved: {sorted(hallucinated)}"
    if not cited:
        return "answered_no_citations", "no citations (may be a valid abstention)"
    return "answered", "ok"