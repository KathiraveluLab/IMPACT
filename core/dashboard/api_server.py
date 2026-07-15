"""
IMPACT Dashboard API Server
============================
A zero-dependency HTTP server (stdlib only) that exposes:
    1. POST /api/llm-analysis
        Body: { "repo": "owner/repo", "lang": "Python", "diff": {...}, "metrics": {...}, "intents": [...] }
        Returns: { "report": "<LLM or rule-based narrative text>" }
    2. POST /api/crawl
        Body: { "repo": "owner/repo" }
        Returns: { "success": true, "v1": graph1, "v2": graph2, "tag1": "v1.0.0", "tag2": "v1.1.0", "detected_language": "Python" }

Run from the project root:
    python -m core.dashboard.api_server
or:
    python core/dashboard/api_server.py
"""

import json
import sys
import os
import re
import zipfile
import shutil
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

# Allow imports from the project root
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.agents.llm_agent import LLMAgent
from adapters.java.extractor import JavaExtractor

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


def _download_and_extract_tag(owner, repo, tag, output_dir, github_token=None):
    zip_url = f"https://github.com/{owner}/{repo}/archive/refs/tags/{tag}.zip"
    headers = {"User-Agent": "IMPACT-Dashboard-Crawler"}
    if github_token:
        headers["Authorization"] = f"token {github_token}"
        
    req = urllib.request.Request(zip_url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            zip_data = response.read()
    except Exception as e:
        # Retry with alternative tag format (without prefix)
        alt_tag = tag.split("-")[-1] if "-" in tag else tag
        alt_url = f"https://github.com/{owner}/{repo}/archive/refs/tags/{alt_tag}.zip"
        req_alt = urllib.request.Request(alt_url, headers=headers)
        try:
            with urllib.request.urlopen(req_alt, timeout=30) as response:
                zip_data = response.read()
        except Exception as ex:
            raise Exception(f"Failed to download zip from {zip_url} or {alt_url}: {ex}")

    os.makedirs(output_dir, exist_ok=True)
    zip_path = os.path.join(output_dir, f"{tag}.zip")
    with open(zip_path, "wb") as f:
        f.write(zip_data)
        
    try:
        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(output_dir)
        os.remove(zip_path)
        return True
    except Exception as e:
        if os.path.exists(zip_path):
            os.remove(zip_path)
        raise Exception(f"Failed to extract zip file: {e}")


def _find_src_dir(parent_dir):
    for entry in os.listdir(parent_dir):
        entry_path = os.path.join(parent_dir, entry)
        if os.path.isdir(entry_path):
            return entry_path
    return parent_dir


def _extract_generic(project_name, version, language, src_dir, output_file):
    # Map languages to file extensions and keywords
    lang_map = {
        "python": (".py", r"\bimport\s+([\w\.]+)\b|\bfrom\s+([\w\.]+)\s+import\b"),
        "gleam": (".gleam", r"\bimport\s+([\w\/]+)\b"),
        "erlang": (".erl", r"-\b(?:include|include_lib)\b\(\"([^\"]+)\"\)"),
        "rust": (".rs", r"\buse\s+([\w\:]+)\b"),
        "javascript": (".js", r"\b(?:import|require)\b"),
        "typescript": (".ts", r"\b(?:import|require)\b"),
    }
    
    lang_lower = language.lower()
    ext, import_pattern = lang_map.get(lang_lower, (None, None))
    if not ext:
        # Fallback for other languages
        ext = f".{lang_lower}" if lang_lower else ".src"
        import_pattern = None

    source_files = []
    for root, _, files in os.walk(src_dir):
        for file in files:
            if file.endswith(ext):
                source_files.append(os.path.join(root, file))

    nodes = {}
    edges = []
    
    # 1. First pass: Register all nodes
    for filepath in source_files:
        rel_path = os.path.relpath(filepath, src_dir)
        node_id = rel_path.replace(os.sep, "/")
        node_name = os.path.basename(filepath)
        
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            
        lines = content.splitlines()
        loc = len([line for line in lines if line.strip() and not line.strip().startswith("#") and not line.strip().startswith("//")])
        
        complexity = 1
        complexity += len(re.findall(r"\b(if|for|while|case|cond|fn|def|match)\b|&&|\|\|", content))
        
        nodes[node_id] = {
            "id": node_id,
            "name": node_name,
            "type": "file",
            "filePath": rel_path,
            "content": content,
            "metrics": {
                "loc": loc,
                "complexity": complexity,
                "fanIn": 0,
                "fanOut": 0,
                "coupling": 0
            }
        }

    # 2. Second pass: Find actual dependencies
    for node_id, node in nodes.items():
        dependencies = set()
        content = node["content"]
        
        if import_pattern:
            for match in re.finditer(import_pattern, content):
                imported = next((g for g in match.groups() if g is not None), None)
                if imported:
                    imported_clean = imported.replace(".", "/").replace("/py", "").strip()
                    for potential_id in nodes:
                        potential_base = potential_id.rsplit(".", 1)[0]
                        if potential_base == imported_clean or potential_base.endswith("/" + imported_clean):
                            dependencies.add(potential_id)
        
        for other_id, other_node in nodes.items():
            if other_id == node_id:
                continue
            other_base = other_id.rsplit(".", 1)[0]
            other_simple_name = other_base.split("/")[-1]
            if re.search(r"\b" + re.escape(other_simple_name) + r"\b", content):
                dependencies.add(other_id)

        for target_id in dependencies:
            edges.append({
                "source": node_id,
                "target": target_id,
                "type": "imports"
            })
            node["metrics"]["fanOut"] += 1
            nodes[target_id]["metrics"]["fanIn"] += 1

    for node in nodes.values():
        node.pop("content", None)
        node["metrics"]["coupling"] = node["metrics"]["fanIn"] + node["metrics"]["fanOut"]

    total_loc = sum(n["metrics"]["loc"] for n in nodes.values())
    total_files = len(nodes)
    avg_coupling = sum(n["metrics"]["coupling"] for n in nodes.values()) / max(1, total_files)

    output_data = {
        "@context": {
            "@vocab": "https://w3id.org/impact/ontology#",
            "projectName": "projectName",
            "version": "versionString",
            "language": "language",
            "extractedAt": "extractedAt",
            "systemMetrics": "systemMetrics",
            "nodes": "hasEntity",
            "edges": "hasDependency",
            "id": "@id",
            "type": "@type",
            "source": "source",
            "target": "target"
        },
        "projectName": project_name,
        "version": version,
        "language": language,
        "extractedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "systemMetrics": {
            "totalLinesOfCode": total_loc,
            "totalClasses": total_files,
            "averageCoupling": avg_coupling
        },
        "nodes": list(nodes.values()),
        "edges": edges
    }

    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2)


