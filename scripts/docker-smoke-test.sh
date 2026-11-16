#!/usr/bin/env bash
# Smoke test for the Gift Genius back end container.
#
# What it protects: the image builds, the API starts INSIDE the container, and
# the port published to the host answers /api/health. It passes the image no
# special settings on purpose. If the image only worked with extra flags, a
# customer running it with a plain "docker run" would get a dead server.
#
# What it does not do: it never calls a model, so it needs no API key and no
# Ollama. The health endpoint does not touch the model.
#
# Run it from anywhere:  scripts/docker-smoke-test.sh
# The same script runs in CI, so a failure on your Mac is the same failure CI sees.

# -e: stop at the first failing command. -u: an unset variable is an error.
# pipefail: a failure inside a pipe is not hidden by the last command.
set -euo pipefail

IMAGE="gift-genius-api:smoke-test"
NAME="gift-genius-smoke"
# 8011 on the host, not 8001, so a locally running API does not clash with the test.
HOST_PORT="${SMOKE_PORT:-8011}"

# Work from the repository root, whatever folder the script was started from.
cd "$(dirname "$0")/.."

# Always remove the test container, even when a step fails. Without this, a
# failed run would leave a container behind and the next run would clash on the name.
cleanup() {
  docker rm -f "$NAME" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "Building the image from backend/ ..."
docker build -t "$IMAGE" backend

# 127.0.0.1 on the left: the port is reachable from this machine only.
# The API has no authentication, so it must never be published to the network.
echo "Starting the container ..."
docker run -d --name "$NAME" -p "127.0.0.1:${HOST_PORT}:8001" "$IMAGE" >/dev/null

# The server needs a moment to start, so ask up to 30 times, one second apart.
# curl -f turns an HTTP error into a failure. -s hides the progress bar.
echo "Waiting for /api/health ..."
for _ in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:${HOST_PORT}/api/health" 2>/dev/null | grep -q '"ok":true'; then
    echo "PASS: the container answered /api/health"
    exit 0
  fi
  sleep 1
done

# Show the container's own output, so the reason is in the log, not a mystery.
echo "FAIL: no healthy answer after 30 seconds. Container log:"
docker logs "$NAME" || true
exit 1
