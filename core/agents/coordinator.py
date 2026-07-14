from core.agents.graph_agent import GraphAgent
from core.agents.diff_agent import DiffAgent
from core.agents.metrics_agent import MetricsAgent
from core.agents.llm_agent import LLMAgent

class CoordinatorAgent:
    """Core coordinator that orchestrates the entire IMPACT evaluation loop."""
    
    def __init__(self, name: str = "CoordinatorAgent"):
        self.name = name
        self.graph_agent = GraphAgent()
        self.diff_agent = DiffAgent()
        self.metrics_agent = MetricsAgent()
        self.llm_agent = LLMAgent()

    def run_analysis(self, file_path_v1: str, file_path_v2: str, intents: list) -> str:
        """Orchestrates the step-by-step evolution analysis of two versions."""
        print("[Coordinator] Step 1: Loading graphs and checking statistics...")
        stats_v1 = self.graph_agent.execute(file_path_v1)
        stats_v2 = self.graph_agent.execute(file_path_v2)
        
        print("[Coordinator] Step 2: Running structural diff comparison...")
        diff = self.diff_agent.execute(file_path_v1, file_path_v2)
        
        print("[Coordinator] Step 3: Computing graph metrics and identifying hubs...")
        metrics = self.metrics_agent.execute(file_path_v2)
        
        print("[Coordinator] Step 4: Synthesizing results and checking intent conformance...")
        report = self.llm_agent.execute(diff, metrics, intents)
        
        print("[Coordinator] Analysis complete.")
        return report

    def run_ecosystem_analysis(self, repo_coordinate: str, intents: list) -> str:
        """Downloads, extracts, and runs the multi-agent evolution analysis on a GitHub repository coordinate."""
        from core.ecosystem_crawler import GitHubEcosystemCrawler
        import os
        import sqlite3

        print(f"[Coordinator] Orchestrating ecosystem analysis for {repo_coordinate}...")
        owner, repo = repo_coordinate.split("/")
        crawler = GitHubEcosystemCrawler()

        # Check if the repository is already in the database queue, if not insert it
        conn = sqlite3.connect("test_projects/github_benchmarks/crawler_queue.db")
        cursor = conn.cursor()
        cursor.execute("SELECT id, status, tag1, tag2 FROM queue WHERE owner = ? AND repo = ?", (owner, repo))
        row = cursor.fetchone()
        
        if not row:
            cursor.execute("INSERT INTO queue (owner, repo) VALUES (?, ?)", (owner, repo))
            conn.commit()
            cursor.execute("SELECT id, status, tag1, tag2 FROM queue WHERE owner = ? AND repo = ?", (owner, repo))
            row = cursor.fetchone()
        
        repo_id, status, tag1, tag2 = row
        conn.close()

        # If it hasn't been crawled successfully yet, process it
        if status != "crawled":
            print(f"[Coordinator] Repository {repo_coordinate} is in '{status}' status. Initiating crawl/extraction...")
            crawler.process_repo(repo_id, owner, repo)
            
            # Re-read status
            conn = sqlite3.connect("test_projects/github_benchmarks/crawler_queue.db")
            cursor = conn.cursor()
            cursor.execute("SELECT status, tag1, tag2, error_msg FROM queue WHERE id = ?", (repo_id,))
            status, tag1, tag2, error_msg = cursor.fetchone()
            conn.close()
            
            if status == "failed":
                raise Exception(f"Ecosystem crawl failed for {repo_coordinate}: {error_msg}")

        # Path to the generated analysis report
        repo_dir = f"test_projects/github_benchmarks/java/{owner}_{repo}"
        report_path = os.path.join(repo_dir, f"{tag1}_to_{tag2}_analysis.txt")
        
        if not os.path.exists(report_path):
            graph_v1 = os.path.join(repo_dir, f"{tag1}_graph.json")
            graph_v2 = os.path.join(repo_dir, f"{tag2}_graph.json")
            report = self.run_analysis(graph_v1, graph_v2, intents)
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(report)
            return report

        with open(report_path, "r", encoding="utf-8") as f:
            return f.read()

