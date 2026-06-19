import asyncio
import re
import sys
from dotenv import load_dotenv
import anthropic
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv()
client = anthropic.Anthropic()

SYSTEM = (
    "You are a careful biomedical research assistant. "
    "To answer, use the search_pubmed tool. "
    "You may search several times with refined queries until you have enough evidence. "
    "Base your answer ONLY on abstracts returned by the tool. "
    "Cite every claim with the source's PubMed ID like [PMID: 12345678]. "
    "If the evidence is insufficient or mixed, say so plainly rather than guessing."
)

PMID_RE = re.compile(r"\[PMID (\d+)\]\s*(.+)")

def collect_refs(text, refs):
    """Extract PMID-to-title mappings from formatted abstract text and merge into refs.

    Args:
        text (str): Text containing "[PMID <id>] <title>" lines, as returned by
            the MCP search_pubmed tool.
        refs (dict): Existing PMID-to-title mapping to update in place. New PMIDs
            are added; existing ones are left unchanged (setdefault semantics).

    Returns:
        None
    """
    for m in PMID_RE.finditer(text):
        refs.setdefault(m.group(1), m.group(2).strip())

async def run(question, max_steps=6):
    """Run the agentic MCP search-and-answer loop.

    Launches pubmed_server.py as a subprocess MCP server, discovers its tools,
    then drives a Claude agent loop that iteratively calls search_pubmed until
    it has enough evidence to write a final cited answer.

    Args:
        question (str): The biomedical question to answer.
        max_steps (int): Maximum number of search-response cycles before stopping.
            Defaults to 6.

    Returns:
        tuple[str, dict]:
            - answer (str): Claude's final answer with [PMID: ...] citations, or a
              timeout message if max_steps was reached.
            - refs (dict): Collected references keyed by PMID string, with article
              title as the value.
    """
    # Launch the server as a subprocess. sys.executable ensures it uses the
    # SAME conda environment you're running this from.
    server_params = StdioServerParameters(command=sys.executable, args=["pubmed_server.py"])

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Discover tools FROM the server, then convert to Anthropic's format.
            mcp_tools = (await session.list_tools()).tools
            tools = [{
                "name": t.name,
                "description": t.description,
                "input_schema": t.inputSchema,
            } for t in mcp_tools]
            print("Tools discovered from MCP server:", [t["name"] for t in tools])

            messages = [{"role": "user", "content": question}]
            refs = {}

            for _ in range(max_steps):
                resp = client.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=1200,
                    system=SYSTEM,
                    tools=tools,
                    messages=messages,
                )
                messages.append({"role": "assistant", "content": resp.content})

                if resp.stop_reason != "tool_use":
                    answer = "".join(b.text for b in resp.content if b.type == "text")
                    return answer, refs

                results = []
                for block in resp.content:
                    if block.type == "tool_use":
                        print(f"  [calling MCP tool {block.name}: {block.input.get('query')!r}]")
                        # The tool now runs THROUGH the MCP server (note the await):
                        mcp_result = await session.call_tool(block.name, block.input)
                        text = "\n".join(
                            c.text for c in mcp_result.content if c.type == "text"
                        )
                        collect_refs(text, refs)
                        results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": text,
                        })
                messages.append({"role": "user", "content": results})

            return "Stopped: reached the maximum number of steps.", refs

if __name__ == "__main__":
    q = "Does vitamin D deficiency increase the risk of depression in adults?"
    answer, refs = asyncio.run(run(q))
    print("\nANSWER:\n", answer)
    print("\nREFERENCES:")
    for pmid, title in refs.items():
        print(f"[PMID {pmid}] {title} — https://pubmed.ncbi.nlm.nih.gov/{pmid}/")