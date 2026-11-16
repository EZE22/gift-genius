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
WEB_MANIFEST = REPO_ROOT / "k8s" / "web.yaml"
CONFIG_MANIFEST = REPO_ROOT / "k8s" / "configmap.yaml"

# The back end listens on this port inside its container. nginx in the web pods
# reaches it as http://api:8001, so the Service must publish the same port.
API_PORT = 8001

# nginx in the web image listens on 8080 (the unprivileged nginx image cannot use 80).
WEB_PORT = 8080


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


def only_container(deployment: dict[str, Any]) -> dict[str, Any]:
    """Return the one container in a Deployment's pod template."""
    containers = deployment["spec"]["template"]["spec"]["containers"]
    assert len(containers) == 1, "the pod should run exactly one container"
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


def assert_selectors_line_up(documents: list[dict[str, Any]]) -> None:
    """Check that the Deployment, its pod template and the Service all use the same label.

    The Deployment selects pods by label, the pod template carries that label,
    and the Service selects the same label. If any of the three is mistyped,
    Kubernetes accepts the file and nothing errors: traffic just goes nowhere.
    """
    deployment = find_one(documents, "Deployment")
    service = find_one(documents, "Service")
    pod_labels = deployment["spec"]["template"]["metadata"]["labels"]

    deployment_selector = deployment["spec"]["selector"]["matchLabels"]
    assert deployment_selector.items() <= pod_labels.items()

    service_selector = service["spec"]["selector"]
    assert service_selector, "a Service with no selector matches no pods"
    assert service_selector.items() <= pod_labels.items()


def test_service_selector_matches_the_pod_labels():
    """Protects the silent failure: an api Service whose label matches no pod sends traffic nowhere."""
    assert_selectors_line_up(load_documents(API_MANIFEST))


def test_deployment_runs_the_local_api_image_on_the_right_port():
    """Protects the image name, the port and the pull policy.

    The image is the one Compose already builds, gift-genius-api:latest. A
    ":latest" tag makes Kubernetes try to pull from the internet by default,
    which fails because this image exists only on the Mac. IfNotPresent tells
    it to use the local copy first.
    """
    container = only_container(find_one(load_documents(API_MANIFEST), "Deployment"))
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
    container = only_container(find_one(load_documents(API_MANIFEST), "Deployment"))
    names = [item["name"].upper() for item in container.get("env", [])]
    for word in ("KEY", "TOKEN", "SECRET", "PASSWORD"):
        assert not any(word in name for name in names), f"{word} found in env names {names}"


# ---------------------------------------------------------------------------
# The web manifest (k8s/web.yaml): nginx serving the React app, two pods.
# ---------------------------------------------------------------------------


def test_web_manifest_holds_one_deployment_and_one_service():
    """Protects the shape of the web file: one Deployment (the pods) and one Service (the front door)."""
    kinds = sorted(doc["kind"] for doc in load_documents(WEB_MANIFEST))
    assert kinds == ["Deployment", "Service"]


def test_web_service_is_named_web_and_stays_inside_the_cluster():
    """Protects the rule that nothing is exposed to the network.

    The web page forwards /api to a back end with no authentication, so putting
    the web Service on the network would expose that API too. ClusterIP keeps it
    inside the cluster, and we reach it from the Mac with kubectl port-forward,
    which binds to 127.0.0.1 only. A customer would use an Ingress or a load
    balancer with a sign-in in front instead.
    """
    service = find_one(load_documents(WEB_MANIFEST), "Service")
    assert service["metadata"]["name"] == "web"
    assert service["spec"].get("type", "ClusterIP") == "ClusterIP"
    (port,) = service["spec"]["ports"]
    assert port["port"] == WEB_PORT
    assert port["targetPort"] == WEB_PORT


def test_web_service_selector_matches_the_pod_labels():
    """Protects the silent failure: a web Service whose label matches no pod sends traffic nowhere."""
    assert_selectors_line_up(load_documents(WEB_MANIFEST))


def test_web_and_api_use_different_labels():
    """Protects against the classic copy and paste mistake.

    The web file is written by copying the api file. If the label "app: api"
    survives the copy, the web Service would send page requests to the back end
    pods, and the Deployments would fight over each other's pods.
    """
    web = find_one(load_documents(WEB_MANIFEST), "Deployment")
    api = find_one(load_documents(API_MANIFEST), "Deployment")
    web_labels = web["spec"]["template"]["metadata"]["labels"]
    api_labels = api["spec"]["template"]["metadata"]["labels"]
    assert web_labels["app"] == "web"
    assert web_labels["app"] != api_labels["app"]


