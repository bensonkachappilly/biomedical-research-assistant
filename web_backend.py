from dotenv import load_dotenv
import anthropic
from pubmed import get_sources
from core import check_citations

load_dotenv()
client = anthropic.Anthropic()
MODEL = "claude-sonnet-4-6"

SYSTEM = (
    "You are a careful biomedical research assistant. "
    "Answer ONLY using the numbered abstracts provided. "
    "Cite every claim with its PubMed ID like [PMID: 12345678]. "
    "If the abstracts don't contain enough to answer, say so plainly."
)

def in_scope(question):
    resp = client.messages.create(
        model=MODEL, max_tokens=5,
        system="Answer only 'yes' or 'no'. Is this a biomedical, clinical, or "
               "health-science research question?",
        messages=[{"role": "user", "content": question}],
    )
    return "".join(b.text for b in resp.content if b.type == "text").strip().lower().startswith("y")

def answer_question(question, max_results=6):
    if not in_scope(question):
        return {"status": "refused_scope",
                "answer": "I only answer biomedical/health research questions.",
                "sources": []}

    sources = get_sources(question, max_results=max_results)
    if not sources:
        return {"status": "no_results",
                "answer": "No PubMed results were found for that question.",
                "sources": []}

    context = "\n\n".join(
        f"[{i}] PMID {s['pmid']} — {s['title']}\n{s['abstract']}"
        for i, s in enumerate(sources, start=1)
    )
    msg = client.messages.create(
        model=MODEL, max_tokens=900, system=SYSTEM,
        messages=[{"role": "user", "content": f"Question: {question}\n\nAbstracts:\n{context}"}],
    )
    answer = "".join(b.text for b in msg.content if b.type == "text")

    valid = {s["pmid"] for s in sources}
    status, _ = check_citations(answer, valid)
    if status == "blocked_hallucinated_citation":
        answer = "The model produced an unsupported citation, so the answer was withheld."
    return {"status": status, "answer": answer, "sources": sources}