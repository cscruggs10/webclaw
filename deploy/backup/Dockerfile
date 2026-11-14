# Nightly pg_dump of the ERPClaw books into the same S3-compatible bucket
# used for uploads. The client major version must be at least the server's.
FROM postgres:17-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-pip \
    && pip3 install --break-system-packages --no-cache-dir boto3==1.35.99 \
    && rm -rf /var/lib/apt/lists/*

COPY backup.py /backup.py
# Drop the Postgres image entrypoint so it does not try to boot a server.
ENTRYPOINT ["python3", "/backup.py"]
USER postgres
