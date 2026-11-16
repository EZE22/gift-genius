#!/usr/bin/env bash
# Smoke test for the Gift Genius back end container.
#
# What it protects: the image builds, the API starts INSIDE the container, the
# port published to the host answers /api/health, and the gift catalog file is
# inside the image and loads. It passes the image no special settings on
# purpose. If the image only worked with extra flags, a customer running it
# with a plain "docker run" would get a dead server.
#
# Why the catalog has its own check: /api/health never reads the catalog, so an
# image missing data/catalog.json would still pass the health check and then
# fail on the first real gift search.
#
# What it does not do: it never calls a model, so it needs no API key and no
# Ollama. Neither the health endpoint nor the catalog loader touches the model.
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
# "healthy" records whether any attempt succeeded, so the steps after the loop
# can run only when the server is really up.
echo "Waiting for /api/health ..."
healthy=false
for _ in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:${HOST_PORT}/api/health" 2>/dev/null | grep -q '"ok":true'; then
    healthy=true
    break
  fi
  sleep 1
done

# Show the container's own output, so the reason is in the log, not a mystery.
if [ "$healthy" != true ]; then
  echo "FAIL: no healthy answer after 30 seconds. Container log:"
  docker logs "$NAME" || true
  exit 1
fi
echo "The container answered /api/health"

# Run the real catalog loader inside the running container. A missing file
# raises FileNotFoundError and an empty catalog fails the assert. Either way
# python exits with an error, and "set -e" stops this script with that error.
# It checks "more than zero" and not an exact count, so adding gifts to the
# catalog later does not break this test.
echo "Checking the catalog file is inside the image ..."
docker exec "$NAME" python -c "
from gift_genius.tools.catalog import load_catalog
count = len(load_catalog())
assert count > 0, 'the catalog is empty'
print(f'catalog loaded: {count} items')
"

echo "PASS: the container answers /api/health and the catalog loads"
