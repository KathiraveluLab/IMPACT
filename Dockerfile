FROM python:3.12-slim

LABEL maintainer="IMPACT Project"
LABEL description="IMPACT distributed crawler worker"

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency declarations first for cache efficiency
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir psycopg2-binary javalang pyshacl rdflib

# Copy project source
COPY . .

# Default entrypoint: run the crawler worker
ENTRYPOINT ["python3", "-m", "core.ecosystem_crawler"]
CMD ["crawl", "--limit", "50"]
