from core import extract_pmids, check_citations

def test_extract_pmids_basic():
    text = "Vitamin D helps [PMID: 12345678] and also [PMID: 87654321]."
    assert extract_pmids(text) == {"12345678", "87654321"}

def test_extract_pmids_handles_no_colon():
    assert extract_pmids("see [PMID 11112222]") == {"11112222"}

def test_extract_pmids_empty():
    assert extract_pmids("no citations here") == set()

def test_citations_pass_when_grounded():
    status, _ = check_citations("Claim [PMID: 111]", {"111", "222"})
    assert status == "answered"

def test_citations_flag_hallucination():
    status, reason = check_citations("Claim [PMID: 999]", {"111", "222"})
    assert status == "blocked_hallucinated_citation"
    assert "999" in reason

def test_citations_allow_abstention():
    status, _ = check_citations("The evidence is insufficient.", {"111"})
    assert status == "answered_no_citations"