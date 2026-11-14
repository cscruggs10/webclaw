# Webclaw API plus ERPClaw and AutomotiveClaw.
# ERPClaw and AutomotiveClaw are cloned at build time from Corey's forks.
# Change the refs to move the books' code; do not float on an unpinned branch.
#
#   docker build \
#     --build-arg ERPCLAW_REF=<sha> \
#     --build-arg AUTOMOTIVE_REF=<sha> \
#     -t webclaw-api .

FROM python:3.12-slim-bookworm

ARG ERPCLAW_REPO=https://github.com/cscruggs10/erpclaw.git
ARG ERPCLAW_REF=aea97950a7d78615fc06d1d129c17c7775b38581
ARG AUTOMOTIVE_REPO=https://github.com/cscruggs10/automotiveclaw.git
ARG AUTOMOTIVE_REF=6123ef7575dde4f3b706c8fff5967717d4c587db

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ERPCLAW_HOME=/data/erpclaw \
    ERPCLAW_DIR=/opt/skills/erpclaw \
    AUTOMOTIVE_DIR=/opt/skills/automotiveclaw \
    SKILLS_DIR=/opt/skills \
    OPENCLAW_SKILLS_DIR=/opt/skills \
    WEBCLAW_DB_PATH=/data/webclaw/webclaw.sqlite \
    UPLOAD_DIR=/data/uploads \
    WEBCLAW_ENV=production \
    PORT=8001

RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY api/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

RUN mkdir -p /opt/skills \
    && git clone "${ERPCLAW_REPO}" /opt/skills/erpclaw \
    && git -C /opt/skills/erpclaw checkout --detach "${ERPCLAW_REF}" \
    && rm -rf /opt/skills/erpclaw/.git \
    && git clone "${AUTOMOTIVE_REPO}" /opt/skills/automotiveclaw \
    && git -C /opt/skills/automotiveclaw checkout --detach "${AUTOMOTIVE_REF}" \
    && rm -rf /opt/skills/automotiveclaw/.git

COPY api/ /opt/webclaw/api/
WORKDIR /opt/webclaw/api

EXPOSE 8001
CMD ["python", "-m", "entrypoint"]
