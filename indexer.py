"""
Application Indexer - Stable version (SAFE + SIMPLE chunking)
"""

import os
import uuid
import sqlite3
import zipfile
import shutil
from pathlib import Path

from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct

# ─────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────
VECTOR_SIZE = 384
QDRANT_PATH = "data/qdrant_db"
APP_DB_PATH = "data/apps.db"
UPLOAD_DIR = "data/uploads"

SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", "dist", "build"}
SKIP_EXTS = {
    ".pyc", ".pyo", ".exe", ".dll", ".so", ".bin",
    ".jpg", ".jpeg", ".png", ".gif", ".svg",
    ".zip", ".tar", ".gz", ".pdf"
}

# ─────────────────────────────────────────────
# SINGLETONS
# ─────────────────────────────────────────────
_model = None
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


# ─────────────────────────────────────────────
# SQLITE DB
# ─────────────────────────────────────────────
def _app_conn():
    os.makedirs("data", exist_ok=True)
    return sqlite3.connect(APP_DB_PATH)


def init_app_db():
    conn = _app_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            zip_filename TEXT NOT NULL,
            chunk_count INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def app_exists(name: str) -> bool:
    conn = _app_conn()
    row = conn.execute(
        "SELECT 1 FROM applications WHERE name=?",
        (name,)
    ).fetchone()
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
    rows = conn.execute(
        "SELECT * FROM applications ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_app_record(name: str):
    conn = _app_conn()
    conn.execute("DELETE FROM applications WHERE name=?", (name,))
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────
# SIMPLE CHUNKING (FIXED APPROACH)
# ─────────────────────────────────────────────
def chunk_file(file_path: str, content: str, max_chars: int = 20000):
    """
    One file = one chunk (or split if very large).
    This improves retrieval quality significantly.
    """

    if not content or not content.strip():
        return []

    content = content.strip()

    # small file → single chunk
    if len(content) <= max_chars:
        return [{
            "content": content,
            "metadata": file_path
        }]

    # large file → split into big chunks
    chunks = []
    start = 0
    part = 1

    while start < len(content):
        end = start + max_chars
        chunks.append({
            "content": content[start:end],
            "metadata": f"{file_path} | part-{part}"
        })
        start = end
        part += 1

    return chunks


# ─────────────────────────────────────────────
# INDEXING
# ─────────────────────────────────────────────
def index_application(app_name: str, zip_bytes: bytes, zip_filename: str) -> dict:
    init_app_db()

    if app_exists(app_name):
        return {"ok": False, "error": f"Application '{app_name}' already exists."}

    os.makedirs(UPLOAD_DIR, exist_ok=True)

    safe_name = "".join(c if c.isalnum() or c in "-_." else "_" for c in zip_filename)
    saved_zip = os.path.join(UPLOAD_DIR, f"{app_name}__{safe_name}")

    with open(saved_zip, "wb") as f:
        f.write(zip_bytes)

    extract_dir = os.path.join(UPLOAD_DIR, f"_extract_{app_name}")

    if os.path.exists(extract_dir):
        shutil.rmtree(extract_dir)

    try:
        with zipfile.ZipFile(saved_zip, "r") as z:
            z.extractall(extract_dir)
    except zipfile.BadZipFile as e:
        return {"ok": False, "error": f"Invalid ZIP file: {e}"}

    # ─────────────────────────────
    # CREATE CHUNKS
    # ─────────────────────────────
    all_chunks = []

    for root, dirs, files in os.walk(extract_dir):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]

        for fname in files:
            fpath = os.path.join(root, fname)
            rel = os.path.relpath(fpath, extract_dir)

            if Path(fname).suffix.lower() in SKIP_EXTS:
                continue

            try:
                content = Path(fpath).read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            all_chunks.extend(chunk_file(rel, content))

    if not all_chunks:
        shutil.rmtree(extract_dir, ignore_errors=True)
        return {"ok": False, "error": "No indexable files found in ZIP"}

    # ─────────────────────────────
    # EMBEDDING + QDRANT
    # ─────────────────────────────
    qdrant = get_qdrant()
    model = get_model()

    if qdrant.collection_exists(app_name):
        qdrant.delete_collection(app_name)

    qdrant.create_collection(
        collection_name=app_name,
        vectors_config=VectorParams(
            size=VECTOR_SIZE,
            distance=Distance.COSINE
        ),
    )

    texts = [c["content"] for c in all_chunks]
    points = []

    batch_size = 64

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        embeddings = model.encode(batch, show_progress_bar=False)

        for j, emb in enumerate(embeddings):
            chunk = all_chunks[i + j]

            points.append(PointStruct(
                id=str(uuid.uuid4()),
                vector=emb.tolist(),
                payload={
                    "content": chunk["content"],
                    "metadata": chunk["metadata"]
                }
            ))

    qdrant.upsert(collection_name=app_name, points=points)

    shutil.rmtree(extract_dir, ignore_errors=True)

    register_app(app_name, safe_name, len(points))

    return {"ok": True, "chunk_count": len(points)}


# ─────────────────────────────────────────────
# SEARCH
# ─────────────────────────────────────────────
def search_code(app_name: str, query: str, limit: int = 6):
    qdrant = get_qdrant()
    model = get_model()

    if not qdrant.collection_exists(app_name):
        return []

    embedding = model.encode(query).tolist()

    results = qdrant.query_points(
        collection_name=app_name,
        query=embedding,
        limit=limit
    )

    return [
        {
            "content": p.payload.get("content", ""),
            "metadata": p.payload.get("metadata", ""),
            "score": round(p.score, 4),
        }
        for p in results.points
    ]


# ─────────────────────────────────────────────
# BOOTSTRAP
# ─────────────────────────────────────────────
init_app_db()