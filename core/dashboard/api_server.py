"""
IMPACT Dashboard API Server
============================
A zero-dependency HTTP server (stdlib only) that exposes a single endpoint:

    POST /api/llm-analysis
        Body: { "repo": "owner/repo", "lang": "Python", "diff": {...}, "metrics": {...}, "intents": [...] }
        Returns: { "report": "<LLM or rule-based narrative text>" }

Run from the project root:
    python -m core.dashboard.api_server
or:
    python core/dashboard/api_server.py

The dashboard fetches this on double-click of a "Conformance report generated" bubble.
If this server is not running the dashboard gracefully falls back to its built-in local summary.
"""

import json
import sys
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

# Allow imports from the project root
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.agents.llm_agent import LLMAgent

PORT = 7842
ALLOWED_ORIGIN = "*"  # restrict in production

_llm_agent = LLMAgent()


def _build_diff_report(payload: dict) -> dict:
    """Convert dashboard JSON payload to the dict shape LLMAgent.execute() expects."""
    d = payload.get("diff", {})
    return {
        "version_old": d.get("version_old", "v1"),
        "version_new": d.get("version_new", "v2"),
        "added_nodes_count": d.get("addedNodes", 0),
        "removed_nodes_count": d.get("removedNodes", 0),
        "added_edges_count": d.get("addedEdges", 0),
        "removed_edges_count": d.get("removedEdges", 0),
        "new_cycles_count": d.get("newCycles", 0),
        "broken_cycles_count": d.get("brokenCycles", 0),
        "raw_diff": {
            "added_nodes": d.get("addedNodeIds", []),
            "removed_nodes": d.get("removedNodeIds", []),
            "added_edges": d.get("addedEdgeIds", []),
            "removed_edges": d.get("removedEdgeIds", []),
            "new_cycles": d.get("newCycleIds", []),
            "broken_cycles": [],
        },
    }


def _build_metrics_report(payload: dict) -> dict:
    """Convert dashboard JSON payload to the dict shape LLMAgent.execute() expects."""
    m = payload.get("metrics", {})
    top_hubs = [{"id": h} for h in m.get("topHubs", [])]
    return {
        "top_hubs": top_hubs,
        "coupling_anomalies": m.get("couplingAnomalies", []),
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):  # suppress default access log noise
        pass

    def _cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", ALLOWED_ORIGIN)
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors_headers()
        self.end_headers()

    def do_POST(self):
        if self.path != "/api/llm-analysis":
            self.send_response(404)
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            return

        diff_report = _build_diff_report(payload)
        metrics_report = _build_metrics_report(payload)
        intents = payload.get("intents", ["avoid cyclic dependencies"])

        try:
            report = _llm_agent.execute(diff_report, metrics_report, intents)
        except Exception as e:
            report = f"[API Error] LLMAgent raised: {e}"

        response = json.dumps({"report": report}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self._cors_headers()
        self.end_headers()
        self.wfile.write(response)


def main():
    server = HTTPServer(("localhost", PORT), Handler)
    print(f"[IMPACT API] Listening on http://localhost:{PORT}/api/llm-analysis")
    print("[IMPACT API] Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[IMPACT API] Stopped.")


if __name__ == "__main__":
    main()
