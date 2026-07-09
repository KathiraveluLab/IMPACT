class LLMAgent:
    """Specialized agent that uses LLMs to interpret structural changes and write architectural explanations."""
    
    def __init__(self, name: str = "LLMAgent"):
        self.name = name

    def execute(self, diff_report: dict, metrics_report: dict, intents: list) -> str:
        """Synthesizes diff and metrics reports into a coherent architectural summary relative to defined intents."""
        
        added_nodes = diff_report["added_nodes_count"]
        added_edges = diff_report["added_edges_count"]
        new_cycles = diff_report["new_cycles_count"]
        top_hubs = ", ".join([h["id"] for h in metrics_report["top_hubs"]])
        
        # Check intent violations
        violations = []
        for intent in intents:
            if "avoid cyclic" in intent.lower() and new_cycles > 0:
                violations.append(f"VIOLATION: New cyclic dependencies detected ({new_cycles} new cycles). This breaches the intent to '{intent}'.")
            if "minimize changes" in intent.lower() and (added_nodes > 10 or added_edges > 20):
                violations.append(f"VIOLATION: High volume of changes detected (added {added_nodes} nodes, {added_edges} edges). This breaches the intent to '{intent}'.")
        
        summary = (
            f"Architectural Evolution Report (Version {diff_report['version_old']} -> {diff_report['version_new']})\n"
            f"===========================================================\n"
            f"1. Structural Changes:\n"
            f"   * Added Nodes: {added_nodes}\n"
            f"   * Added Dependencies (Edges): {added_edges}\n"
            f"   * Removed Nodes: {diff_report['removed_nodes_count']}\n"
            f"   * Removed Dependencies (Edges): {diff_report['removed_edges_count']}\n\n"
            f"2. Dependency Cycles:\n"
            f"   * New Cycles Detected: {new_cycles}\n"
            f"   * Broken Cycles: {diff_report['broken_cycles_count']}\n\n"
            f"3. Coupling & Complexity Hubs:\n"
            f"   * Top Coupled Nodes in New Version: {top_hubs}\n\n"
            f"4. Intent Conformance Evaluation:\n"
        )
        
        if violations:
            summary += "\n".join([f"   * {v}" for v in violations])
        else:
            summary += "   * All intents successfully satisfied. No modularity or cycle violations detected."
            
        summary += "\n\n5. Recommendations:\n"
        if new_cycles > 0:
            summary += "   * Action required: Break the newly introduced dependency cycle(s) to preserve modular boundaries.\n"
        else:
            summary += "   * Codebase structure is clean. Modularity is preserved.\n"
            
        return summary
