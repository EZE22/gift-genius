"""Checks on the Kubernetes manifest for the back end (k8s/api.yaml).

A manifest is a plain text file, and a typo in it fails silently: a Service
whose label matches no pod simply sends traffic nowhere. These tests read the
file and check the rules a platform team will ask about. They need no cluster,
no Docker, no model and no key, so they run in CI like every other test here.

Who decides what: nothing in this file uses a model. These tests are plain
code that reads plain configuration.
"""

from pathlib import Path
from typing import Any

import yaml

# This file lives at backend/tests/, so the repository root is two levels up.
REPO_ROOT = Path(__file__).resolve().parents[2]
API_MANIFEST = REPO_ROOT / "k8s" / "api.yaml"

# The back end listens on this port inside its container. nginx in the web pods
# reaches it as http://api:8001, so the Service must publish the same port.
API_PORT = 8001


def load_documents(path: Path) -> list[dict[str, Any]]:
    """Read every YAML document in a manifest file.

    One file can hold several Kubernetes objects separated by "---", so this
    returns a list. A missing file fails with a plain message, so a failing
    test says "the file is missing" and not a confusing Python error.
    """
    assert path.exists(), f"missing manifest: {path.relative_to(REPO_ROOT)}"
    return [doc for doc in yaml.safe_load_all(path.read_text()) if doc]


def find_one(documents: list[dict[str, Any]], kind: str) -> dict[str, Any]:
    """Return the single object of the given kind, or fail if there is not exactly one."""
    matches = [doc for doc in documents if doc.get("kind") == kind]
    assert len(matches) == 1, f"expected exactly one {kind}, found {len(matches)}"
    return matches[0]


def api_container(deployment: dict[str, Any]) -> dict[str, Any]:
    """Return the one container in the Deployment's pod template."""
    containers = deployment["spec"]["template"]["spec"]["containers"]
    assert len(containers) == 1, "the api pod should run exactly one container"
    return containers[0]


def test_manifest_holds_one_deployment_and_one_service():
    """Protects the shape of the file: one Deployment (the pods) and one Service (the front door)."""
    kinds = sorted(doc["kind"] for doc in load_documents(API_MANIFEST))
    assert kinds == ["Deployment", "Service"]


def test_service_is_named_api_and_stays_inside_the_cluster():
    """Protects the name nginx relies on and the rule that the back end is never exposed.

    The web pods call http://api:8001, so the Service name must be "api". The
    API has no authentication, so the Service type must be ClusterIP, which is
    reachable only from inside the cluster. A NodePort or LoadBalancer here
    would put an unauthenticated API on the network.
    """
    service = find_one(load_documents(API_MANIFEST), "Service")
    assert service["metadata"]["name"] == "api"
    assert service["spec"].get("type", "ClusterIP") == "ClusterIP"
    (port,) = service["spec"]["ports"]
    assert port["port"] == API_PORT
    assert port["targetPort"] == API_PORT


def test_service_selector_matches_the_pod_labels():
    """Protects the silent failure: a Service whose label matches no pod sends traffic nowhere.

    Three labels must agree. The Deployment selects pods by label, the pod
    template carries that label, and the Service selects the same label.
    """
    documents = load_documents(API_MANIFEST)
    deployment = find_one(documents, "Deployment")
    service = find_one(documents, "Service")
    pod_labels = deployment["spec"]["template"]["metadata"]["labels"]

    deployment_selector = deployment["spec"]["selector"]["matchLabels"]
    assert deployment_selector.items() <= pod_labels.items()

    service_selector = service["spec"]["selector"]
    assert service_selector, "a Service with no selector matches no pods"
    assert service_selector.items() <= pod_labels.items()


def test_deployment_runs_the_local_api_image_on_the_right_port():
    """Protects the image name, the port and the pull policy.

    The image is the one Compose already builds, gift-genius-api:latest. A
    ":latest" tag makes Kubernetes try to pull from the internet by default,
    which fails because this image exists only on the Mac. IfNotPresent tells
    it to use the local copy first.
    """
    container = api_container(find_one(load_documents(API_MANIFEST), "Deployment"))
    assert container["image"] == "gift-genius-api:latest"
    assert container["imagePullPolicy"] == "IfNotPresent"
    assert {p["containerPort"] for p in container["ports"]} == {API_PORT}


def test_deployment_asks_for_one_api_pod():
    """Protects the replica count. The back end stays at one pod on purpose.

    Ollama on an 8 GB Mac is the bottleneck, so more api pods would only queue
    more model calls. The web Deployment is where we practice scaling.
    """
    deployment = find_one(load_documents(API_MANIFEST), "Deployment")
    assert deployment["spec"]["replicas"] == 1


def test_no_secret_looking_settings_in_the_manifest():
    """Protects the rule that keys never appear in a committed file.

    The model settings will come from a ConfigMap in a later piece, and none of
    them is a secret. If a variable with a key-like name shows up here, someone
    is about to commit a credential.
    """
    container = api_container(find_one(load_documents(API_MANIFEST), "Deployment"))
    names = [item["name"].upper() for item in container.get("env", [])]
    for word in ("KEY", "TOKEN", "SECRET", "PASSWORD"):
        assert not any(word in name for name in names), f"{word} found in env names {names}"
