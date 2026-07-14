import urllib.request
import urllib.parse
import urllib.error
import time

def make_github_request(url, github_token=None):
    """Executes a request to GitHub API, handling rate limits dynamically."""
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "IMPACT-Ecosystem-Crawler")
    if github_token:
        req.add_header("Authorization", f"token {github_token}")

    while True:
        try:
            with urllib.request.urlopen(req) as response:
                return response.read(), response.info()
        except urllib.error.HTTPError as e:
            if e.code == 403:
                remaining = e.headers.get("X-RateLimit-Remaining")
                reset_time = e.headers.get("X-RateLimit-Reset")
                if remaining == "0" and reset_time:
                    sleep_time = max(0, int(reset_time) - int(time.time())) + 2
                    print(f"[Rate Limit] Limit reached. Sleeping for {sleep_time} seconds...")
                    time.sleep(sleep_time)
                    continue
            raise e
