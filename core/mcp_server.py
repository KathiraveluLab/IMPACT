import sys
import json
import os
from core.agents.coordinator import CoordinatorAgent
from adapters.java.extractor import JavaExtractor

def log_debug(msg):
    # Standard output is used for JSON-RPC communication, so debug messages go to stderr
    sys.stderr.write(f"[MCPServer] {msg}\n")
    sys.stderr.flush()

def handle_initialize(request_id):
    response = {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {}
            },
            "serverInfo": {
                "name": "impact-core-server",
                "version": "1.0.0"
            }
        }
    }
    return response

def handle_tools_list(request_id):
    response = {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "tools": [
                {
                    "name": "run_evolution_analysis",
                    "description": "Run the multi-agent evolution analysis on two versions of a dependency graph against defined architectural intents.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "file_v1": {
                                "type": "string",
                                "description": "Path to the base version graph JSON file."
                            },
                            "file_v2": {
                                "type": "string",
                                "description": "Path to the target version graph JSON file."
                            },
                            "intents": {
                                "type": "array",
                                "items": {
                                    "type": "string"
                                },
                                "description": "List of architectural intents to evaluate."
                            }
                        },
                        "required": ["file_v1", "file_v2", "intents"]
                    }
                },
                {
                    "name": "extract_java_graph",
                    "description": "Extract a standardized IMPACT dependency graph JSON-LD from a Java source directory.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "project_name": {
                                "type": "string",
                                "description": "Name of the software project."
                            },
                            "version": {
                                "type": "string",
                                "description": "Version string of the source code."
                            },
                            "src_dir": {
                                "type": "string",
                                "description": "Path to the Java source root directory."
                            },
                            "output_file": {
                                "type": "string",
                                "description": "Path where the generated JSON-LD graph will be saved."
                            }
                        },
                        "required": ["project_name", "version", "src_dir", "output_file"]
                    }
                }
            ]
        }
    }
    return response

def handle_tools_call(request_id, params):
    tool_name = params.get("name")
    arguments = params.get("arguments", {})
    
    log_debug(f"Calling tool: {tool_name} with arguments: {arguments}")
    
    try:
        if tool_name == "run_evolution_analysis":
            coordinator = CoordinatorAgent()
            file_v1 = arguments["file_v1"]
            file_v2 = arguments["file_v2"]
            intents = arguments["intents"]
            
            report = coordinator.run_analysis(file_v1, file_v2, intents)
            result_text = report
        elif tool_name == "extract_java_graph":
            p_name = arguments["project_name"]
            ver = arguments["version"]
            s_dir = arguments["src_dir"]
            out_f = arguments["output_file"]
            
            extractor = JavaExtractor(p_name, ver)
            extractor.extract(s_dir, out_f)
            result_text = f"Successfully extracted dependency graph for {p_name} v{ver} to {out_f}"
        else:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {tool_name}"
                }
            }
            
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": result_text
                    }
                ]
            }
        }
    except Exception as e:
        log_debug(f"Error executing tool {tool_name}: {e}")
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": -32603,
                "message": str(e)
            }
        }

def main():
    log_debug("MCP Server started listening on stdio...")
    try:
        for line in sys.stdin:
            if not line.strip():
                continue
            
            try:
                request = json.loads(line)
            except json.JSONDecodeError:
                log_debug("Failed to parse input line as JSON")
                continue
            
            method = request.get("method")
            request_id = request.get("id")
            params = request.get("params", {})
            
            log_debug(f"Received request: {method} (id: {request_id})")
            
            response = None
            if method == "initialize":
                response = handle_initialize(request_id)
            elif method == "tools/list":
                response = handle_tools_list(request_id)
            elif method == "tools/call":
                response = handle_tools_call(request_id, params)
            else:
                # Default empty response or method not supported
                if request_id is not None:
                    response = {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {
                            "code": -32601,
                            "message": f"Method not found: {method}"
                        }
                    }
            
            if response:
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()
                log_debug(f"Sent response for id: {request_id}")
    except KeyboardInterrupt:
        log_debug("MCP Server shutting down...")
    except Exception as e:
        log_debug(f"Fatal server error: {e}")

if __name__ == "__main__":
    main()
