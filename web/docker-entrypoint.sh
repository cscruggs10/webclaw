#!/bin/sh
# HOSTNAME is overwritten by Docker with the container id. Next.js standalone
# uses HOSTNAME as the bind address, so set it again here.
set -eu
export HOSTNAME=0.0.0.0
export PORT="${PORT:-3000}"
exec node server.js
