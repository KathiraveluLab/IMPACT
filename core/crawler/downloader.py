import os
import zipfile
import shutil
import urllib.request
import urllib.error

from core.crawler.network import make_github_request

def download_zip(owner, repo, tag, dest_root, github_token=None):
    """Downloads repository archive for a specific tag and extracts it."""
    zip_url = f"https://api.github.com/repos/{owner}/{repo}/zipball/{tag}"
    os.makedirs(dest_root, exist_ok=True)
    zip_path = os.path.join(dest_root, f"{tag}.zip")

    try:
        content, _ = make_github_request(zip_url, github_token)
        with open(zip_path, "wb") as f:
            f.write(content)

        # Extract zip file
        extract_dir = os.path.join(dest_root, f"src_{tag}")
        os.makedirs(extract_dir, exist_ok=True)
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(extract_dir)

        # Remove the zip archive file itself
        os.remove(zip_path)

        # The extracted zip usually creates a single top-level directory: owner-repo-hash
        children = os.listdir(extract_dir)
        if len(children) == 1:
            actual_src_dir = os.path.join(extract_dir, children[0])
            return True, (actual_src_dir, extract_dir)
        return True, (extract_dir, extract_dir)

    except Exception as e:
        print(f"Failed to download zip for {owner}/{repo} tag {tag}: {e}")
        if os.path.exists(zip_path):
            os.remove(zip_path)
        return False, (None, None)

def cleanup_path(path):
    if not path or not os.path.exists(path):
        return
    try:
        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)
    except Exception as e:
        print(f"Failed to clean up path {path}: {e}")
