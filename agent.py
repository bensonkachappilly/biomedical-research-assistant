# Import packages and functions
from dotenv import load_dotenv
import anthropic
from pubmed import get_sources

load_dotenv()
client = anthropic.Anthropic()

SYSTEM = (
    "You are a careful biomedical research assistant. "
    "To answer, search PubMed using the search_pubmed tool. "
    "You may search several times with refined queries until you have enough evidence. "
    "Base your answer ONLY on abstracts returned by the tool. "
    "Cite every claim with the source's PubMed ID like [PMID: 12345678]. "
    "If the evidence is insufficient or mixed, say so plainly rather than guessing."
)

# This is how you DESCRIBE a tool to Claude. It never sees your Python code —
# only this schema. Claude uses the description to decide when to call it.
TOOLS = [{
    "name": "search_pubmed",
    "description": (
        "Search PubMed for biomedical research abstracts. Call this to gather "
        "evidence before answering. You can call it several times with different "
        "or more specific queries."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "A focused PubMed search query"},
            "max_results": {"type": "integer", "description": "Number of articles, 1-8"},
        },
        "required": ["query"],
    },
}]

def run_search(query, max_results=5, collected=None):
    """Execute a PubMed search and optionally accumulate results across calls.

    Args:
        query (str): PubMed search query to run.
        max_results (int): Number of articles to fetch, clamped to [1, 8]. Defaults to 5.
        collected (dict | None): If provided, article dicts are merged into this dict
            keyed by PMID to deduplicate results across multiple searches.

    Returns:
        str: Formatted abstracts as "[PMID <id>] <title>\\n<abstract>" blocks joined
            by double newlines, or an error message if no results were found.
    """
    max_results = max(1, min(int(max_results or 5), 8))
    sources = get_sources(query, max_results=max_results)
    if collected is not None:
        for s in sources:
            collected[s["pmid"]] = s          # dedupe by PMID across searches
    if not sources:
        return "No results for that query. Try a broader query."
    return "\n\n".join(
        f"[PMID {s['pmid']}] {s['title']}\n{s['abstract']}" for s in sources
    )

def ask(question, max_steps=6):
    """Run the agentic search-and-answer loop.

    Sends the question to Claude with the search_pubmed tool available. Claude
    iteratively calls the tool with refined queries until it has enough evidence
    or max_steps is reached, then writes a final cited answer.

    Args:
        question (str): The biomedical question to answer.
        max_steps (int): Maximum number of search-response cycles before stopping.
            Defaults to 6.

    Returns:
        tuple[str, dict]:
            - answer (str): Claude's final answer with PMID citations, or a
              timeout message if max_steps was reached.
            - collected (dict): All retrieved articles, keyed by PMID, with keys
              pmid, title, and abstract.
    """
    messages = [{"role": "user", "content": question}]
    collected = {}

    for step in range(max_steps):
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1200,
            system=SYSTEM,
            tools=TOOLS,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": resp.content})

        # If Claude didn't ask for a tool, it has written its final answer.
        if resp.stop_reason != "tool_use":
            answer = "".join(b.text for b in resp.content if b.type == "text")
            return answer, collected

        # Otherwise, run every search Claude requested and feed results back.
        results = []
        for block in resp.content:
            if block.type == "tool_use" and block.name == "search_pubmed":
                print(f"  [agent searching: {block.input.get('query')!r}]")
                text = run_search(**block.input, collected=collected)
                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": text,
                })
        messages.append({"role": "user", "content": results})

    return "Stopped: reached the maximum number of search steps.", collected

def reflect(question, answer, collected):
    """Review and correct a draft answer against the retrieved source abstracts.

    Sends the draft answer and all collected abstracts to Claude acting as a
    strict reviewer. Returns the original answer unchanged if no sources were
    collected.

    Args:
        question (str): The original biomedical question.
        answer (str): The draft answer produced by ask().
        collected (dict): Articles keyed by PMID (as returned by ask()), used
            to verify every factual claim in the draft.

    Returns:
        str: A corrected answer with unsupported claims removed or flagged and
            all remaining claims backed by [PMID: ...] citations. Returns the
            original answer if collected is empty.
    """
    if not collected:
        return answer
    sources_text = "\n\n".join(
        f"[PMID {s['pmid']}] {s['title']}\n{s['abstract']}" for s in collected.values()
    )
    review_system = (
        "You are a strict reviewer. Check the draft answer against the abstracts. "
        "Every factual claim must be supported by a cited [PMID: ...]. "
        "Remove or flag anything unsupported, keep good citations, and return only "
        "the corrected final answer."
    )
    user = f"Question: {question}\n\nDraft answer:\n{answer}\n\nAbstracts:\n{sources_text}"
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1200,
        system=review_system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(b.text for b in msg.content if b.type == "text")

if __name__ == "__main__":
    q = "Does vitamin D deficiency increase the risk of depression in adults?"
    print(f"Question: {q}\n")

    draft, collected = ask(q)
    print("\nDRAFT ANSWER:\n", draft)

    final = reflect(q, draft, collected)
    print("\nREVIEWED ANSWER:\n", final)

    print("\nREFERENCES:")
    for s in collected.values():
        print(f"[PMID {s['pmid']}] {s['title']} — https://pubmed.ncbi.nlm.nih.gov/{s['pmid']}/")
