"""
Log retrieval + analysis pipeline
"""
import os
import re

from incident_db import get_incident
from indexer import search_code

LOGS_DIR = "data/logs"

# ── log retrieval (simulated Azure App Insights) ──────────────────────────

def fetch_logs(incident_number: str, user_id: str) -> str | None:
    """
    Priority:
      1. <INC_NUM>_user<USER_ID>.log   (most specific)
      2. <INC_NUM>_*.log               (any log for this incident)
      3. *_user<USER_ID>.log           (any log for this user)
    """
    candidates = [
        os.path.join(LOGS_DIR, f"{incident_number}_user{user_id}.log"),
    ]

    for path in candidates:
        if os.path.isfile(path):
            return open(path, encoding="utf-8").read()

    # fallback: first file matching incident prefix
    if os.path.isdir(LOGS_DIR):
        for fname in sorted(os.listdir(LOGS_DIR)):
            if fname.startswith(incident_number + "_"):
                return open(os.path.join(LOGS_DIR, fname), encoding="utf-8").read()

        for fname in sorted(os.listdir(LOGS_DIR)):
            if f"_user{user_id}." in fname:
                return open(os.path.join(LOGS_DIR, fname), encoding="utf-8").read()

    return None


# ── log preprocessing ─────────────────────────────────────────────────────

NOISE_PATTERNS = [
    re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} DEBUG.*$", re.MULTILINE),
    re.compile(r"^\s*at sun\.reflect\..*$", re.MULTILINE),
    re.compile(r"^\s*\.\.\. \d+ more.*$", re.MULTILINE),
]

MAX_LOG_CHARS = 3000


def preprocess_logs(raw: str) -> str:
    text = raw
    for pat in NOISE_PATTERNS:
        text = pat.sub("", text)
    # collapse blank lines
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) > MAX_LOG_CHARS:
        # text = text[:MAX_LOG_CHARS] + "\n... [truncated]"
        text = "... [truncated]\n" + text[-MAX_LOG_CHARS:]
    return text


# ── error extraction ──────────────────────────────────────────────────────

# def extract_primary_error(log_text: str) -> str:
#     lines = log_text.splitlines()
#     for line in lines:
#         if "ERROR" in line or "Exception" in line or "FATAL" in line:
#             return line.strip()
#     return log_text[:300]
# def extract_primary_error(log_text: str) -> str:
#     lines = log_text.splitlines()
#     for line in lines:
#         if "ERROR" in line or "Exception" in line or "FATAL" in line:
#             return line.strip()
#     return log_text[-500:] if len(log_text) > 500 else log_text


# ── optional health checks (simulated) ───────────────────────────────────

def run_health_checks(error_line: str) -> list[dict]:
    """Simulate infra checks based on keywords in the error."""
    checks = []
    return [{
            "check": "Inventory Sync Service",
            "status": "✅  Service running",
            "detail": "Simulated: last sync 4 min ago, next in 1 min"
        }]

    # if "Connection" in error_line or "pool" in error_line.lower() or "Database" in error_line:
    #     checks.append({
    #         "check": "Database Connectivity",
    #         "status": "⚠️  Pool near saturation (92%)",
    #         "detail": "Simulated: max_pool_size=10, active_connections=9"
    #     })

    # if "Null" in error_line or "null" in error_line:
    #     checks.append({
    #         "check": "Data Integrity",
    #         "status": "⚠️  Possible missing migration",
    #         "detail": "Simulated: schema version mismatch detected on users table"
    #     })

    # if "Stock" in error_line or "Inventory" in error_line:
    #     checks.append({
    #         "check": "Inventory Sync Service",
    #         "status": "✅  Service running",
    #         "detail": "Simulated: last sync 4 min ago, next in 1 min"
    #     })

    # return checks


# ── full analysis pipeline ────────────────────────────────────────────────

def run_analysis(instruction: str) -> dict:
    """
    Returns a dict with keys:
      incident, logs_raw, logs_clean, error_line, code_chunks,
      health_checks, analysis_prompt
    Or raises ValueError with a user-friendly message.
    """
    match = re.search(r"\bINC\d{3,4}\b", instruction, re.IGNORECASE)

    if match:
        incident_number = match.group()
    incident = get_incident(incident_number)
    if not incident:
        raise ValueError(f"Incident **{incident_number}** not found in the database.")

    raw_logs = fetch_logs(incident_number, incident["user_id"])
    if not raw_logs:
        raise ValueError(
            f"No log files found for incident {incident_number} / user {incident['user_id']}."
        )

    logs_clean  = preprocess_logs(raw_logs)
    error_line  = raw_logs[-500:] if len(raw_logs) > 500 else raw_logs #extract_primary_error(logs_clean)
    code_chunks = search_code(incident["application_name"], error_line, limit=5)
    health      = run_health_checks(logs_clean)

    prompt = _build_prompt(incident, logs_clean, code_chunks, health)

    return {
        "incident":     incident,
        "logs_raw":     raw_logs,
        "logs_clean":   logs_clean,
        "code_chunks":  code_chunks,
        "health_checks": health,
        "analysis_prompt": prompt,
    }


def _build_prompt(incident, logs, code_chunks, health) -> str:
    code_section = ""
    for i, chunk in enumerate(code_chunks, 1):
        code_section += f"\n--- Chunk {i} ({chunk['metadata']}, score={chunk['score']}) ---\n{chunk['content']}\n"

    health_section = ""
    if health:
        health_section = "\n\nINFRASTRUCTURE HEALTH CHECKS:\n"
        for h in health:
            health_section += f"• {h['check']}: {h['status']} — {h['detail']}\n"

    return f"""You are an expert site-reliability engineer and debugging assistant.

INCIDENT DETAILS:
- Number:      {incident['incident_number']}
- Application: {incident['application_name']}
- User ID:     {incident['user_id']}
- Status:      {incident['status']}
- Reported:    {incident['created_time']}
- Description: {incident['error_description']}

PROCESSED LOGS:
{logs}
{health_section}

RELEVANT SOURCE CODE:
{code_section if code_section else "No indexed code available for this application."}

---
Please provide a thorough incident analysis with the following sections:

## 🔍 Root Cause Analysis
Identify the exact root cause. Reference the specific log lines and code chunks.

## 🧩 Impact Assessment  
Who / what is affected, and what is the blast radius?

## 🛠️ Immediate Fix
Step-by-step remediation actions the on-call engineer should take RIGHT NOW.

## 🏗️ Long-Term Recommendations
Code or architecture changes to prevent recurrence.

## ✅ Verification Steps
How to confirm the fix is working.

Be precise, actionable, and concise. Use markdown formatting."""