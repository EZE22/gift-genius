#!/usr/bin/env bash
# Smoke test for the Docker Compose setup: one command starts the back end and
# the web front end together.
#
# What it protects: "docker compose up --wait" brings BOTH services to a
# healthy state, the page and /api/health answer through the web port, the web
# port is published to this machine only, and the back end publishes no port at
# all. Only nginx should be reachable from outside, and the back end has no
# authentication, so it must never be.
#
# The contract this test relies on (compose.yaml must match):
#   - the services are named "api" and "web"
#   - the web service publishes to host port ${WEB_PORT}, on 127.0.0.1 only
#   - the api service has a health check, so "--wait" has something to wait for
#
# What it does not do: it never calls a model, so it needs no API key and no
# Ollama. Neither the page nor /api/health touches the model. A real search is
# a manual check, because it needs a running model.
#
# Run it from anywhere:  scripts/docker-compose-smoke-test.sh
# The same script runs in CI, so a failure on your Mac is the same failure CI sees.

# -e: stop at the first failing command. -u: an unset variable is an error.
# pipefail: a failure inside a pipe is not hidden by the last command.
set -euo pipefail

PROJECT="gift-genius-smoke"
# compose.yaml reads WEB_PORT. 8013 on the host, so a stack you started by hand
# on its normal port does not clash with this test.
export WEB_PORT="${SMOKE_COMPOSE_PORT:-8013}"
BASE_URL="http://127.0.0.1:${WEB_PORT}"

# Work from the repository root, whatever folder the script was started from.
cd "$(dirname "$0")/.."

# One place that says how Compose is called. "-p" gives the test its own
# project name, so "down" can never touch a stack you are running by hand.
# "--env-file /dev/null" makes Compose ignore your real .env file, so the test
# behaves the same on your Mac and in CI, and never reads your settings.
compose() {
  docker compose -p "$PROJECT" --env-file /dev/null "$@"
}

# Always stop and remove everything, even when a step fails. Without this, a
# failed run would leave containers and a network behind.
cleanup() {
  compose down --volumes --remove-orphans >/dev/null 2>&1 || true
}
trap cleanup EXIT

# "--build" builds both images. "--wait" waits until every service is running
# and every health check passes, and fails if one does not.
echo "Starting the stack with docker compose ..."
if ! compose up -d --build --wait --wait-timeout 180; then
  echo "FAIL: docker compose up did not bring the services to a healthy state"
  compose logs || true
  exit 1
fi

# The web container has no health check, so give nginx a moment, up to 10 tries.
# The question goes through nginx to the back end, so it only succeeds when
# the whole chain works.
echo "Checking ${BASE_URL}/api/health through nginx ..."
healthy=false
for _ in $(seq 1 10); do
  if curl -fsS "${BASE_URL}/api/health" 2>/dev/null | grep -q '"ok":true'; then
    healthy=true
    break
  fi
  sleep 1
done
if [ "$healthy" != true ]; then
  echo "FAIL: no healthy answer through the web port"
  compose logs || true
  exit 1
fi

# The page must be the React app: its HTML has the empty root element.
# (The JavaScript file itself is checked by docker-web-smoke-test.sh.)
if ! curl -fsS "${BASE_URL}/" | grep -q 'id="root"'; then
  echo "FAIL: the page has no id=\"root\" element, so it is not the React app"
  compose logs || true
  exit 1
fi
echo "The page and /api/health answered through the web port"

# Ask Docker which ports each container really publishes. This is the check
# that keeps the back end private: an unpublished port shows as null, a
# published one shows a HostPort.
api_ports="$(docker inspect -f '{{json .NetworkSettings.Ports}}' "$(compose ps -q api)")"
web_ports="$(docker inspect -f '{{json .NetworkSettings.Ports}}' "$(compose ps -q web)")"

if printf '%s' "$api_ports" | grep -q 'HostPort'; then
  echo "FAIL: the api service publishes a port to the host: ${api_ports}"
  exit 1
fi
if ! printf '%s' "$web_ports" | grep -q '"HostIp":"127.0.0.1"'; then
  echo "FAIL: the web port is not limited to 127.0.0.1: ${web_ports}"
  exit 1
fi
echo "Only the web port is published, and only on 127.0.0.1"

echo "PASS: docker compose starts both services and only web is reachable"