def _crawl_repository(repo_str, custom_lang=None):
    raw_repo = repo_str
    suffix_lang = custom_lang
    if ":" in repo_str:
        parts = repo_str.split(":")
        raw_repo = parts[0].strip()
        suffix_lang = parts[1].strip()
        
    if "/" not in raw_repo:
        raise Exception(f"Invalid repository format '{repo_str}'. Must be 'owner/repo'.")
        
    owner, repo_name = raw_repo.split("/", 1)
    github_token = os.environ.get("GITHUB_TOKEN")
    
    # Detect language
    language = suffix_lang
    if not language:
        lang_url = f"https://api.github.com/repos/{owner}/{repo_name}/languages"
        headers = {"User-Agent": "IMPACT-Dashboard-Crawler"}
        if github_token:
            headers["Authorization"] = f"token {github_token}"
        req = urllib.request.Request(lang_url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=15) as res:
                lang_data = json.loads(res.read().decode("utf-8"))
                if lang_data:
                    sorted_langs = sorted(lang_data.items(), key=lambda x: x[1], reverse=True)
                    if sorted_langs:
                        language = sorted_langs[0][0]
        except Exception:
            language = "Java"
            
    if not language:
        language = "Java"
        
    # Standardize language name
    lang_lower = language.lower()
    if "java" in lang_lower:
        standard_lang = "Java"
    elif "python" in lang_lower:
        standard_lang = "Python"
    elif "gleam" in lang_lower:
        standard_lang = "Gleam"
    elif "erlang" in lang_lower:
        standard_lang = "Erlang"
    else:
        standard_lang = language.capitalize()
        
    # Fetch release tags
    tags_url = f"https://api.github.com/repos/{owner}/{repo_name}/tags?per_page=10"
    headers = {"User-Agent": "IMPACT-Dashboard-Crawler"}
    if github_token:
        headers["Authorization"] = f"token {github_token}"
    req = urllib.request.Request(tags_url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as res:
            tags_data = json.loads(res.read().decode("utf-8"))
    except Exception as e:
        raise Exception(f"Failed to fetch tags for {owner}/{repo_name}: {e}")
        
    if len(tags_data) < 2:
        # Fallback to commit list if tags don't exist
        commits_url = f"https://api.github.com/repos/{owner}/{repo_name}/commits?per_page=10"
        req_commits = urllib.request.Request(commits_url, headers=headers)
        try:
            with urllib.request.urlopen(req_commits, timeout=15) as res:
                commits_data = json.loads(res.read().decode("utf-8"))
                if len(commits_data) >= 2:
                    tag2 = commits_data[0]["sha"][:7]
                    tag1 = commits_data[1]["sha"][:7]
                else:
                    raise Exception(f"Insufficient release tags or commits found for {owner}/{repo_name}. Need at least 2.")
        except Exception as ex:
            raise Exception(f"Insufficient release tags found for {owner}/{repo_name} and failed commit fallback: {ex}")
    else:
        tag2 = tags_data[0]["name"]
        tag1 = tags_data[1]["name"]
        
    benchmark_root = os.path.join("test_projects/github_benchmarks", standard_lang.lower())
    repo_dir = os.path.join(benchmark_root, f"{owner}_{repo_name}")
    
    graph_v1_path = os.path.join(repo_dir, f"{tag1}_graph.json")
    graph_v2_path = os.path.join(repo_dir, f"{tag2}_graph.json")
    
    if os.path.exists(graph_v1_path) and os.path.exists(graph_v2_path):
        with open(graph_v1_path, "r", encoding="utf-8") as f:
            v1_graph = json.load(f)
        with open(graph_v2_path, "r", encoding="utf-8") as f:
            v2_graph = json.load(f)
        return v1_graph, v2_graph, tag1, tag2, standard_lang
        
    dir_v1 = os.path.join(repo_dir, f"{tag1}_src")
    dir_v2 = os.path.join(repo_dir, f"{tag2}_src")
    
    try:
        _download_and_extract_tag(owner, repo_name, tag1, dir_v1, github_token)
        src_v1 = _find_src_dir(dir_v1)
        
        _download_and_extract_tag(owner, repo_name, tag2, dir_v2, github_token)
        src_v2 = _find_src_dir(dir_v2)
        
        if standard_lang == "Java":
            extractor_v1 = JavaExtractor(repo_name, tag1)
            extractor_v1.extract(src_v1, graph_v1_path)
            
            extractor_v2 = JavaExtractor(repo_name, tag2)
            extractor_v2.extract(src_v2, graph_v2_path)
        else:
            _extract_generic(repo_name, tag1, standard_lang, src_v1, graph_v1_path)
            _extract_generic(repo_name, tag2, standard_lang, src_v2, graph_v2_path)
            
        # Clean up extracted source directories
        for path in (dir_v1, dir_v2):
            if os.path.exists(path) and os.path.isdir(path):
                shutil.rmtree(path)
                
    except Exception as e:
        for path in (dir_v1, dir_v2):
            if os.path.exists(path) and os.path.isdir(path):
                shutil.rmtree(path)
        raise Exception(f"Crawl and extraction failed: {e}")
        
    with open(graph_v1_path, "r", encoding="utf-8") as f:
        v1_graph = json.load(f)
    with open(graph_v2_path, "r", encoding="utf-8") as f:
        v2_graph = json.load(f)
        
    return v1_graph, v2_graph, tag1, tag2, standard_lang


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
        if self.path not in ("/api/llm-analysis", "/api/crawl"):
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

        if self.path == "/api/llm-analysis":
            diff_report = _build_diff_report(payload)
            metrics_report = _build_metrics_report(payload)
            intents = payload.get("intents", ["avoid cyclic dependencies"])

            try:
                report = _llm_agent.execute(diff_report, metrics_report, intents)
            except Exception as e:
                report = f"[API Error] LLMAgent raised: {e}"

            response = json.dumps({"report": report}).encode("utf-8")
        else:  # /api/crawl
            repo = payload.get("repo")
            try:
                v1, v2, tag1, tag2, lang = _crawl_repository(repo)
                response = json.dumps({
                    "success": True,
                    "v1": v1,
                    "v2": v2,
                    "tag1": tag1,
                    "tag2": tag2,
                    "detected_language": lang
                }).encode("utf-8")
            except Exception as e:
                response = json.dumps({
                    "success": False,
                    "error": str(e)
                }).encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self._cors_headers()
        self.end_headers()
        self.wfile.write(response)


def load_dotenv():
    """Load variables from .env file in the project root if it exists."""
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    dotenv_path = os.path.join(root_dir, ".env")
    if os.path.exists(dotenv_path):
        try:
            with open(dotenv_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        key, val = line.split("=", 1)
                        key = key.strip()
                        val = val.strip().strip("'").strip('"')
                        os.environ[key] = val
        except Exception:
            pass


def main():
    load_dotenv()
    server = HTTPServer(("localhost", PORT), Handler)
    print(f"[IMPACT API] Listening on http://localhost:{PORT}")
    print("[IMPACT API] Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[IMPACT API] Stopped.")


if __name__ == "__main__":
    main()
