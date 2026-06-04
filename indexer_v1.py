"""
Application Indexer - Semantic chunking (AST-based for Python, heuristic for others)
"""
import os
import ast
import uuid
import sqlite3
import zipfile
import shutil
from pathlib import Path

from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct

# ── constants ──────────────────────────────────────────────────────────────
VECTOR_SIZE = 384
QDRANT_PATH = "data/qdrant_db"
APP_DB_PATH  = "data/apps.db"
UPLOAD_DIR   = "data/uploads"

# ── singletons ─────────────────────────────────────────────────────────────
_model  = None
_qdrant = None


def get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def get_qdrant():
    global _qdrant
    if _qdrant is None:
        os.makedirs(QDRANT_PATH, exist_ok=True)
        _qdrant = QdrantClient(path=QDRANT_PATH)
    return _qdrant


# ── app registry (SQLite) ──────────────────────────────────────────────────

def _app_conn():
    os.makedirs("data", exist_ok=True)
    return sqlite3.connect(APP_DB_PATH)


def init_app_db():
    conn = _app_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            name         TEXT UNIQUE NOT NULL,
            zip_filename TEXT NOT NULL,
            chunk_count  INTEGER DEFAULT 0,
            created_at   TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def app_exists(name: str) -> bool:
    conn = _app_conn()
    row = conn.execute("SELECT 1 FROM applications WHERE name=?", (name,)).fetchone()
    conn.close()
    return row is not None


def register_app(name: str, zip_filename: str, chunk_count: int):
    from datetime import datetime
    conn = _app_conn()
    conn.execute(
        "INSERT INTO applications (name, zip_filename, chunk_count, created_at) VALUES (?,?,?,?)",
        (name, zip_filename, chunk_count, datetime.now().isoformat(timespec="seconds")),
    )
    conn.commit()
    conn.close()


def list_apps():
    conn = _app_conn()
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM applications ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_app_record(name: str):
    conn = _app_conn()
    conn.execute("DELETE FROM applications WHERE name=?", (name,))
    conn.commit()
    conn.close()


# ── semantic chunking ─────────────────────────────────────────────────────

def _chunk_python(source: str, file_path: str):
    """Extract top-level and nested functions/classes as individual chunks."""
    chunks = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return _chunk_generic(source, file_path)

    lines = source.splitlines(keepends=True)

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            # only top-level and direct class methods (avoid deep nesting duplicates)
            start = node.lineno - 1
            end   = node.end_lineno
            code  = "".join(lines[start:end])
            label = type(node).__name__.replace("Def", "").replace("Async", "async ").lower()
            chunks.append({
                "content": code,
                "metadata": f"{file_path} | {label}: {node.name} (lines {node.lineno}-{node.end_lineno})",
            })

    if not chunks:
        # file has no functions/classes → treat whole file as one chunk
        chunks.append({"content": source, "metadata": file_path})

    return chunks


def _chunk_generic(source: str, file_path: str, max_lines: int = 60):
    """Sliding-window chunker that respects blank-line boundaries."""
    lines  = source.splitlines(keepends=True)
    chunks = []
    start  = 0
    while start < len(lines):
        end = min(start + max_lines, len(lines))
        # extend to next blank line so we don't cut mid-block
        while end < len(lines) and lines[end].strip():
            end += 1
        chunk_text = "".join(lines[start:end])
        if chunk_text.strip():
            chunks.append({
                "content":  chunk_text,
                "metadata": f"{file_path} (lines {start+1}-{end})",
            })
        start = end if end > start else start + max_lines
    return chunks


def chunk_file(file_path: str, content: str):
    ext = Path(file_path).suffix.lower()
    if ext == ".py":
        return _chunk_python(content, file_path)
    elif ext in (".js", ".ts", ".jsx", ".tsx", ".java", ".cs", ".go", ".rs"):
        return _chunk_generic(content, file_path, max_lines=50)
    elif ext in (".json", ".yaml", ".yml", ".toml", ".env", ".cfg", ".ini"):
        return [{"content": content[:4000], "metadata": file_path}]
    elif ext in (".md", ".txt", ".rst"):
        return _chunk_generic(content, file_path, max_lines=40)
    else:
        return []   # skip binaries / unrecognised


