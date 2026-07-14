# Database Schema and Ecosystem Crawler CLI Documentation

This document describes the database schema used by the IMPACT Crawler (SQLite and PostgreSQL backends) and details the CLI commands for crawler and AST extraction.

---

## 1. Database Schema Specifications

IMPACT supports two database backends:
1. **SQLite**: For single-node local runs (default).
2. **PostgreSQL**: For distributed containerized runs on Kubernetes clusters.

### `crawler_queue` Table
Maintains the queue state of repositories discovered from the GitHub ecosystem.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `repository` | `VARCHAR(255)` | `PRIMARY KEY` | The unique GitHub owner/repo identifier (e.g. `jhy/jsoup`). |
| `status` | `VARCHAR(50)` | `NOT NULL` | Queue state: `pending`, `processing`, `crawled`, `failed`. |
| `worker_id` | `VARCHAR(100)` | `NULL` | ID of the crawler worker container claiming this job. |
| `claimed_at` | `TIMESTAMP` | `NULL` | Time when a worker claimed the repository. |
| `updated_at` | `TIMESTAMP` | `NULL` | Time of the last state transition. |

### SQLite Queue Table Creation
```sql
CREATE TABLE IF NOT EXISTS crawler_queue (
    repository TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    worker_id TEXT DEFAULT NULL,
    claimed_at TIMESTAMP DEFAULT NULL,
    updated_at TIMESTAMP DEFAULT NULL
);
```

---

## 2. Command Line Interface (CLI) Usage

IMPACT installs multiple console script entrypoints when packaged as a Python package.

### A. Ecosystem Crawler (`impact-crawl`)
Used to scan GitHub, populate the queue, and run distributed crawlers.

* **Discover Repositories**:
  ```bash
  # Scans GitHub for Java projects with more than 1000 stars and adds them to the queue
  impact-crawl discover --min-stars 1000 --limit 100
  ```

* **Run Crawler Workers**:
  ```bash
  # Starts processing the queue (defaults to local SQLite database)
  impact-crawl crawl --limit 50
  ```

* **Configure Backend Connection**:
  Specify database connections via the `--db-uri` flag or set the environment variable `DATABASE_URL`:
  ```bash
  export DATABASE_URL="postgresql://impact:password@postgres-service:5432/crawler_db"
  impact-crawl crawl --limit 50
  ```

### B. AST Extractor (`impact-extract`)
Used to run AST-like semantic extraction on local directories.

```bash
# Parses Java files in the source directory and saves the graph
impact-extract --src ./my_project/src --out ./graph.json --name "MyProj" --version "1.0.0"
```
