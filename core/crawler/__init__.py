import os
from core.crawler.crawler import GitHubEcosystemCrawler
from core.crawler.database import DB_PATH as _DEFAULT_DB_PATH

# Allow Kubernetes pods (or any deployment) to override the database path/DSN
# via the IMPACT_DB_PATH environment variable.
# Set to a postgresql:// URI for distributed multi-node operation.
DB_PATH = os.environ.get("IMPACT_DB_PATH", _DEFAULT_DB_PATH)
