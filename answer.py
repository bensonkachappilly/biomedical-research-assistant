# Import packages and functions
from dotenv import load_dotenv
import anthropic
from pubmed import get_sources

load_dotenv()
client = anthropic.Anthropic()

def build_context(sources):
    """Format article metadata into a numbered context block for the prompt.

    Args:
        sources (list[dict]): Article dicts with keys pmid, title, and abstract
            (as returned by get_sources).

    Returns:
        str: Newline-separated numbered entries in the form
            "[N] PMID <pmid> — <title>\\n<abstract>", ready to embed in a prompt.
    """
    return "\n\n".join(
        f"[{i}] PMID {s['pmid']} — {s['title']}\n{s['abstract']}"
        for i, s in enumerate(sources, start=1)
    )

def answer_question(question, max_results=5):
    """Answer a biomedical question using PubMed abstracts as grounding.

    Retrieves relevant PubMed articles for the question, then prompts Claude
    to answer using only those abstracts with inline citations.

    Args:
        question (str): The biomedical question to answer.
        max_results (int): Number of PubMed articles to retrieve. Defaults to 5.

    Returns:
        tuple[str, list[dict]]:
            - answer (str): Claude's response with inline citations, or a message
              indicating no results were found.
            - sources (list[dict]): The article dicts used to ground the answer
              (empty list if no results).
    """
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