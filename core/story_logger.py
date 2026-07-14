#!/usr/bin/env python3
"""
IMPACT Multi-Agent Storyteller Log Generator.
Formats raw agent execution traces into a narrative logs format with story commentary.
"""

import sys
import os
import json
from datetime import datetime, timezone

class AgentStoryLogger:
    def __init__(self, output_file: str):
        self.output_file = output_file
        self.traces = []

    def log_agent_activity(self, agent: str, phase: str, message: str, narrative: str):
        self.traces.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": agent,
            "phase": phase,
            "message": message,
            "narrative": narrative
        })

    def write_story_log(self):
        with open(self.output_file, "w", encoding="utf-8") as f:
            f.write("# IMPACT Swarm Agent Storyteller Execution Logs\n\n")
            f.write("This log outlines the narrative progression of the multi-agent system during codebase analysis.\n\n")
            f.write("---\n\n")
            
            for i, trace in enumerate(self.traces):
                f.write(f"### [Step {i+1}] {trace['phase']} - {trace['agent']}\n")
                f.write(f"* **Timestamp**: `{trace['timestamp']}`\n")
                f.write(f"* **System Output**: *\"{trace['message']}\"*\n")
                f.write(f"* **Storyteller Narrative**: {trace['narrative']}\n\n")
                f.write("  ---\n\n")

if __name__ == "__main__":
    out_path = sys.argv[1] if len(sys.argv) > 1 else "agent_story_log.md"
    logger = AgentStoryLogger(out_path)
    
    # Simulate agent trace steps
    logger.log_agent_activity(
        "GraphAgent", 
        "Initialization", 
        "Loaded Version 2.0.0 of TelemetryService (4 classes, 41 LOC).",
        "Our story begins as GraphAgent, the cartographer of the digital domain, opens the archives of TelemetryService v2.0.0. The agent maps out four distinct modules standing in silent isolation, awaiting discovery."
    )
    
    logger.log_agent_activity(
        "DiffAgent", 
        "Evolution Scan", 
        "Identified structural changes: added 1 classes, added 1 edges. Detected 1 new cycle loops.",
        "DiffAgent, the chronicler of change, compares the old map with the new. Instantly, it spots a new class, `NewUtility`, and a new pathway linking the `Database` back to the `Service`. This circular loop introduces a critical feedback loop where none existed before."
    )
    
    logger.log_agent_activity(
        "MetricsAgent", 
        "Network Analysis", 
        "Calculated network metrics. Most central coupling hubs: com.telemetry.Database, com.telemetry.Service.",
        "MetricsAgent, the number-smith, computes the central gravity of our network. It reveals that the `Database` and `Service` modules are heavily entangled, pulling other modules into their orbit like celestial gravity hubs."
    )
    
    logger.log_agent_activity(
        "LLMAgent", 
        "Compliance Verdict", 
        "VIOLATION: New cyclic dependencies detected. Breaches 'Avoid cyclic dependencies'.",
        "At last, the LLMAgent, acting as the high justice of code quality, reviews the gathered evidence. Because the developers declared an intent to prevent cycles, this new circular pathway stands in clear violation of our modular laws. A warning is declared, demanding developer remediation!"
    )
    
    logger.write_story_log()
    print(f"Generated agent storytelling log at: {out_path}")
