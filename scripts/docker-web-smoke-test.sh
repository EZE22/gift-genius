#!/usr/bin/env bash
# Smoke test for the Gift Genius web container running next to the back end.
#
# What it protects: the web image builds, nginx serves the React page and its
# JavaScript file, and nginx forwards /api to the back end container, so
# /api/health answers THROUGH the web port. That last part is the whole reason
# for nginx: a browser talks to one address, and nginx decides where each
# request goes.
#
# The contract this test relies on (the Dockerfile and nginx config must match):
#   - the back end container is named "api" on a shared network, because the
#     nginx config forwards /api to the host name "api"
#   - nginx listens on port 8080 inside the web container, because a non-root
#     user cannot bind port 80
#
# What it does not do: it never calls a model, so it needs no API key and no
# Ollama. Neither the page nor /api/health touches the model.
#
# Run it from anywhere:  scripts/docker-web-smoke-test.sh
# The same script runs in CI, so a failure on your Mac is the same failure CI sees.

# -e: stop at the first failing command. -u: an unset variable is an error.
# pipefail: a failure inside a pipe is not hidden by the last command.
set -euo pipefail

API_IMAGE="gift-genius-api:smoke-test"
WEB_IMAGE="gift-genius-web:smoke-test"
NETWORK="gift-genius-smoke-net"
API_NAME="api"
WEB_NAME="gift-genius-web-smoke"
# 8012 on the host, so it does not clash with a local dev server or the other smoke test.
HOST_PORT="${SMOKE_WEB_PORT:-8012}"
BASE_URL="http://127.0.0.1:${HOST_PORT}"

# Work from the repository root, whatever folder the script was started from.
cd "$(dirname "$0")/.."

# Always remove the containers and the network, even when a step fails.
# Without this, a failed run would leave them behind and the next run would
# clash on the names. The network goes last, because it cannot be removed
# while a container is still attached to it.
cleanup() {
  docker rm -f "$WEB_NAME" "$API_NAME" >/dev/null 2>&1 || true
  docker network rm "$NETWORK" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "Building the web image from frontend/web/ ..."
docker build -t "$WEB_IMAGE" frontend/web

echo "Building the back end image from backend/ ..."
docker build -t "$API_IMAGE" backend

# One private network. Containers on it find each other by name, which is how
# nginx reaches "api". The back end publishes NO port to the host here: only
# nginx is reachable from outside, as it would be for a customer.
echo "Starting both containers ..."
docker network create "$NETWORK" >/dev/null
docker run -d --name "$API_NAME" --network "$NETWORK" "$API_IMAGE" >/dev/null
# 127.0.0.1 on the left: the port is reachable from this machine only.
docker run -d --name "$WEB_NAME" --network "$NETWORK" -p "127.0.0.1:${HOST_PORT}:8080" "$WEB_IMAGE" >/dev/null

# Both servers need a moment to start, so ask up to 30 times, one second apart.
# The question goes through nginx: it only succeeds when nginx is up AND the
# back end is up AND nginx forwarded the request correctly.
# curl -f turns an HTTP error into a failure. -s hides the progress bar.
echo "Waiting for ${BASE_URL}/api/health through nginx ..."
healthy=false
for _ in $(seq 1 30); do
  if curl -fsS "${BASE_URL}/api/health" 2>/dev/null | grep -q '"ok":true'; then
    healthy=true
    break
  fi
  sleep 1
done

# Print both containers' own output, so the reason is in the log, not a mystery.
show_logs() {
  echo "--- web container log ---"
  docker logs "$WEB_NAME" || true
  echo "--- back end container log ---"
  docker logs "$API_NAME" || true
}

if [ "$healthy" != true ]; then
  echo "FAIL: no healthy answer through nginx after 30 seconds."
  show_logs
  exit 1
fi
echo "nginx forwarded /api/health to the back end"

# The page must be the React app: its HTML has the empty root element that the
# JavaScript fills in.
echo "Checking the page ..."
# If the request itself fails (for example a 404), say so and show the logs,
# instead of letting "set -e" stop the script with only curl's one line.
if ! page="$(curl -fsS "${BASE_URL}/")"; then
  echo "FAIL: the page request to ${BASE_URL}/ failed"
  show_logs
  exit 1
fi
if ! printf '%s' "$page" | grep -q 'id="root"'; then
  echo "FAIL: the page has no id=\"root\" element, so it is not the React app"
  exit 1
fi

# The page is useless if its JavaScript file is missing. Find the first
# /assets/*.js file the page asks for and request it. "|| true" keeps a page
# with no match from stopping the script before the clear message below, and
# ${var%%...} keeps only the first line if there are several.
asset="$(printf '%s' "$page" | grep -o '/assets/[^"]*\.js' || true)"
asset="${asset%%$'\n'*}"
if [ -z "$asset" ]; then
  echo "FAIL: the page does not reference a JavaScript file under /assets/"
  exit 1
fi
if ! curl -fsS -o /dev/null "${BASE_URL}${asset}"; then
  echo "FAIL: the JavaScript file ${asset} was not served"
  show_logs
  exit 1
fi
echo "The page and its JavaScript file (${asset}) were served"

echo "PASS: nginx serves the web app and forwards /api to the back end"
