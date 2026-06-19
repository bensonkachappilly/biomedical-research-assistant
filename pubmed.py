# Import packages
import time
import requests
import xml.etree.ElementTree as ET

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
EMAIL = "benson.kachappilly1@hotmail.com"
TOOL = "litscout"

def search_pubmed(query, max_results=5):
    """Return a list of PubMed IDs (PMIDs) matching the query."""
    resp = requests.get(
        f"{EUTILS}/esearch.fcgi",
        params={"db": "pubmed", "term": query, "retmax": max_results,
                "retmode": "json", "email": EMAIL, "tool": TOOL},
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()["esearchresult"]["idlist"]

def fetch_abstracts(pmids):
    """Given PMIDs, return a list of {pmid, title, abstract} dicts."""
    if not pmids:
        return []
    resp = requests.get(
        f"{EUTILS}/efetch.fcgi",
        params={"db": "pubmed", "id": ",".join(pmids), "rettype": "abstract",
                "retmode": "xml", "email": EMAIL, "tool": TOOL},
        timeout=30,
    )
    resp.raise_for_status()
    root = ET.fromstring(resp.text)
    articles = []
    for art in root.findall(".//PubmedArticle"):
        pmid = art.findtext(".//PMID", default="")
        title = art.findtext(".//ArticleTitle", default="(no title)")
        parts = [el.text or "" for el in art.findall(".//Abstract/AbstractText")]
        abstract = " ".join(p.strip() for p in parts if p).strip() or "(no abstract)"
        articles.append({"pmid": pmid, "title": title, "abstract": abstract})
    return articles

def get_sources(query, max_results=5):
    """Search + fetch in one step."""
    pmids = search_pubmed(query, max_results=max_results)
    time.sleep(0.4)   # be polite to NCBI's servers
    return fetch_abstracts(pmids)

if __name__ == "__main__":
    for s in get_sources("vitamin D deficiency and depression", max_results=3):
        print(f"[{s['pmid']}] {s['title']}")
        print(s["abstract"][:200], "...\n")
