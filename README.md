# IMPACT: Intent-based Multi-agent Platform for Architectural Change Tracking

IMPACT is a language-agnostic multi-agent framework designed to monitor and manage the structural evolution of software systems. Drawing inspiration from Intent-Based Networking (IBN) in autonomic computing, IMPACT enables human software architects to specify high-level structural intents, such as preventing cyclic dependencies or limiting complexity growth. A swarm of cooperative agents then evaluates codebase transitions, detects violations, and provides explainable, natural-language refactoring advice.

This project is built to align with the paradigm of Human-AI Collaboration, establishing a structured feedback loop where human expertise guides agentic analysis and governance.

## Repository Structure

The repository is organized as follows:

*   **`core/`**: The core Python package of the IMPACT framework:
    *   `schema/`: Standardized JSON schema for software dependency graphs.
    *   `agents/`: Specialized agent implementations including the Coordinator, Graph, Diff, Metrics, and LLM agents.
    *   `graph_utils.py`: Utility functions for loading graphs and computing structural diffs.
*   **`test_projects/`**: Mock datasets simulating software evolution:
    *   `v1_graph.json`: Clean, acyclic baseline version (TelemetryService 1.0.0).
    *   `v2_graph.json`: Evolved version containing an injected cyclic dependency violation (TelemetryService 2.0.0).
*   **`_paper/`**: Academic draft and design notes:
    *   `design/`: Preliminary system design and architecture plans.
    *   `src/`: LaTeX manuscript source files, bibliography, and compiled PDF.
*   **`run_demo.py`**: Execution script to run the multi-agent evolution tracker.
*   **`test_impact.py`**: Automated unit test suite to verify graph loading, diff calculations, and coordinator orchestration.

## Installation & Setup

IMPACT is implemented in Python and relies on `networkx` for graph calculations. 

### Prerequisites

Ensure you have Python 3.8 or higher installed on your system.

### Install Dependencies

Install the required packages using pip:

```bash
pip install networkx
```

## Running the Project

### Running the Demo

To run the full multi-agent evolution analysis on the sample `TelemetryService` transition, execute:

```bash
python3 run_demo.py
```

This will run the Coordinator agent, orchestrate the swarm, evaluate intents against the graph diffs, and generate the compliance report.

### Running Unit Tests

To run the automated test suite, execute:

```bash
python3 -m unittest test_impact.py
```

## How It Works

1.  **Codebase Extraction**: Pluggable language adapters parse a codebase and export its structural dependency network and metrics conforming to the standardized JSON schema.
2.  **Orchestration**: The Coordinator agent manages the evaluation loop.
3.  **Graph Analysis**: The Graph agent loads the JSON-LD files, and the Metrics agent calculates network centralities to identify coupling hubs.
4.  **Version Comparison**: The Diff agent compares adjacent versions to discover added, removed, or modified nodes and edges, as well as newly introduced cycles.
5.  **Intent Conformance**: The LLM agent evaluates the diff metrics against the user-specified architectural intents, outputting a compliance report and refactoring recommendations.
