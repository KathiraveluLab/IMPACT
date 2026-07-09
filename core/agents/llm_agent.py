import os
import json
import urllib.request
import urllib.error

class LLMAgent:
    """Specialized agent that uses LLMs to interpret structural changes and write architectural explanations."""
    
    def __init__(self, name: str = "LLMAgent"):
        self.name = name

    def execute(self, diff_report: dict, metrics_report: dict, intents: list) -> str:
        """Synthesizes diff and metrics reports into a coherent architectural summary relative to defined intents."""
        
        # Build prompt
        prompt = (
            f"Please analyze the following software architecture evolution and evaluate conformance to the specified intents.\n\n"
            f"Intents:\n" + "\n".join([f"- {intent}" for intent in intents]) + "\n\n"
            f"Structural Diff Report:\n"
            f"- Version: {diff_report['version_old']} -> {diff_report['version_new']}\n"
            f"- Added Nodes Count: {diff_report['added_nodes_count']} ({diff_report['raw_diff']['added_nodes']})\n"
            f"- Removed Nodes Count: {diff_report['removed_nodes_count']} ({diff_report['raw_diff']['removed_nodes']})\n"
            f"- Added Edges Count: {diff_report['added_edges_count']} ({diff_report['raw_diff']['added_edges']})\n"
            f"- Removed Edges Count: {diff_report['removed_edges_count']} ({diff_report['raw_diff']['removed_edges']})\n"
            f"- New Cycles Count: {diff_report['new_cycles_count']} ({diff_report['raw_diff']['new_cycles']})\n"
            f"- Broken Cycles Count: {diff_report['broken_cycles_count']} ({diff_report['raw_diff']['broken_cycles']})\n\n"
            f"Centrality Metrics:\n"
            f"- Top Hubs: {json.dumps(metrics_report['top_hubs'])}\n\n"
            f"Generate a report with the following structure:\n"
            f"1. Structural Changes\n"
            f"2. Dependency Cycles\n"
            f"3. Coupling & Complexity Hubs\n"
            f"4. Intent Conformance Evaluation (mark clearly as VIOLATION if any intent is breached)\n"
            f"5. Recommendations"
        )
        
        # Attempt to make a live API call if keys are present
        response_text = self._try_live_api(prompt)
        if response_text:
            return response_text
            
        # Fallback to local rule-based summary generator
        return self._generate_local_fallback(diff_report, metrics_report, intents)

    def _try_live_api(self, prompt: str) -> str:
        openai_key = os.environ.get("OPENAI_API_KEY")
        gemini_key = os.environ.get("GEMINI_API_KEY")
        custom_endpoint = os.environ.get("LLM_API_URL")
        
        # 1. Custom Endpoint or OpenAI API base compatibility
        if custom_endpoint or openai_key:
            url = custom_endpoint if custom_endpoint else "https://api.openai.com/v1/chat/completions"
            key = openai_key if openai_key else "placeholder"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key}"
            }
            data = {
                "model": os.environ.get("LLM_MODEL", "gpt-4o-mini"),
                "messages": [
                    {"role": "system", "content": "You are an expert software architect analyzing codebase changes and intent conformance."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.2
            }
            return self._send_post_request(url, headers, data)
            
        # 2. Gemini Developer API
        elif gemini_key:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_key}"
            headers = {"Content-Type": "application/json"}
            data = {
                "contents": [{
                    "parts": [{"text": "You are an expert software architect analyzing codebase changes and intent conformance.\n\n" + prompt}]
                }],
                "generationConfig": {
                    "temperature": 0.2
                }
            }
            res_json = self._send_post_request(url, headers, data)
            if res_json:
                try:
                    parsed = json.loads(res_json)
                    return parsed["candidates"][0]["content"]["parts"][0]["text"]
                except Exception:
                    pass
                    
        return None

    def _send_post_request(self, url: str, headers: dict, data: dict) -> str:
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(data).encode("utf-8"),
                headers=headers,
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                res_body = response.read().decode("utf-8")
                
                # If OpenAI style, extract text content
                if "chat/completions" in url or "openai" in url:
                    parsed = json.loads(res_body)
                    return parsed["choices"][0]["message"]["content"]
                return res_body
        except Exception as e:
            # Silence warning if no credentials were provided and we just tried placeholder
            if "placeholder" not in headers.get("Authorization", ""):
                print(f"[LLMAgent] Live API call failed (falling back to local evaluation): {e}")
            return None

    def _generate_local_fallback(self, diff_report: dict, metrics_report: dict, intents: list) -> str:
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
