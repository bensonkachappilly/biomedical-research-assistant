from core import extract_pmids, check_citations

def test_extract_pmids_basic():
    """Verify that two PMIDs with colons are extracted from a normal sentence.

    Args:
        No arguments.

    Returns:
        No return value; asserts on extracted PMID set.
    """
    text = "Vitamin D helps [PMID: 12345678] and also [PMID: 87654321]."
    assert extract_pmids(text) == {"12345678", "87654321"}

def test_extract_pmids_handles_no_colon():
    """Verify that a PMID without a colon separator is still extracted.

    Args:
        No arguments.

    Returns:
        No return value; asserts on extracted PMID set.
    """
    assert extract_pmids("see [PMID 11112222]") == {"11112222"}

def test_extract_pmids_empty():
    """Verify that text with no PMID patterns returns an empty set.

    Args:
        No arguments.

    Returns:
        No return value; asserts that the result is an empty set.
    """
    assert extract_pmids("no citations here") == set()

def test_citations_pass_when_grounded():
    """Verify that citing a retrieved PMID returns the 'answered' status.

    Args:
        No arguments.

    Returns:
        No return value; asserts on the returned status string.
    """
    status, _ = check_citations("Claim [PMID: 111]", {"111", "222"})
    assert status == "answered"

def test_citations_flag_hallucination():
    """Verify that citing a PMID not in the retrieved set is flagged as a hallucination.

    Args:
        No arguments.

    Returns:
        No return value; asserts on status and that the phantom PMID appears in the reason.
    """
    status, reason = check_citations("Claim [PMID: 999]", {"111", "222"})
    assert status == "blocked_hallucinated_citation"
    assert "999" in reason

def test_citations_allow_abstention():
    """Verify that an answer with no citations returns the 'answered_no_citations' status.

    Args:
        No arguments.

    Returns:
        No return value; asserts on the returned status string.
    """
    status, _ = check_citations("The evidence is insufficient.", {"111"})
    assert status == "answered_no_citations"