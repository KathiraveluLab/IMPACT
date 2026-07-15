import http.server
import socketserver
import webbrowser
import threading
import time
import sys
import os

DASHBOARD_PORT = 8080
API_PORT = 7842


class SafeHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        # Disable caching for active development
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        super().end_headers()

    def log_message(self, format, *args):
        pass  # silence per-request noise; the startup banner is enough


def start_dashboard_server():
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", DASHBOARD_PORT), SafeHandler) as httpd:
        print(f"[Dashboard] Serving on http://localhost:{DASHBOARD_PORT}/index.html")
        httpd.serve_forever()


def start_api_server():
    """Start the LLM Analysis API server (core.dashboard.api_server) in-process."""
    # Allow imports from the project root (two levels up from this file)
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if root not in sys.path:
        sys.path.insert(0, root)

    try:
        from core.dashboard.api_server import Handler, PORT as _PORT
        from http.server import HTTPServer
        socketserver.TCPServer.allow_reuse_address = True
        server = HTTPServer(("localhost", _PORT), Handler)
        print(f"[LLM API]   Serving on http://localhost:{_PORT}/api/llm-analysis")
        server.serve_forever()
    except OSError as e:
        # Port already in use — another instance is running, that's fine
        print(f"[LLM API]   Port {API_PORT} already in use — skipping (existing server will be used).")
    except Exception as e:
        print(f"[LLM API]   Could not start API server: {e}")


def main():
    print("Starting IMPACT Architect Dashboard...")

    package_dir = os.path.dirname(os.path.abspath(__file__))
    dashboard_dir = os.path.join(package_dir, "dashboard")
    os.chdir(dashboard_dir)

    # Start LLM API server in background daemon thread
    api_thread = threading.Thread(target=start_api_server, daemon=True)
    api_thread.start()

    # Start dashboard web server in background daemon thread
    server_thread = threading.Thread(target=start_dashboard_server, daemon=True)
    server_thread.start()

    # Give both servers a moment to bind before opening the browser
    time.sleep(0.8)

    url = f"http://localhost:{DASHBOARD_PORT}/index.html"
    print(f"[Browser]   Opening {url}")
    webbrowser.open(url)

    print("\nPress Ctrl+C to stop all servers.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down. Goodbye!")
        sys.exit(0)


if __name__ == "__main__":
    main()
