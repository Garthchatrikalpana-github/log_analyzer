# 🚀 Log Analyzer - Setup & Execution Guide

This project contains two Streamlit-based applications:

1. `indexer_ui.py` → Used to upload and index applications
2. `analyzer_ui.py` → Used to analyze incidents using logs + code search + LLM

---

# 📁 1. Project Setup

## Step 1: Create required folder structure

Before running the project, create a `data` directory.
inside data, create qdrant_db and logs subdirectories

This folder will be used to store:
logs
uploaded applications
Qdrant vector database
SQLite database


## Step 2: Create a virtual environment
python -m venv .venv
## Step 3: Activate virtual environment
Windows (Git Bash / CMD)
.venv\Scripts\activate
Mac/Linux
source .venv/bin/activate
## Step 4: Install dependencies
pip install -r requirements.txt

🧭 2. Run Application Indexer UI

This UI is used to upload and index application code into a vector database.
Start the indexer UI:
streamlit run indexer_ui.py
What happens after running?
A browser window will open automatically
You will see a login screen
Login Credentials (Demo):
Username: demo
Password: demo
Features:

After login, you can:

📌 View existing applications
Shows already indexed applications
📌 Add new application
Enter:
Application name
ZIP file containing source code

Example:

minicommerce.zip (sample provided)
Indexing process:

Click "Create Index" to:

Extract ZIP file
Chunk source code
Generate embeddings
Store data in Qdrant vector DB

Once completed, the application will be available for analysis.

🧠 3. Run Incident Analyzer UI

After indexing is complete, stop the previous app and run:

streamlit run analyzer_ui.py
What this UI does:

This is the Incident Analysis Chat Interface.

You can:
Enter incident number (e.g., INC001)
Click Analyze
Get full RCA (Root Cause Analysis)
Backend workflow:

When you submit an incident:

Incident details are fetched
Logs are retrieved
Relevant code is searched using vector DB
Logs are cleaned and processed
LLM generates RCA report
Output includes:
🔍 Root Cause Analysis
🧩 Impact Assessment
🛠️ Immediate Fix
🏗️ Long-Term Recommendations
✅ Verification Steps
⚠️ 4. Handling “multiple instances accessing Qdrant” error

If you see an error like:

Storage folder is already accessed by another instance of Qdrant client

Run this command to kill all Python processes:

taskkill /f /im python.exe

Then restart the app:

streamlit run analyzer_ui.py
🔁 5. Recommended workflow
1. Create data folder
2. Setup venv
3. Install dependencies
4. Run indexer_ui.py → upload & index app
5. Run analyzer_ui.py → analyze incidents
