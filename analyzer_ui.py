"""
Log Analyzer — Chat UI
Run: streamlit run analyzer_ui.py
"""
import streamlit as st
import requests
import json
import os

from qdrant_client import QdrantClient

@st.cache_resource
def get_qdrant():
    return QdrantClient(path="data/qdrant_db")

# ─── page config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Log Analyzer | LogSense",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── styles ───────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=JetBrains+Mono:wght@400;500&family=Inter:wght@300;400;500&display=swap');

:root {
    --bg:       #07090e;
    --surface:  #0f1117;
    --surface2: #141720;
    --border:   #1a1e2a;
    --accent:   #4f8ef7;
    --accent2:  #a259f7;
    --success:  #22c55e;
    --warn:     #f59e0b;
    --danger:   #ef4444;
    --text:     #e2e8f0;
    --muted:    #64748b;
    --user-bg:  linear-gradient(135deg, #1a2540, #1a1040);
    --bot-bg:   var(--surface2);
}

html, body, [data-testid="stAppViewContainer"] {
    background: var(--bg) !important; color: var(--text) !important;
    font-family: 'Inter', sans-serif;
}
[data-testid="stHeader"] { background: transparent !important; }
h1,h2,h3 { font-family: 'Syne', sans-serif !important; }

/* sidebar */
[data-testid="stSidebar"] {
    background: var(--surface) !important;
    border-right: 1px solid var(--border) !important;
}
[data-testid="stSidebar"] * { color: var(--text) !important; }

/* chat messages */
.user-msg {
    display: flex; justify-content: flex-end; margin: 12px 0;
}
.user-bubble {
    background: var(--user-bg); border: 1px solid rgba(79,142,247,.2);
    border-radius: 16px 4px 16px 16px;
    padding: 12px 18px; max-width: 70%;
    font-size: .93rem;
}
.bot-msg {
    display: flex; gap: 12px; margin: 12px 0;
}
.bot-avatar {
    width: 36px; height: 36px; flex-shrink: 0;
    background: linear-gradient(135deg, var(--accent), var(--accent2));
    border-radius: 50%; display: flex; align-items: center;
    justify-content: center; font-size: 1rem;
}
.bot-bubble {
    background: var(--bot-bg); border: 1px solid var(--border);
    border-radius: 4px 16px 16px 16px;
    padding: 14px 20px; flex: 1;
    font-size: .92rem; line-height: 1.65;
}

/* incident card */
.inc-card {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 10px; padding: 14px 18px; margin: 10px 0;
    font-size: .82rem;
}
.inc-card .field { display: flex; gap: 10px; margin-bottom: 6px; align-items: flex-start; }
.inc-card .key { color: var(--muted); min-width: 110px; font-size: .78rem; text-transform: uppercase; letter-spacing: .05em; }
.inc-card .val { color: var(--text); font-family: 'JetBrains Mono', monospace; font-size: .8rem; }
.status-active { color: var(--warn); }
.status-inactive { color: var(--success); }

/* code chunk */
.chunk-card {
    background: #0a0d14; border: 1px solid var(--border);
    border-radius: 8px; overflow: hidden; margin: 8px 0;
}
.chunk-header {
    background: var(--surface2); padding: 6px 14px;
    font-family: 'JetBrains Mono', monospace; font-size: .72rem;
    color: var(--muted); display: flex; justify-content: space-between;
}
.chunk-body { padding: 12px 14px; font-family: 'JetBrains Mono', monospace;
    font-size: .78rem; overflow-x: auto; white-space: pre; color: #c8d3f5; }

/* health check */
.health-item {
    background: var(--surface2); border: 1px solid var(--border);
    border-radius: 8px; padding: 10px 14px; margin: 6px 0; font-size: .83rem;
}

/* input area */
.stTextInput input {
    background: var(--surface) !important; border: 1px solid var(--border) !important;
    border-radius: 10px !important; color: var(--text) !important;
    font-family: 'JetBrains Mono', monospace !important; font-size: .9rem !important;
}
.stTextInput input:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 2px rgba(79,142,247,.2) !important;
}
.stButton > button {
    background: linear-gradient(135deg, var(--accent), var(--accent2)) !important;
    color: #fff !important; border: none !important; border-radius: 8px !important;
    font-family: 'Syne', sans-serif !important; font-weight: 600 !important;
}

/* top bar */
.top-bar {
    display: flex; align-items: center; justify-content: space-between;
    padding: 10px 0 22px; border-bottom: 1px solid var(--border); margin-bottom: 24px;
}
.logo { font-family:'Syne',sans-serif; font-weight:800; font-size:1.4rem;
    background:linear-gradient(135deg,var(--accent),var(--accent2));
    -webkit-background-clip:text; -webkit-text-fill-color:transparent; }
.nav-tag { font-family:'JetBrains Mono',monospace; font-size:.72rem;
    color:var(--warn); background:rgba(245,158,11,.1);
    border:1px solid rgba(245,158,11,.25); border-radius:4px; padding:3px 10px; }

div[data-testid="stExpander"] {
    background: var(--surface) !important; border: 1px solid var(--border) !important;
    border-radius: 10px !important;
}
</style>
""", unsafe_allow_html=True)

# ─── session state ────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []

# ─── sidebar — incident list ──────────────────────────────────────────────────
from incident_db import list_incidents

with st.sidebar:
    st.markdown("""
    <div style="font-family:'Syne',sans-serif; font-weight:800; font-size:1.25rem;
                background:linear-gradient(135deg,#4f8ef7,#a259f7);
                -webkit-background-clip:text; -webkit-text-fill-color:transparent;
                margin-bottom:4px;">
        LogSense
    </div>
    <div style="color:#64748b; font-size:.78rem; margin-bottom:20px;">Log Analyzer</div>
    """, unsafe_allow_html=True)

    st.markdown("#### 📋 Open Incidents")
    incidents = list_incidents()
    for inc in incidents:
        status_color = "#f59e0b" if inc["status"] == "active" else "#22c55e"
        st.markdown(f"""
        <div style="background:#111318; border:1px solid #1e2230; border-radius:8px;
                    padding:10px 14px; margin-bottom:8px; cursor:pointer;">
            <div style="font-family:'JetBrains Mono',monospace; font-size:.8rem;
                        color:#4f8ef7;">{inc['incident_number']}</div>
            <div style="font-size:.78rem; color:#94a3b8; margin:3px 0;
                        white-space:nowrap; overflow:hidden; text-overflow:ellipsis;"
                 title="{inc['error_description']}">
                {inc['error_description'][:55]}…
            </div>
            <div style="font-size:.72rem; color:{status_color};">● {inc['status'].upper()}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    if st.button("🗑 Clear Chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# ─── main area ────────────────────────────────────────────────────────────────
st.markdown("""
<div class="top-bar">
    <div class="logo">⚡ LogSense</div>
    <div class="nav-tag">Log Analyzer</div>
</div>
""", unsafe_allow_html=True)

# Welcome banner (only when no messages)
if not st.session_state.messages:
    st.markdown("""
    <div style="background:#0f1117; border:1px solid #1a1e2a; border-radius:14px;
                padding:28px 32px; margin-bottom:28px; text-align:center;">
        <div style="font-size:2.5rem; margin-bottom:8px;">🔬</div>
        <div style="font-family:'Syne',sans-serif; font-weight:700; font-size:1.4rem; margin-bottom:8px;">
            Incident Intelligence
        </div>
        <div style="color:#64748b; font-size:.9rem; max-width:480px; margin:0 auto;">
            Enter an incident number below to trigger end-to-end log analysis —
            I'll fetch the incident, retrieve logs, scan relevant code, run health checks,
            and generate actionable troubleshooting steps.
        </div>
        <div style="margin-top:20px; display:flex; gap:10px; justify-content:center; flex-wrap:wrap;">
            <span style="background:rgba(79,142,247,.1); border:1px solid rgba(79,142,247,.2);
                         color:#4f8ef7; border-radius:6px; padding:5px 14px; font-size:.8rem;
                         font-family:'JetBrains Mono',monospace;">INC001</span>
            <span style="background:rgba(79,142,247,.1); border:1px solid rgba(79,142,247,.2);
                         color:#4f8ef7; border-radius:6px; padding:5px 14px; font-size:.8rem;
                         font-family:'JetBrains Mono',monospace;">INC002</span>
            <span style="background:rgba(79,142,247,.1); border:1px solid rgba(79,142,247,.2);
                         color:#4f8ef7; border-radius:6px; padding:5px 14px; font-size:.8rem;
                         font-family:'JetBrains Mono',monospace;">INC003</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

# # ─── render chat history ─────────────────────────────────────────────────────
# for msg in st.session_state.messages:
#     if msg["role"] == "user":
#         st.markdown(f"""
#         <div class="user-msg">
#             <div class="user-bubble">{msg['content']}</div>
#         </div>
#         """, unsafe_allow_html=True)
#     else:
#         st.markdown("""<div class="bot-msg"><div class="bot-avatar">⚡</div><div class="bot-bubble">""",
#                     unsafe_allow_html=True)
#         # render sub-components stored in the message
#         _data = msg.get("data")
#         if _data:
#             _render_analysis(_data)   # defined below — called after definition
#         else:
#             st.markdown(msg["content"])
#         st.markdown("</div></div>", unsafe_allow_html=True)


# ─── render function (defined after initial render loop so it can be called) ─
def _render_analysis(data: dict):
    inc = data["incident"]

    # incident card
    status_cls = "status-active" if inc["status"] == "active" else "status-inactive"
    st.markdown(f"""
    <div class="inc-card">
        <div style="font-family:'Syne',sans-serif; font-weight:700; font-size:.95rem;
                    margin-bottom:10px; color:#4f8ef7;">
            📋 {inc['incident_number']} — {inc['application_name']}
        </div>
        <div class="field"><span class="key">Description</span>
            <span class="val">{inc['error_description'][:120]}…</span></div>
        <div class="field"><span class="key">User ID</span>
            <span class="val">{inc['user_id']}</span></div>
        <div class="field"><span class="key">Status</span>
            <span class="val {status_cls}">{inc['status'].upper()}</span></div>
        <div class="field"><span class="key">Created</span>
            <span class="val">{inc['created_time']}</span></div>
    </div>
    """, unsafe_allow_html=True)

    # health checks
    if data.get("health_checks"):
        with st.expander("🏥 Infrastructure Health Checks", expanded=False):
            for h in data["health_checks"]:
                st.markdown(f"""
                <div class="health-item">
                    <strong>{h['check']}</strong>
                    <div style="margin-top:4px;">{h['status']}</div>
                    <div style="color:#64748b; font-size:.78rem; margin-top:2px;">{h['detail']}</div>
                </div>
                """, unsafe_allow_html=True)

    # retrieved code chunks
    if data.get("code_chunks"):
        with st.expander(f"📂 Retrieved Code Chunks ({len(data['code_chunks'])})", expanded=False):
            for chunk in data["code_chunks"]:
                st.markdown(f"""
                <div class="chunk-card">
                    <div class="chunk-header">
                        <span>{chunk['metadata']}</span>
                        <span>score: {chunk['score']}</span>
                    </div>
                    <div class="chunk-body">{chunk['content'][:600]}{'…' if len(chunk['content'])>600 else ''}</div>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("ℹ️ No code indexed for this application. Use the Application Indexer to upload the source code.")

    # raw logs
    with st.expander("📜 Processed Logs", expanded=False):
        st.code(data["logs_clean"], language="text")

    # LLM analysis
    st.markdown("---")
    st.markdown(data["llm_response"])


# ─── render chat history ─────────────────────────────────────────────────────
for msg in st.session_state.messages:
    if msg["role"] == "user":
        st.markdown(f"""
        <div class="user-msg">
            <div class="user-bubble">{msg['content']}</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""<div class="bot-msg"><div class="bot-avatar">⚡</div><div class="bot-bubble">""",
                    unsafe_allow_html=True)
        # render sub-components stored in the message
        _data = msg.get("data")
        if _data:
            _render_analysis(_data)   # defined below — called after definition
        else:
            st.markdown(msg["content"])
        st.markdown("</div></div>", unsafe_allow_html=True)

# ─── input bar ───────────────────────────────────────────────────────────────
st.markdown("<div style='height:16px'/>", unsafe_allow_html=True)

col_input, col_btn = st.columns([5, 1])
with col_input:
    incident_input = st.text_input(
        label="",
        placeholder="Enter incident number (e.g. INC001) and press Analyze…",
        label_visibility="collapsed",
        key="incident_input",
    )
with col_btn:
    analyze_clicked = st.button("Analyze", use_container_width=True)


# ─── analysis trigger ─────────────────────────────────────────────────────────
if analyze_clicked and incident_input.strip():
    inc_num = incident_input.strip().upper()
    st.session_state.messages.append({"role": "user", "content": f"Analyze {inc_num}"})

    # pipeline
    from analyzer import run_analysis
    try:
        data = run_analysis(inc_num)
    except ValueError as e:
        st.session_state.messages.append({
            "role": "assistant",
            "content": f"❌ {e}",
            "data": None,
        })
        st.rerun()

    # call LLM
    prompt = data["analysis_prompt"]
    llm_response = "⚠️ LLM call failed — check your API key / connection."

    # try:
    #     import anthropic as _ant
    #     _client = _ant.Anthropic()
    #     _resp = _client.messages.create(
    #         model="claude-sonnet-4-20250514",
    #         max_tokens=1500,
    #         messages=[{"role": "user", "content": prompt}],
    #     )
    #     llm_response = _resp.content[0].text
    # except Exception as llm_err:
    #     # fallback: try openai-compatible endpoint from original llm_client
    #     try:
    #         from llm_client import LLMClient
    #         llm_response = LLMClient().generate(prompt)
    #     except Exception:
    #         llm_response = f"⚠️ LLM unavailable: {llm_err}\n\n**Prompt was prepared — add API key to enable generation.**"
    try:
        from llm_client import LLMClient
        llm_response = LLMClient().generate(prompt)
    except Exception as llm_err:
        llm_response = f"⚠️ LLM unavailable: {llm_err}\n\n"
    
    data["llm_response"] = llm_response

    st.session_state.messages.append({
        "role": "assistant",
        "content": "",
        "data": data,
    })
    st.rerun()

# re-render messages with data after rerun
# (the first render loop above handles this via `data` key)