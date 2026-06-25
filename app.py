import streamlit as st
from web_backend import answer_question

st.set_page_config(page_title="BioScout — Evidence from PubMed", page_icon="🔬", layout="centered")

# ---------- styling ----------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
#MainMenu, footer { visibility: hidden; }

.hero {
    background: linear-gradient(135deg, #0E7C7B 0%, #134E5E 100%);
    padding: 2.2rem 2rem; border-radius: 16px; color: white;
    margin-bottom: 1.6rem; box-shadow: 0 8px 28px rgba(14,124,123,0.20);
}
.hero h1 { color: #fff; font-size: 2.1rem; font-weight: 700; margin: 0; letter-spacing: -0.5px; }
.hero p  { color: rgba(255,255,255,0.9); font-size: 1.02rem; margin: 0.5rem 0 0; line-height: 1.5; }

.pill { display:inline-block; padding: 5px 14px; border-radius: 999px;
        font-size: 0.82rem; font-weight: 600; margin: 0.2rem 0 0.6rem; }
.pill-ok   { background:#E3F2EF; color:#0E7C7B; }
.pill-warn { background:#FDECEC; color:#C0392B; }
.src-pmid  { color:#0E7C7B; font-size:0.85rem; font-weight:600; }
</style>
""", unsafe_allow_html=True)

# ---------- state ----------
if "question" not in st.session_state:
    st.session_state.question = ""

def use_example(text):
    st.session_state.question = text

# ---------- sidebar ----------
with st.sidebar:
    st.markdown("### 🔬 About BioScout")
    st.write("BioScout answers biomedical research questions using live evidence from "
             "PubMed, and cites every claim so you can verify it yourself.")
    st.markdown("**How it works**")
    st.markdown(
        "- Searches PubMed via the E-utilities API\n"
        "- Reads the abstracts with Claude\n"
        "- Answers *only* from retrieved sources\n"
        "- Guardrails withhold unsupported citations"
    )
    st.markdown("[📂 View the code on GitHub]"
                "(https://github.com/bensonkachappilly/biomedical-research-assistant)")
    st.divider()
    st.caption("Educational demo. Not medical advice.")

# ---------- hero ----------
st.markdown("""
<div class="hero">
  <h1>🔬 BioScout</h1>
  <p>Evidence-based answers to biomedical questions — grounded in live PubMed research,
  with citations you can verify.</p>
</div>
""", unsafe_allow_html=True)

# ---------- examples ----------
EXAMPLES = [
    "Does vitamin D deficiency increase the risk of depression?",
    "Is metformin associated with reduced cancer risk in type 2 diabetes?",
    "What are the cardiovascular effects of intermittent fasting?",
]
st.markdown("**Try an example**")
cols = st.columns(len(EXAMPLES))
for i, (col, ex) in enumerate(zip(cols, EXAMPLES)):
    label = ex if len(ex) < 38 else ex[:35] + "…"
    col.button(label, key=f"ex_{i}", on_click=use_example, args=(ex,), use_container_width=True)

# ---------- input ----------
st.text_input("Your question", key="question",
              placeholder="Ask a biomedical research question…", label_visibility="collapsed")
search = st.button("Search PubMed", type="primary", use_container_width=True)

# ---------- results ----------
def render(result):
    status = result["status"]
    if status in ("refused_scope", "no_results"):
        st.markdown('<span class="pill pill-warn">Out of scope</span>'
                    if status == "refused_scope"
                    else '<span class="pill pill-warn">No results found</span>',
                    unsafe_allow_html=True)
        st.info(result["answer"])
        return

    n = len(result["sources"])
    st.markdown(f'<span class="pill pill-ok">Grounded in {n} PubMed source'
                f'{"s" if n != 1 else ""}</span>', unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown("#### Answer")
        st.markdown(result["answer"])

    st.markdown("#### Sources")
    for i, s in enumerate(result["sources"], start=1):
        url = f"https://pubmed.ncbi.nlm.nih.gov/{s['pmid']}/"
        with st.container(border=True):
            st.markdown(f"**[{i}] {s['title']}**")
            st.markdown(f"<span class='src-pmid'>PMID {s['pmid']}</span> · "
                        f"[View on PubMed]({url})", unsafe_allow_html=True)

if search and st.session_state.question.strip():
    with st.spinner("Searching PubMed and reading the latest abstracts…"):
        result = answer_question(st.session_state.question)
    render(result)

st.divider()
st.caption("BioScout is an educational demonstration and does not provide medical advice. "
           "Always consult a qualified professional.")