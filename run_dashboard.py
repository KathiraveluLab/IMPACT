import http.server
import socketserver
import webbrowser
import threading
import time
import sys

PORT = 8080

class SafeHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        # Disable caching for active development
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        super().end_headers()

def start_server():
    # Allow port reuse to prevent address-already-in-use errors
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), SafeHandler) as httpd:
        print(f"[DashboardServer] Serving on port {PORT}...")
        httpd.serve_forever()

def main():
    print("Starting IMPACT Architect Dashboard...")
    
    # Start web server in background thread
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()
    
    # Give the server a moment to bind
    time.sleep(0.5)
    
    # Open dashboard in browser
    url = f"http://localhost:{PORT}/dashboard/index.html"
    print(f"Opening browser at: {url}")
    webbrowser.open(url)
    
    print("\nPress Ctrl+C to terminate the dashboard server.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down dashboard server. Goodbye!")
        sys.exit(0)

if __name__ == "__main__":
    main()
