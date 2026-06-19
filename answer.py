# Import packages and functions
from dotenv import load_dotenv
import anthropic
from pubmed import get_sources

load_dotenv()
client = anthropic.Anthropic()

def build_context(sources):
    """Number each source so Claude can cite it as [1], [2], ..."""
    return "\n\n".join(
        f"[{i}] PMID {s['pmid']} — {s['title']}\n{s['abstract']}"
        for i, s in enumerate(sources, start=1)
    )

def answer_question(question, max_results=5):
    sources = get_sources(question, max_results=max_results)
    if not sources:
        return "No PubMed results found.", []

    system = (
        "You are a careful biomedical research assistant. "
        "Answer ONLY using the numbered abstracts provided. "
        "Cite every claim with its source number in square brackets, e.g. [1]. "
        "If the abstracts don't contain enough to answer, say so plainly. "
        "Do not use outside knowledge."
    )
    user = f"Question: {question}\n\nAbstracts:\n{build_context(sources)}"

    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=800,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return msg.content[0].text, sources

if __name__ == "__main__":
    q = "Does vitamin D deficiency increase the risk of depression?"
    text, sources = answer_question(q)
    print("ANSWER:\n", text, "\n\nREFERENCES:")
    for i, s in enumerate(sources, start=1):
        print(f"[{i}] {s['title']} — https://pubmed.ncbi.nlm.nih.gov/{s['pmid']}/")