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

    backoff = 2
    while True:
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                return response.read(), response.info()
        except urllib.error.HTTPError as e:
            if e.code in (403, 429):
                # Check for Retry-After first (typical for secondary rate limit or 429)
                retry_after = e.headers.get("Retry-After")
                if retry_after:
                    try:
                        sleep_time = int(retry_after) + 2
                        print(f"[Rate Limit] Retry-After header found. Sleeping for {sleep_time} seconds...")
                        time.sleep(sleep_time)
                        continue
                    except ValueError:
                        pass

                # Check for X-RateLimit headers (primary rate limit / search limit)
                remaining = e.headers.get("X-RateLimit-Remaining")
                reset_time = e.headers.get("X-RateLimit-Reset")
                if remaining == "0" and reset_time:
                    try:
                        sleep_time = max(0, int(reset_time) - int(time.time())) + 2
                        print(f"[Rate Limit] Primary/Search rate limit reached. Sleeping for {sleep_time} seconds...")
                        time.sleep(sleep_time)
                        continue
                    except ValueError:
                        pass

                # Fallback: if we hit a 403/429 but no headers are present or parsing failed,
                # it's likely a secondary rate limit or abuse detection. Sleep with exponential backoff.
                print(f"[Rate Limit] Hit rate limit/abuse limit (HTTP {e.code}). Backing off for {backoff} seconds...")
                time.sleep(backoff)
                backoff = min(backoff * 2, 60)  # Max 60 seconds backoff per retry
                continue
            raise e
