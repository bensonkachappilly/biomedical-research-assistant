import asyncio
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import anthropic
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from core import check_citations, extract_pmids, CITATION_RE

load_dotenv()
client = anthropic.Anthropic()
MODEL = "claude-sonnet-4-6"

SYSTEM = (
    "You are a careful biomedical research assistant. "
    "Use the search_pubmed tool to gather evidence; you may search several times. "
    "Base your answer ONLY on returned abstracts. "
    "Cite every claim with the source's PubMed ID like [PMID: 12345678]. "
    "If the evidence is insufficient or mixed, say so plainly rather than guessing."
)

# ---------- GUARDRAIL 1: stay in scope ----------
def in_scope(question):
    """Check whether a question falls within the biomedical/health-science domain.

    Args:
        question (str): The user's question to classify.

    Returns:
        bool: True if Claude classifies the question as biomedical, clinical, or
            health-science related; False otherwise.
    """
    resp = client.messages.create(
        model=MODEL,                      # a tiny call; swap to a cheaper model to save cost
        max_tokens=5,
        system="Answer only 'yes' or 'no'. Is this a biomedical, clinical, or "
               "health-science research question?",
        messages=[{"role": "user", "content": question}],
    )
    return "".join(b.text for b in resp.content if b.type == "text").strip().lower().startswith("y")

# ---------- OBSERVABILITY: record every step ----------
class Trace:
    def __init__(self, question):
        """Initialise a new trace for the given question.

        Args:
            question (str): The biomedical question being answered.
        """
        self.question, self.started = question, time.perf_counter()
        self.steps, self.in_tok, self.out_tok = [], 0, 0

    def model_call(self, resp, latency):
        """Record a Claude API call and accumulate token usage.

        Args:
            resp: The Anthropic Message response object.
            latency (float): Wall-clock seconds the call took.

        Returns:
            None
        """
        self.in_tok += resp.usage.input_tokens
        self.out_tok += resp.usage.output_tokens
        self.steps.append({"type": "model_call", "stop_reason": resp.stop_reason,
                           "input_tokens": resp.usage.input_tokens,
                           "output_tokens": resp.usage.output_tokens,
                           "latency_s": round(latency, 2)})

    def tool_call(self, name, query, chars, latency):
        """Record an MCP tool call.

        Args:
            name (str): Name of the tool that was called.
            query (str): The search query passed to the tool.
            chars (int): Character count of the tool's response text.
            latency (float): Wall-clock seconds the call took.

        Returns:
            None
        """
        self.steps.append({"type": "tool_call", "tool": name, "query": query,
                           "result_chars": chars, "latency_s": round(latency, 2)})

    def save(self, answer, refs, status):
        """Serialise the trace to a timestamped JSON file in the traces/ directory.

        Args:
            answer (str): The final answer or refusal message.
            refs (dict): PMID-to-title mapping of all retrieved sources.
            status (str): Outcome label (e.g. "answered", "refused_scope",
                "blocked_hallucinated_citation", "max_steps").

        Returns:
            str: Path to the written trace file (e.g. "traces/20260619_143021.json").
        """
        # Sonnet 4.6 rates are approximate — confirm at docs.claude.com (pricing).
        cost = (self.in_tok / 1e6) * 3.0 + (self.out_tok / 1e6) * 15.0
        record = {"question": self.question, "status": status, "answer": answer,
                  "sources": list(refs.keys()),
                  "total_latency_s": round(time.perf_counter() - self.started, 2),
                  "input_tokens": self.in_tok, "output_tokens": self.out_tok,
                  "est_cost_usd": round(cost, 4), "steps": self.steps}
        Path("traces").mkdir(exist_ok=True)
        path = f"traces/{datetime.now():%Y%m%d_%H%M%S}.json"
        Path(path).write_text(json.dumps(record, indent=2))
        return path

async def run(question, max_steps=6):
    """Run the traced agentic search-and-answer loop with guardrails.

    Applies three guardrails: scope check before spending tokens, a hard cap on
    search iterations, and citation hallucination detection before returning the
    answer. Every model and tool call is recorded in a Trace and written to disk.

    Args:
        question (str): The biomedical question to answer.
        max_steps (int): Maximum number of search-response cycles before stopping.
            Defaults to 6.

    Returns:
        tuple[str, dict, str]:
            - answer (str): Claude's final answer, a refusal message, or a
              guardrail-blocked message.
            - refs (dict): Collected references keyed by PMID string, with article
              title as the value.
            - trace_path (str): Path to the JSON trace file written by Trace.save().
    """
    trace = Trace(question)

    if not in_scope(question):                      # guardrail 1, before spending money
        path = trace.save("Refused: out of scope.", {}, "refused_scope")
        return "I only answer biomedical/health research questions.", {}, path

    server = StdioServerParameters(command=sys.executable, args=["pubmed_server.py"])
    async with stdio_client(server) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            mcp_tools = (await session.list_tools()).tools
            tools = [{"name": t.name, "description": t.description,
                      "input_schema": t.inputSchema} for t in mcp_tools]

            messages, refs = [{"role": "user", "content": question}], {}
            for _ in range(max_steps):              # guardrail 3: hard cap on the loop
                t0 = time.perf_counter()
                resp = client.messages.create(model=MODEL, max_tokens=1200,
                                              system=SYSTEM, tools=tools, messages=messages)
                trace.model_call(resp, time.perf_counter() - t0)
                messages.append({"role": "assistant", "content": resp.content})

                if resp.stop_reason != "tool_use":
                    answer = "".join(b.text for b in resp.content if b.type == "text")
                    status, reason = check_citations(answer, refs.keys())   # guardrail 2
                    if status == "blocked_hallucinated_citation":
                        answer = f"[Answer withheld — failed guardrail: {reason}]"
                    path = trace.save(answer, refs, status)
                    return answer, refs, path

                results = []
                for block in resp.content:
                    if block.type == "tool_use":
                        t1 = time.perf_counter()
                        out = await session.call_tool(block.name, block.input)
                        text = "\n".join(c.text for c in out.content if c.type == "text")
                        trace.tool_call(block.name, block.input.get("query"), len(text),
                                       time.perf_counter() - t1)
                        for m in re.finditer(r"\[PMID (\d+)\]\s*(.+)", text):
                            refs.setdefault(m.group(1), m.group(2).strip())
                        results.append({"type": "tool_result", "tool_use_id": block.id,
                                        "content": text})
                messages.append({"role": "user", "content": results})

            path = trace.save("Stopped: max steps reached.", refs, "max_steps")
            return "Stopped: reached the step limit.", refs, path

if __name__ == "__main__":
    q = "Does vitamin D deficiency increase the risk of depression in adults?"
    answer, refs, trace_file = asyncio.run(run(q))
    print("\nANSWER:\n", answer)
    print("\nREFERENCES:")
    for pmid, title in refs.items():
        print(f"[PMID {pmid}] {title} — https://pubmed.ncbi.nlm.nih.gov/{pmid}/")
    print(f"\nTrace written to: {trace_file}")