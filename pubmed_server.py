# Import packages and functions
from mcp.server.fastmcp import FastMCP
from pubmed import get_sources

mcp = FastMCP("pubmed")

@mcp.tool()
def search_pubmed(query: str, max_results: int = 5) -> str:
    """Search PubMed for biomedical abstracts and return them as text.

    Args:
        query (str): A focused PubMed search query.
        max_results (int): Number of articles to return, clamped to [1, 8]. Defaults to 5.

    Returns:
        str: Formatted abstracts as "[PMID <id>] <title>\\n<abstract>" blocks joined
            by double newlines, or an error message if no results were found.
    """
    max_results = max(1, min(int(max_results), 8))
    sources = get_sources(query, max_results=max_results)
    if not sources:
        return "No results for that query. Try a broader query."
    return "\n\n".join(
        f"[PMID {s['pmid']}] {s['title']}\n{s['abstract']}" for s in sources
    )

if __name__ == "__main__":
    mcp.run()   # runs over stdio — waits silently for a client to connect