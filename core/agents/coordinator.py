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
