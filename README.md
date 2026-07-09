# IMPACT: Intent-based Multi-agent Platform for Architectural Change Tracking

IMPACT is a language-agnostic multi-agent framework designed to monitor and manage the structural evolution of software systems. Drawing inspiration from Intent-Based Networking (IBN) in autonomic computing, IMPACT enables human software architects to specify high-level structural intents, such as preventing cyclic dependencies or limiting complexity growth. A swarm of cooperative agents then evaluates codebase transitions, detects violations, and provides explainable, natural-language refactoring advice.

This project is built to align with the paradigm of Human-AI Collaboration, establishing a structured feedback loop where human expertise guides agentic analysis and governance.

## Repository Structure

The repository is organized as follows:

*   **`core/`**: The core Python package of the IMPACT framework:
    *   `schema/`: Standardized JSON schema for software dependency graphs.
    *   `agents/`: Specialized agent implementations including the Coordinator, Graph, Diff, Metrics, and LLM agents.
    *   `graph_utils.py`: Utility functions for loading graphs and computing structural diffs.
*   **`adapters/`**: Pluggable source code extraction layers:
    *   `java/`: Python-based parser that walks Java project directories, extracts FQCNs, resolves dependency call-graphs, and exports JSON graphs.
*   **`test_projects/`**: Datasets and source folders simulating software evolution:
    *   `telemetry_service_v1/`: Version 1.0.0 Java source code of TelemetryService.
    *   `telemetry_service_v2/`: Version 2.0.0 Java source code of TelemetryService.
    *   `v1_graph.json`: Extracted dependency graph for Version 1.0.0.
    *   `v2_graph.json`: Extracted dependency graph for Version 2.0.0.
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

### Running Graph Extraction (Java Adapter)

To extract a dependency graph from a Java source code directory, execute the Java extractor tool:

```bash
python3 adapters/java/extractor.py <projectName> <version> <srcDirectory> <outputJsonPath>
```

For example, to extract graphs for the mock `TelemetryService` project versions:

```bash
python3 adapters/java/extractor.py TelemetryService 1.0.0 test_projects/telemetry_service_v1/src test_projects/v1_graph.json
python3 adapters/java/extractor.py TelemetryService 2.0.0 test_projects/telemetry_service_v2/src test_projects/v2_graph.json
```

### Running the Demo

To run the full multi-agent evolution analysis on the sample `TelemetryService` transition, execute:

```bash
python3 run_demo.py
```

This will run the Coordinator agent, orchestrate the swarm, evaluate intents against the graph diffs, and generate the compliance report.

### Running the Architect Dashboard (UI)

To launch the interactive visual dashboard in your browser, execute:

```bash
python3 run_dashboard.py
```

This starts a local development server and automatically opens the dashboard interface at `http://localhost:8080/dashboard/index.html`. In the dashboard, you can visually explore the dependency graphs (with cycles highlighted in red), add new intents, trigger evolution analyses, and view tabular diff metrics.

![IMPACT Architect Dashboard UI](docs/dashboard_screenshot.png)


### Running Unit Tests

To run the automated test suite, execute:

```bash
python3 -m unittest test_impact.py
```

### Running the Model Context Protocol (MCP) Server

To run the stdio-compliant Model Context Protocol server:

```bash
python3 -m core.mcp_server
```

This starts the server on stdio. Any MCP-compatible client (such as Claude Desktop) can connect to it and invoke the `run_evolution_analysis` and `extract_java_graph` tools.

### Running PMD Static Analysis Merger

To integrate PMD static analysis reports into the extracted dependency graph, run:

```bash
python3 adapters/java/static_analyzer.py <graphJsonPath> <pmdJsonPath>
```

For example, to merge our mock PMD report into the Version 2 graph:

```bash
python3 adapters/java/static_analyzer.py test_projects/v2_graph.json test_projects/pmd_report_v2.json
```

### Running the SHACL Structural Validator

To validate your JSON-LD software graphs against our SHACL structural shapes, execute:

```bash
python3 core/shacl_validator.py <graphJsonPath>
```



## How It Works

1.  **Codebase Extraction**: Pluggable language adapters parse a codebase and export its structural dependency network and metrics conforming to the standardized JSON schema.
2.  **Orchestration**: The Coordinator agent manages the evaluation loop.
3.  **Graph Analysis**: The Graph agent loads the JSON-LD files, and the Metrics agent calculates network centralities to identify coupling hubs.
4.  **Version Comparison**: The Diff agent compares adjacent versions to discover added, removed, or modified nodes and edges, as well as newly introduced cycles.
5.  **Intent Conformance**: The LLM agent evaluates the diff metrics against the user-specified architectural intents, outputting a compliance report and refactoring recommendations.
