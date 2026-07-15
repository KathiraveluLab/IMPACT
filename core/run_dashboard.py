import http.server
import socketserver
import webbrowser
import threading
import time
import sys
import os
import glob
import signal
import socket

DASHBOARD_PORT = 8080
API_PORT = 7842


class SafeHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        # Disable caching for active development
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        super().end_headers()

    def log_message(self, format, *args):
        pass  # silence per-request noise; the startup banner is enough


def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("", port))
            return False
        except OSError:
            return True


def get_process_using_port(port):
    """Return (pid, cmdline, is_impact) if a process is listening on the given port, else None."""
    port_hex = f"{port:04X}"
    inodes = set()
    for proto in ("tcp", "tcp6"):
        path = f"/proc/net/{proto}"
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r") as f:
                lines = f.readlines()
            for line in lines[1:]:
                parts = line.strip().split()
                if len(parts) >= 10:
                    local_addr = parts[1]
                    state = parts[3]
                    inode = parts[9]
                    # Check if port matches and state is LISTEN (0A)
                    if local_addr.endswith(":" + port_hex) and state == "0A":
                        inodes.add(inode)
        except Exception:
            pass

    if not inodes:
        return None

    # Search /proc for these inodes
    for proc_dir in glob.glob("/proc/[0-9]*"):
        try:
            pid = int(os.path.basename(proc_dir))
        except ValueError:
            continue
        fd_dir = os.path.join(proc_dir, "fd")
        if not os.path.isdir(fd_dir):
            continue
        try:
            for fd in os.listdir(fd_dir):
                fd_path = os.path.join(fd_dir, fd)
                if os.path.islink(fd_path):
                    target = os.readlink(fd_path)
                    if target.startswith("socket:[") and target.endswith("]"):
                        inode = target[8:-1]
                        if inode in inodes:
                            # Found the process! Get command line and check if it's IMPACT
                            cmdline = ""
                            try:
                                with open(f"/proc/{pid}/cmdline", "r") as f:
                                    cmdline = f.read().replace("\x00", " ").strip()
                            except Exception:
                                pass
                            
                            is_impact = False
                            if any(term in cmdline for term in ("impact-dashboard", "run_dashboard.py", "IMPACT")):
                                is_impact = True
                            else:
                                try:
                                    cwd = os.readlink(f"/proc/{pid}/cwd")
                                    if "IMPACT" in cwd or cwd.startswith("/home/pradeeban/IMPACT"):
                                        is_impact = True
                                except Exception:
                                    pass
                            
                            return pid, cmdline, is_impact
        except Exception:
            continue
    return None


def start_dashboard_server():
    try:
        socketserver.TCPServer.allow_reuse_address = True
        with socketserver.TCPServer(("", DASHBOARD_PORT), SafeHandler) as httpd:
            print(f"[Dashboard] Serving on http://localhost:{DASHBOARD_PORT}/index.html")
            httpd.serve_forever()
    except OSError as e:
        print(f"[Dashboard] Port {DASHBOARD_PORT} already in use — skipping (existing server will be used).")
    except Exception as e:
        print(f"[Dashboard] Could not start dashboard server: {e}")


def start_api_server():
    """Start the LLM Analysis API server (core.dashboard.api_server) in-process."""
    # Allow imports from the project root (two levels up from this file)
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if root not in sys.path:
        sys.path.insert(0, root)

    try:
        from core.dashboard.api_server import Handler
        from http.server import HTTPServer
        socketserver.TCPServer.allow_reuse_address = True
        server = HTTPServer(("localhost", API_PORT), Handler)
        print(f"[LLM API]   Serving on http://localhost:{API_PORT}/api/llm-analysis")
        server.serve_forever()
    except OSError as e:
        # Port already in use — another instance is running, that's fine
        print(f"[LLM API]   Port {API_PORT} already in use — skipping (existing server will be used).")
    except Exception as e:
        print(f"[LLM API]   Could not start API server: {e}")


def load_dotenv():
    """Load variables from .env file in the project root if it exists."""
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    dotenv_path = os.path.join(root_dir, ".env")
    if os.path.exists(dotenv_path):
        try:
            with open(dotenv_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        key, val = line.split("=", 1)
                        key = key.strip()
                        val = val.strip().strip("'").strip('"')
                        os.environ[key] = val
        except Exception as e:
            print(f"Warning: Could not load .env file: {e}")


def main():
    load_dotenv()
    global DASHBOARD_PORT, API_PORT
    print("Starting IMPACT Architect Dashboard...")

    # Resolve DASHBOARD_PORT
    while is_port_in_use(DASHBOARD_PORT):
        proc_info = get_process_using_port(DASHBOARD_PORT)
        if proc_info:
            pid, cmdline, is_impact = proc_info
            if is_impact:
                try:
                    choice = input(f"Port {DASHBOARD_PORT} is currently in use by an IMPACT process (PID {pid}: {cmdline}).\nWould you like to kill it? [y/N]: ").strip().lower()
                except (KeyboardInterrupt, EOFError):
                    print("\nAborting.")
                    sys.exit(1)
                if choice in ('y', 'yes'):
                    print(f"Killing process {pid}...")
                    try:
                        os.kill(pid, signal.SIGTERM)
                        for _ in range(30):
                            time.sleep(0.1)
                            if not is_port_in_use(DASHBOARD_PORT):
                                break
                        if is_port_in_use(DASHBOARD_PORT):
                            os.kill(pid, signal.SIGKILL)
                            time.sleep(0.5)
                    except Exception as e:
                        print(f"Failed to kill process: {e}")
                    
                    if not is_port_in_use(DASHBOARD_PORT):
                        continue
        print(f"Port {DASHBOARD_PORT} is in use. Trying next port...")
        DASHBOARD_PORT += 1

    # Resolve API_PORT
    while is_port_in_use(API_PORT):
        proc_info = get_process_using_port(API_PORT)
        if proc_info:
            pid, cmdline, is_impact = proc_info
            if is_impact:
                try:
                    choice = input(f"Port {API_PORT} is currently in use by an IMPACT process (PID {pid}: {cmdline}).\nWould you like to kill it? [y/N]: ").strip().lower()
                except (KeyboardInterrupt, EOFError):
                    print("\nAborting.")
                    sys.exit(1)
                if choice in ('y', 'yes'):
                    print(f"Killing process {pid}...")
                    try:
                        os.kill(pid, signal.SIGTERM)
                        for _ in range(30):
                            time.sleep(0.1)
                            if not is_port_in_use(API_PORT):
                                break
                        if is_port_in_use(API_PORT):
                            os.kill(pid, signal.SIGKILL)
                            time.sleep(0.5)
                    except Exception as e:
                        print(f"Failed to kill process: {e}")
                    
                    if not is_port_in_use(API_PORT):
                        continue
        print(f"Port {API_PORT} is in use. Trying next port...")
        API_PORT += 1

    package_dir = os.path.dirname(os.path.abspath(__file__))
    dashboard_dir = os.path.join(package_dir, "dashboard")
    
    # Write the config file for the frontend to know the resolved API port
    config_path = os.path.join(dashboard_dir, "config.js")
    try:
        with open(config_path, "w") as f:
            f.write(f"window.IMPACT_API_PORT = {API_PORT};\n")
    except Exception as e:
        print(f"Warning: Could not write config.js: {e}")

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
