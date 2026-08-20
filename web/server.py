"""Launcher for the Multi-Agent Research Studio Web UI."""

import sys
import uvicorn
from multi_agent_research_lab.web.app import app

if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

if __name__ == "__main__":
    print("Multi-Agent Research Studio running at: http://127.0.0.1:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000)
