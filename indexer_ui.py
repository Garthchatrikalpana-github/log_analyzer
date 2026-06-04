"""
Application Indexer — UI
Run: streamlit run indexer_ui.py
"""
import streamlit as st
import os

# ─── page config ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="App Indexer | LogSense",
    page_icon="🗂️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── global styles ───────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=JetBrains+Mono:wght@400;500&family=Inter:wght@300;400;500&display=swap');

:root {
    --bg:       #0a0c10;
    --surface:  #111318;
    --border:   #1e2230;
    --accent:   #4f8ef7;
    --accent2:  #a259f7;
    --success:  #22c55e;
    --warn:     #f59e0b;
    --danger:   #ef4444;
    --text:     #e2e8f0;
    --muted:    #64748b;
}

html, body, [data-testid="stAppViewContainer"] {
    background: var(--bg) !important;
    color: var(--text) !important;
    font-family: 'Inter', sans-serif;
}

[data-testid="stHeader"] { background: transparent !important; }

h1,h2,h3 { font-family: 'Syne', sans-serif; }

/* top nav bar */
.top-bar {
    display: flex; align-items: center; justify-content: space-between;
    padding: 14px 0 28px;
    border-bottom: 1px solid var(--border);
    margin-bottom: 32px;
}
.logo {
    font-family: 'Syne', sans-serif; font-weight: 800; font-size: 1.5rem;
    background: linear-gradient(135deg, var(--accent), var(--accent2));
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.nav-tag {
    font-family: 'JetBrains Mono', monospace; font-size: .75rem;
    color: var(--accent); background: rgba(79,142,247,.12);
    border: 1px solid rgba(79,142,247,.3); border-radius: 4px;
    padding: 3px 10px;
}

/* stat cards */
.stat-row { display: flex; gap: 16px; margin-bottom: 28px; }
.stat-card {
    flex: 1; background: var(--surface); border: 1px solid var(--border);
    border-radius: 12px; padding: 20px 24px;
}
.stat-card .label { font-size: .75rem; color: var(--muted); text-transform: uppercase; letter-spacing: .1em; margin-bottom: 6px; }
.stat-card .value { font-family: 'Syne', sans-serif; font-size: 2rem; font-weight: 700; color: var(--text); }
.stat-card .delta { font-size: .8rem; color: var(--success); margin-top: 2px; }

/* app table */
.app-row {
    display: flex; align-items: center; gap: 12px;
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 10px; padding: 16px 20px; margin-bottom: 10px;
    transition: border-color .2s;
}
.app-row:hover { border-color: var(--accent); }
.app-icon {
    width: 40px; height: 40px; border-radius: 8px;
    background: linear-gradient(135deg, var(--accent), var(--accent2));
    display: flex; align-items: center; justify-content: center;
    font-size: 1.1rem; flex-shrink: 0;
}
.app-name { font-family: 'Syne', sans-serif; font-weight: 600; font-size: 1rem; }
.app-meta { font-size: .78rem; color: var(--muted); margin-top: 2px; }
.badge {
    font-size: .7rem; font-family: 'JetBrains Mono', monospace;
    padding: 3px 8px; border-radius: 4px;
    background: rgba(79,142,247,.12); color: var(--accent);
    border: 1px solid rgba(79,142,247,.2);
}
.badge-green { background: rgba(34,197,94,.12); color: var(--success); border-color: rgba(34,197,94,.2); }

/* modal-like panel */
.panel {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 14px; padding: 28px 32px; margin-bottom: 24px;
}
.panel-title {
    font-family: 'Syne', sans-serif; font-size: 1.1rem; font-weight: 700;
    margin-bottom: 20px; display: flex; align-items: center; gap: 8px;
}

/* override streamlit inputs */
[data-testid="stTextInput"] input {
    background: #0f111a !important; border: 1px solid var(--border) !important;
    border-radius: 8px !important; color: var(--text) !important;
    font-family: 'Inter', sans-serif !important;
}
[data-testid="stTextInput"] input:focus {
    border-color: var(--accent) !important; box-shadow: 0 0 0 2px rgba(79,142,247,.2) !important;
}
[data-testid="stFileUploader"] {
    background: #0f111a !important; border: 1px dashed var(--border) !important;
    border-radius: 10px !important;
}
.stButton > button {
    background: linear-gradient(135deg, var(--accent), var(--accent2)) !important;
    color: #fff !important; border: none !important; border-radius: 8px !important;
    font-family: 'Syne', sans-serif !important; font-weight: 600 !important;
    padding: 10px 28px !important; font-size: .95rem !important;
    transition: opacity .2s !important;
}
.stButton > button:hover { opacity: .88 !important; }

/* section heading */
.section-head {
    font-family: 'Syne', sans-serif; font-size: 1.25rem; font-weight: 700;
    margin: 28px 0 16px; display: flex; align-items: center; gap: 10px;
}
.section-head::after {
    content: ''; flex: 1; height: 1px; background: var(--border);
}

div[data-testid="stAlert"] {
    border-radius: 8px !important;
}
</style>
""", unsafe_allow_html=True)

# ─── auth gate ───────────────────────────────────────────────────────────────
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    col_a, col_b, col_c = st.columns([1, 1.6, 1])
    with col_b:
        st.markdown("""
        <div style="text-align:center; padding: 60px 0 32px;">
            <div style="font-family:'Syne',sans-serif; font-weight:800; font-size:2rem;
                        background:linear-gradient(135deg,#4f8ef7,#a259f7);
                        -webkit-background-clip:text; -webkit-text-fill-color:transparent;">
                LogSense
            </div>
            <div style="color:#64748b; font-size:.9rem; margin-top:6px; margin-bottom:32px;">
                Application Intelligence Platform
            </div>
        </div>
        """, unsafe_allow_html=True)

        with st.container():
            st.markdown('<div class="panel">', unsafe_allow_html=True)
            st.markdown('<div class="panel-title">🔐 Sign in</div>', unsafe_allow_html=True)
            username = st.text_input("Username", placeholder="demo")
            password = st.text_input("Password", type="password", placeholder="••••••••")
            if st.button("Sign In", use_container_width=True):
                if username == "demo" and password == "demo":
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("Invalid credentials. Use demo / demo")
            st.markdown("</div>", unsafe_allow_html=True)
            st.caption("Demo credentials: **demo** / **demo**")
    st.stop()

# ─── main app ────────────────────────────────────────────────────────────────
from indexer import list_apps, app_exists, index_application, UPLOAD_DIR

# top bar
st.markdown("""
<div class="top-bar">
    <div class="logo">⚡ LogSense</div>
    <div class="nav-tag">Application Indexer</div>
</div>
""", unsafe_allow_html=True)

apps = list_apps()

# stats
total_apps   = len(apps)
total_chunks = sum(a.get("chunk_count", 0) for a in apps)
st.markdown(f"""
<div class="stat-row">
    <div class="stat-card">
        <div class="label">Indexed Applications</div>
        <div class="value">{total_apps}</div>
        <div class="delta">↑ ready for analysis</div>
    </div>
    <div class="stat-card">
        <div class="label">Total Code Chunks</div>
        <div class="value">{total_chunks:,}</div>
        <div class="delta">semantic units indexed</div>
    </div>
    <div class="stat-card">
        <div class="label">Index Engine</div>
        <div class="value" style="font-size:1.1rem; margin-top:6px;">MiniLM-L6</div>
        <div class="delta">AST-aware chunking</div>
    </div>
</div>
""", unsafe_allow_html=True)

# ── two-column layout ─────────────────────────────────────────────────────────
left, right = st.columns([1.1, 1], gap="large")

with right:
    st.markdown('<div class="section-head">➕ Index New Application</div>', unsafe_allow_html=True)
    with st.container():
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        app_name = st.text_input(
            "Application Name",
            placeholder="e.g. mini-commerce",
            help="Used as the collection name. Must be unique.",
        )
        zip_file = st.file_uploader(
            "Source Code (ZIP)",
            type=["zip"],
            help="Upload a ZIP containing your application's source code",
        )

        if st.button("🚀 Create Index", use_container_width=True):
            if not app_name.strip():
                st.error("Application name is required.")
            elif not zip_file:
                st.error("Please upload a ZIP file.")
            elif app_exists(app_name.strip()):
                st.error(f"⚠️ Application **'{app_name}'** is already indexed. Choose a different name.")
            else:
                with st.spinner("Chunking & embedding source code…"):
                    result = index_application(
                        app_name=app_name.strip(),
                        zip_bytes=zip_file.read(),
                        zip_filename=zip_file.name,
                    )
                if result["ok"]:
                    st.success(
                        f"✅ **{app_name}** indexed successfully — "
                        f"**{result['chunk_count']}** semantic chunks stored."
                    )
                    st.rerun()
                else:
                    st.error(f"Indexing failed: {result['error']}")

        st.markdown("</div>", unsafe_allow_html=True)

with left:
    st.markdown('<div class="section-head">📦 Indexed Applications</div>', unsafe_allow_html=True)

    if not apps:
        st.markdown("""
        <div style="color:#64748b; font-size:.9rem; padding: 24px;
                    background:#111318; border:1px dashed #1e2230; border-radius:10px; text-align:center;">
            No applications indexed yet.<br>Upload a ZIP on the right to get started.
        </div>
        """, unsafe_allow_html=True)
    else:
        for app in apps:
            zip_path = os.path.join(UPLOAD_DIR, f"{app['name']}__{app['zip_filename']}")
            has_zip  = os.path.isfile(zip_path)

            st.markdown(f"""
            <div class="app-row">
                <div class="app-icon">📁</div>
                <div style="flex:1">
                    <div class="app-name">{app['name']}</div>
                    <div class="app-meta">Indexed {app['created_at']} · {app['chunk_count']:,} chunks</div>
                </div>
                <span class="badge badge-green">indexed</span>
            </div>
            """, unsafe_allow_html=True)

            if has_zip:
                with open(zip_path, "rb") as f:
                    st.download_button(
                        label=f"⬇ Download {app['name']}.zip",
                        data=f.read(),
                        file_name=f"{app['name']}.zip",
                        mime="application/zip",
                        key=f"dl_{app['name']}",
                    )

st.markdown("---")
st.caption("LogSense · Application Indexer · Powered by sentence-transformers + Qdrant")