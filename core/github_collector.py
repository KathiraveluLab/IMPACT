import os
import sys
import json
import urllib.request
import urllib.error
import zipfile
from datetime import datetime, timezone
from adapters.java.extractor import JavaExtractor
from core.agents.coordinator import CoordinatorAgent
from core.shacl_validator import SHACLValidator

GITHUB_SEARCH_URL = "https://api.github.com/search/repositories"

def make_request(url, headers=None):
    if headers is None:
        headers = {}
    headers.setdefault("User-Agent", "IMPACT-Swarm-Collector")
    
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            return response.read()
    except urllib.error.HTTPError as e:
        print(f"HTTP Error: {e.code} - {e.reason}")
        return None
    except Exception as e:
        print(f"Request failed: {e}")
        return None

def search_repos(query, limit=5):
    print(f"Searching GitHub for Java repositories matching: '{query}'...")
    url = f"{GITHUB_SEARCH_URL}?q={urllib.parse.quote(query)}+language:java+size:<10000&sort=stars&order=desc"
    response_body = make_request(url)
    if not response_body:
        print("Failed to fetch search results from GitHub.")
        return []
    
    try:
        data = json.loads(response_body.decode("utf-8"))
        items = data.get("items", [])[:limit]
        results = []
        for item in items:
            results.append({
                "full_name": item["full_name"],
                "stars": item["stargazers_count"],
                "url": item["html_url"],
                "description": item["description"]
            })
        return results
    except Exception as e:
        print(f"Error parsing search results: {e}")
        return []

def download_and_extract_tag(owner, repo, tag, output_dir):
    zip_url = f"https://github.com/{owner}/{repo}/archive/refs/tags/{tag}.zip"
    print(f"Downloading source zip for {owner}/{repo} version {tag} from: {zip_url}")
    
    zip_data = make_request(zip_url)
    if not zip_data:
        # Try alternate tag formatting: tag without repo name prefix (e.g. 1.13.0 instead of javapoet-1.13.0)
        alternative_tag = tag.split("-")[-1] if "-" in tag else tag
        alternative_url = f"https://github.com/{owner}/{repo}/archive/refs/tags/{alternative_tag}.zip"
        print(f"Retrying with alternative URL: {alternative_url}")
        zip_data = make_request(alternative_url)
        if not zip_data:
            print(f"Failed to download version {tag}.")
            return False

    os.makedirs(output_dir, exist_ok=True)
    zip_path = os.path.join(output_dir, f"{tag}.zip")
    
    with open(zip_path, "wb") as f:
        f.write(zip_data)
        
    print(f"Extracting zip archive: {zip_path}")
    try:
        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(output_dir)
        os.remove(zip_path) # Clean up zip file
        return True
    except Exception as e:
        print(f"Failed to extract zip file: {e}")
        return False