# ── main indexing function ────────────────────────────────────────────────

SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", "dist", "build", ".idea", ".vscode"}
SKIP_EXTS = {".pyc", ".pyo", ".exe", ".dll", ".so", ".bin", ".jpg", ".jpeg", ".png", ".gif",
             ".svg", ".ico", ".pdf", ".zip", ".tar", ".gz", ".whl", ".egg"}


def index_application(app_name: str, zip_bytes: bytes, zip_filename: str) -> dict:
    """
    Full pipeline:
      1. Save ZIP
      2. Extract to temp dir
      3. Semantic-chunk all source files
      4. Embed & upsert into Qdrant (collection = app_name)
      5. Register in SQLite
    Returns {"ok": True, "chunk_count": N} or {"ok": False, "error": msg}
    """
    init_app_db()

    if app_exists(app_name):
        return {"ok": False, "error": f"Application '{app_name}' already exists."}

    # 1. Save ZIP
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    safe_name    = "".join(c if c.isalnum() or c in "-_." else "_" for c in zip_filename)
    saved_zip    = os.path.join(UPLOAD_DIR, f"{app_name}__{safe_name}")
    with open(saved_zip, "wb") as f:
        f.write(zip_bytes)

    # 2. Extract
    extract_dir = os.path.join(UPLOAD_DIR, f"_extract_{app_name}")
    if os.path.exists(extract_dir):
        shutil.rmtree(extract_dir)
    try:
        with zipfile.ZipFile(saved_zip, "r") as z:
            z.extractall(extract_dir)
    except zipfile.BadZipFile as e:
        return {"ok": False, "error": f"Invalid ZIP file: {e}"}

    # 3. Chunk
    all_chunks = []
    for root, dirs, files in os.walk(extract_dir):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fname in files:
            fpath = os.path.join(root, fname)
            rel   = os.path.relpath(fpath, extract_dir)
            if Path(fname).suffix.lower() in SKIP_EXTS:
                continue
            try:
                content = Path(fpath).read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            all_chunks.extend(chunk_file(rel, content))

    if not all_chunks:
        shutil.rmtree(extract_dir, ignore_errors=True)
        return {"ok": False, "error": "No indexable source files found in ZIP."}

    # 4. Embed & upsert
    qdrant = get_qdrant()
    model  = get_model()

    if qdrant.collection_exists(app_name):
        qdrant.delete_collection(app_name)

    qdrant.create_collection(
        collection_name=app_name,
        vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
    )

    batch_size = 64
    points     = []
    texts      = [c["content"] for c in all_chunks]

    for i in range(0, len(texts), batch_size):
        batch     = texts[i: i + batch_size]
        embeddings = model.encode(batch, show_progress_bar=False)
        for j, emb in enumerate(embeddings):
            chunk = all_chunks[i + j]
            points.append(PointStruct(
                id=str(uuid.uuid4()),
                vector=emb.tolist(),
                payload={"content": chunk["content"], "metadata": chunk["metadata"]},
            ))

    qdrant.upsert(collection_name=app_name, points=points)
    shutil.rmtree(extract_dir, ignore_errors=True)

    # 5. Register
    register_app(app_name, safe_name, len(points))

    return {"ok": True, "chunk_count": len(points)}


def search_code(app_name: str, query: str, limit: int = 6):
    qdrant = get_qdrant()
    model  = get_model()
    # app_name = "minicommerce"

    if not qdrant.collection_exists(app_name):
        return []

    embedding = model.encode(query).tolist()
    results   = qdrant.query_points(collection_name=app_name, query=embedding, limit=limit)

    return [
        {
            "content":  p.payload.get("content", ""),
            "metadata": p.payload.get("metadata", ""),
            "score":    round(p.score, 4),
        }
        for p in results.points
    ]


# bootstrap
init_app_db()