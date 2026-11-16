# Image for the Gift Genius back end API. Plain code: this file only packages
# the app. It decides nothing about routing, tools or the model.

# One pinned Python version, the same one CI uses. "slim" leaves out compilers
# and docs, so the image is smaller and has less in it to attack.
FROM python:3.12-slim

# No .pyc files (useless in a container). Unbuffered output sends log lines
# straight to "docker logs" instead of holding them back.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# The API listens on 127.0.0.1 by default, which inside a container means only
# the container itself. 0.0.0.0 lets the published port reach it. This is safe
# because the person running the container decides which host address
# the port is published to (see docker-smoke-test.sh: 127.0.0.1 only).
ENV GIFT_GENIUS_API_HOST=0.0.0.0

WORKDIR /app

# Copy only what the install needs. tests and .venv are kept out by .dockerignore.
COPY pyproject.toml ./
COPY src ./src

# The "api" extra adds FastAPI and uvicorn. --no-cache-dir keeps pip's download
# cache out of the image. A normal install, not editable, so the image holds a
# finished copy of the package, including data/catalog.json.
RUN pip install --no-cache-dir ".[api]"

# Run as a normal user, not root. If the server is ever compromised, the
# attacker does not get root inside the container.
RUN useradd --create-home app
USER app

# Documentation only: it does not publish the port. "docker run -p" does that.
EXPOSE 8001

# Tells Docker whether the server is really answering, not just running.
# Compose's "--wait" and "depends_on: service_healthy" use this, and so will a
# Kubernetes probe later. The check uses Python because the slim image has no
# curl. urlopen raises an error on a refused connection or a non-2xx answer,
# and an error makes Python exit with a failure. It reads the same port
# variable the server reads, so changing the port cannot break the check.
HEALTHCHECK --interval=5s --timeout=3s --start-period=5s --retries=10 \
  CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('GIFT_GENIUS_API_PORT', '8001') + '/api/health', timeout=2)"]

# The command the package installs (gift-genius-api). Model settings such as
# OLLAMA_BASE_URL are NOT baked in. They are passed when the container starts.
CMD ["gift-genius-api"]