def test_web_deployment_runs_the_local_web_image_on_the_right_port():
    """Protects the image name, the port and the pull policy for the web pods.

    The image is the one Compose already builds, gift-genius-web:latest. As with
    the api, IfNotPresent makes Kubernetes use the copy on this Mac instead of
    trying to pull a ":latest" image from the internet.
    """
    container = only_container(find_one(load_documents(WEB_MANIFEST), "Deployment"))
    assert container["image"] == "gift-genius-web:latest"
    assert container["imagePullPolicy"] == "IfNotPresent"
    assert {p["containerPort"] for p in container["ports"]} == {WEB_PORT}


def test_web_deployment_asks_for_two_pods():
    """Protects the replica count. Web runs two pods so we can practice scaling and self-healing.

    nginx serving static files is cheap, so a second copy costs almost nothing.
    Two pods also show the Service sharing traffic and a pod being replaced
    while the page stays up.
    """
    deployment = find_one(load_documents(WEB_MANIFEST), "Deployment")
    assert deployment["spec"]["replicas"] == 2


# ---------------------------------------------------------------------------
# The settings file (k8s/configmap.yaml): model settings kept outside the image.
# ---------------------------------------------------------------------------

# The name the api Deployment uses to find its settings. Both files must agree.
CONFIG_NAME = "gift-genius-config"


def test_configmap_holds_the_three_model_settings():
    """Protects the settings the back end reads at start up.

    client.py reads MODEL_SOURCE, OLLAMA_BASE_URL and OLLAMA_MODEL from the
    environment. Without MODEL_SOURCE=ollama the back end looks for an API key
    and fails. The base URL must point at the Mac, because Ollama runs outside
    the cluster and "localhost" inside a pod means the pod itself. These are not
    secrets, so a ConfigMap (plain text settings) is the right home for them.
    """
    config_map = find_one(load_documents(CONFIG_MANIFEST), "ConfigMap")
    assert config_map["metadata"]["name"] == CONFIG_NAME
    data = config_map["data"]
    assert data["MODEL_SOURCE"] == "ollama"
    assert data["OLLAMA_BASE_URL"] == "http://host.docker.internal:11434"
    assert data["OLLAMA_MODEL"].strip() != ""


def test_api_deployment_reads_its_settings_from_the_configmap():
    """Protects the link between the pod and its settings.

    A ConfigMap that no pod points at does nothing, and a wrong name fails
    silently until the pod cannot reach the model. This checks the api
    container loads every key from the ConfigMap with the matching name.
    """
    container = only_container(find_one(load_documents(API_MANIFEST), "Deployment"))
    config_names = [
        source["configMapRef"]["name"]
        for source in container.get("envFrom", [])
        if "configMapRef" in source
    ]
    assert config_names == [CONFIG_NAME]


# ---------------------------------------------------------------------------
# Health probes: how Kubernetes asks each pod whether it is working.
# ---------------------------------------------------------------------------


def get_http_probe(container: dict[str, Any], kind: str) -> dict[str, Any]:
    """Return the HTTP check for "readinessProbe" or "livenessProbe", or fail with a clear message."""
    assert kind in container, f"container has no {kind}"
    probe = container[kind]
    assert "httpGet" in probe, f"{kind} should be an HTTP check"
    return probe


def test_api_probes_ask_the_health_endpoint():
    """Protects the api pod from taking traffic before it can answer.

    The back end already answers GET /api/health. Both probes must use that
    path on the container port. The check only proves the process responds. It
    does not call Ollama on purpose: a slow model must never make Kubernetes
    restart a healthy pod.
    """
    container = only_container(find_one(load_documents(API_MANIFEST), "Deployment"))
    for kind in ("readinessProbe", "livenessProbe"):
        check = get_http_probe(container, kind)["httpGet"]
        assert check["path"] == "/api/health"
        assert check["port"] == API_PORT


def test_web_probes_ask_for_the_home_page():
    """Protects the web pods from taking traffic before nginx can serve the page.

    nginx serves index.html at "/". If the file is missing, "/" returns a 404
    and the probe fails, which is the signal we want. The probe asks nginx only,
    never the api, so a slow back end cannot mark the web pods unhealthy.
    """
    container = only_container(find_one(load_documents(WEB_MANIFEST), "Deployment"))
    for kind in ("readinessProbe", "livenessProbe"):
        check = get_http_probe(container, kind)["httpGet"]
        assert check["path"] == "/"
        assert check["port"] == WEB_PORT


def test_liveness_never_starts_checking_before_readiness():
    """Protects a slow starting pod from being killed.

    Liveness restarts the pod when it fails. If it began checking earlier than
    readiness, a pod that is merely still starting could be restarted again and
    again, a loop that never lets it finish. So liveness must wait at least as
    long as readiness before its first check.
    """
    for manifest in (API_MANIFEST, WEB_MANIFEST):
        container = only_container(find_one(load_documents(manifest), "Deployment"))
        ready = get_http_probe(container, "readinessProbe").get("initialDelaySeconds", 0)
        live = get_http_probe(container, "livenessProbe").get("initialDelaySeconds", 0)
        assert live >= ready, f"{manifest.name}: liveness starts before readiness"