def run_github_evaluation(owner, repo, tag1, tag2, language="java"):
    benchmark_root = os.path.join("test_projects/github_benchmarks", language.lower())
    repo_dir = os.path.join(benchmark_root, f"{owner}_{repo}")
    
    dir_v1 = os.path.join(repo_dir, tag1)
    dir_v2 = os.path.join(repo_dir, tag2)
    
    # 1. Download and Extract v1 and v2
    if not os.path.exists(dir_v1):
        print(f"\n--- Preparing Version 1: {tag1} ---")
        success = download_and_extract_tag(owner, repo, tag1, repo_dir)
        if not success:
            return
            
    if not os.path.exists(dir_v2):
        print(f"\n--- Preparing Version 2: {tag2} ---")
        success = download_and_extract_tag(owner, repo, tag2, repo_dir)
        if not success:
            return

    # Find the source folder inside extracted archive (GitHub nests folders inside the zip)
    def find_src_dir(parent_dir, target_tag):
        # The folder name is usually repo-tag (e.g. javapoet-javapoet-1.12.0)
        # Search for any directory matching the tag
        for entry in os.listdir(parent_dir):
            entry_path = os.path.join(parent_dir, entry)
            if os.path.isdir(entry_path) and (target_tag in entry or target_tag.split("-")[-1] in entry):
                return entry_path
        return parent_dir

    src_v1 = find_src_dir(repo_dir, tag1)
    src_v2 = find_src_dir(repo_dir, tag2)
    
    graph_v1 = os.path.join(repo_dir, f"{tag1}_graph.json")
    graph_v2 = os.path.join(repo_dir, f"{tag2}_graph.json")
    
    # 2. Extract dependency graphs
    if language.lower() == "java":
        print(f"\n--- Extracting Dependency Graph for Version 1 ({tag1}) ---")
        extractor_v1 = JavaExtractor(repo, tag1)
        extractor_v1.extract(src_v1, graph_v1)
        
        print(f"\n--- Extracting Dependency Graph for Version 2 ({tag2}) ---")
        extractor_v2 = JavaExtractor(repo, tag2)
        extractor_v2.extract(src_v2, graph_v2)
    else:
        print(f"Extraction for language '{language}' is not yet supported. Please integrate the appropriate adapter.")
        return
    
    # 3. Validate structures via SHACL
    print(f"\n--- Running SHACL Shape Validation on Extracted Graphs ---")
    validator = SHACLValidator()
    
    report_v1 = validator.validate_graph(graph_v1)
    print(f"Version 1 ({tag1}) SHACL Conformance: {report_v1['conforms']}")
    if not report_v1['conforms']:
        print(f"Violations: {report_v1['results']}")
        
    report_v2 = validator.validate_graph(graph_v2)
    print(f"Version 2 ({tag2}) SHACL Conformance: {report_v2['conforms']}")
    if not report_v2['conforms']:
        print(f"Violations: {report_v2['results']}")

    # 4. Execute Multi-agent Swarm Evolution Analysis
    print(f"\n--- Running Swarm Evolution Analysis ---")
    coordinator = CoordinatorAgent()
    intents = [
        "avoid cyclic dependencies",
        "minimize changes and complexity increase"
    ]
    
    report = coordinator.run_analysis(graph_v1, graph_v2, intents)
    
    print(f"\n=== Evolution Analysis Report for {owner}/{repo} ({tag1} -> {tag2}) ===")
    print(report)
    
    # Save the report for verification
    report_path = os.path.join(repo_dir, f"{tag1}_to_{tag2}_analysis.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\nAnalysis report successfully saved to: {report_path}")

def main():
    if len(sys.argv) < 2:
        print("IMPACT GitHub Collector & Benchmarker")
        print("Usage:")
        print("  python3 core/github_collector.py search <query>")
        print("  python3 core/github_collector.py evaluate <owner> <repo> <tag1> <tag2>")
        print("  python3 core/github_collector.py benchmark")
        sys.exit(1)
        
    cmd = sys.argv[1]
    
    if cmd == "search":
        if len(sys.argv) < 3:
            print("Please specify a search query. E.g., python3 core/github_collector.py search javapoet")
            sys.exit(1)
        query = sys.argv[2]
        repos = search_repos(query)
        print(f"\nFound {len(repos)} matching Java repositories:")
        for r in repos:
            print(f"- {r['full_name']} ({r['stars']} stars): {r['url']}")
            print(f"  Description: {r['description']}\n")
            
    elif cmd == "evaluate":
        if len(sys.argv) < 6:
            print("Usage: python3 core/github_collector.py evaluate <owner> <repo> <tag1> <tag2> [language]")
            sys.exit(1)
        owner = sys.argv[2]
        repo = sys.argv[3]
        tag1 = sys.argv[4]
        tag2 = sys.argv[5]
        lang = sys.argv[6] if len(sys.argv) > 6 else "java"
        run_github_evaluation(owner, repo, tag1, tag2, language=lang)
        
    elif cmd == "benchmark":
        print("Running preset batch benchmarks...")
        projects = [
            ("square", "javapoet", "javapoet-1.12.0", "javapoet-1.13.0"),
            ("jhy", "jsoup", "jsoup-1.14.1", "jsoup-1.14.2"),
            ("google", "gson", "gson-parent-2.8.5", "gson-parent-2.8.6"),
            ("reactive-streams", "reactive-streams-jvm", "v1.0.2", "v1.0.3")
        ]
        for owner, repo, tag1, tag2 in projects:
            print(f"\n==================================================")
            print(f"Benchmarking project: {owner}/{repo} ({tag1} -> {tag2})")
            print(f"==================================================")
            try:
                run_github_evaluation(owner, repo, tag1, tag2)
            except Exception as e:
                print(f"Failed to benchmark {owner}/{repo}: {e}")
        
    else:
        print(f"Unknown command: {cmd}")

if __name__ == "__main__":
    main()
