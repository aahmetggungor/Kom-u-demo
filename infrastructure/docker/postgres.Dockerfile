FROM pgvector/pgvector:0.8.0-pg17
RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends postgresql-17-postgis-3 && rm -rf /var/lib/apt/lists/*
COPY infrastructure/docker/init-runtime.sh /docker-entrypoint-initdb.d/10-runtime.sh
