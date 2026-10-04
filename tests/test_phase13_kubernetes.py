"""Phase 13 — Kubernetes deployment validation.

These tests validate the manifests structurally and do not require a cluster.
Where `kubectl` is available the rendered kustomization is validated as well,
which catches reference and selector problems that plain YAML parsing misses.
"""

import os
import re
import shutil
import subprocess

import pytest
import yaml

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
K8S_DIR = os.path.join(REPO_ROOT, "k8s")

WORKLOAD_KINDS = {"Deployment", "StatefulSet"}
NAMESPACE = "sentryops"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _iter_yaml_files():
    for root, _dirs, files in os.walk(K8S_DIR):
        for name in sorted(files):
            if name.endswith((".yaml", ".yml")):
                yield os.path.join(root, name)


def load_k8s_documents():
    docs = []
    for path in _iter_yaml_files():
        with open(path, encoding="utf-8") as handle:
            for doc in yaml.safe_load_all(handle):
                if doc:
                    docs.append((os.path.relpath(path, REPO_ROOT), doc))
    return docs


def _documents():
    return [doc for _path, doc in load_k8s_documents()]


def _by_kind(kind):
    return [d for d in _documents() if d.get("kind") == kind]


def _workloads():
    return [d for d in _documents() if d.get("kind") in WORKLOAD_KINDS]


def _named(kind, name):
    for doc in _documents():
        if doc.get("kind") == kind and doc["metadata"]["name"] == name:
            return doc
    raise AssertionError(f"{kind}/{name} not found")


def _workload_containers(workload):
    spec = workload["spec"]["template"]["spec"]
    return list(spec.get("initContainers", [])) + list(spec.get("containers", []))


def kustomize_available():
    return shutil.which("kubectl") is not None


# ---------------------------------------------------------------------------
# Manifest validity
# ---------------------------------------------------------------------------

def test_all_manifests_parse_and_have_required_fields():
    docs = load_k8s_documents()
    assert len(docs) >= 20
    for relpath, doc in docs:
        assert isinstance(doc, dict), f"{relpath} did not parse to a mapping"
        assert "apiVersion" in doc, f"{relpath} missing apiVersion"
        assert "kind" in doc, f"{relpath} missing kind"
        if doc["kind"] == "Kustomization":
            # Kustomization files are build config, not cluster objects.
            continue
        assert "metadata" in doc, f"{relpath} missing metadata"
        assert doc["metadata"].get("name"), f"{relpath} missing metadata.name"


def test_kustomization_files_are_valid():
    for path in _iter_yaml_files():
        if os.path.basename(path) != "kustomization.yaml":
            continue
        with open(path, encoding="utf-8") as handle:
            doc = yaml.safe_load(handle)
        assert doc["apiVersion"] == "kustomize.config.k8s.io/v1beta1"
        assert doc["kind"] == "Kustomization"


def test_kustomization_resource_paths_exist():
    for path in _iter_yaml_files():
        if os.path.basename(path) != "kustomization.yaml":
            continue
        base = os.path.dirname(path)
        with open(path, encoding="utf-8") as handle:
            doc = yaml.safe_load(handle)
        for entry in doc.get("resources", []) or []:
            if entry.startswith("http://") or entry.startswith("https://"):
                continue
            assert os.path.exists(os.path.join(base, entry)), (
                f"{os.path.relpath(path, REPO_ROOT)} references missing resource {entry}"
            )


@pytest.mark.skipif(not kustomize_available(), reason="kubectl is not installed")
def test_kustomize_build_succeeds():
    result = subprocess.run(
        ["kubectl", "kustomize", K8S_DIR],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"kustomize failed:\n{result.stderr}"
    rendered = [d for d in yaml.safe_load_all(result.stdout) if d]
    assert len(rendered) >= 30
    ns = {d["metadata"].get("namespace") for d in rendered if d["kind"] != "Namespace"}
    assert ns == {NAMESPACE}


# ---------------------------------------------------------------------------
# Namespace and workload inventory
# ---------------------------------------------------------------------------

def test_dedicated_namespace_exists_and_others_are_cluster_scoped():
    namespace = _by_kind("Namespace")
    assert [n["metadata"]["name"] for n in namespace] == [NAMESPACE]


def test_every_namespaced_resource_uses_sentryops_namespace():
    for doc in _documents():
        if doc["kind"] in {"Namespace", "Kustomization"}:
            continue
        if doc.get("kind") == "CustomResourceDefinition":
            continue
        if "namespace" in doc.get("metadata", {}) or doc["kind"] in {
            "Deployment", "StatefulSet", "Service", "ConfigMap", "Secret"
        }:
            assert doc["metadata"].get("namespace") == NAMESPACE, (
                f"{doc['kind']}/{doc['metadata']['name']} is not in {NAMESPACE}"
            )


@pytest.mark.parametrize("name", [
    "postgres", "redis", "backend", "frontend",
    "api-gateway", "order-service", "payment-service",
    "notification-service", "user-service", "fault-injection",
    "prometheus", "loki", "jaeger", "grafana",
])
def test_expected_workload_exists(name):
    names = {w["metadata"]["name"] for w in _workloads()}
    assert name in names


def test_postgres_is_a_statefulset_and_others_are_deployments():
    assert _named("StatefulSet", "postgres")
    for name in ["redis", "backend", "frontend", "prometheus", "loki", "jaeger", "grafana"]:
        assert _named("Deployment", name)


# ---------------------------------------------------------------------------
# Services and discovery
# ---------------------------------------------------------------------------

EXPECTED_SERVICE_PORTS = {
    "postgres": 5432,
    "redis": 6379,
    "backend": 8000,
    "frontend": 80,
    "api-gateway": 8000,
    "order-service": 8001,
    "payment-service": 8002,
    "notification-service": 8003,
    "user-service": 8004,
    "fault-injection": 8005,
    "prometheus": 9090,
    "loki": 3100,
    "jaeger": 16686,
    "grafana": 3000,
}


@pytest.mark.parametrize("name,port", sorted(EXPECTED_SERVICE_PORTS.items()))
def test_service_exists_with_expected_port(name, port):
    service = _named("Service", name)
    ports = [p["port"] for p in service["spec"]["ports"]]
    assert port in ports, f"Service/{name} does not expose port {port} (has {ports})"


def test_service_selectors_match_a_workload():
    workloads = {
        w["metadata"]["name"]: w["spec"]["template"]["metadata"]["labels"]
        for w in _workloads()
    }
    for service in _by_kind("Service"):
        name = service["metadata"]["name"]
        selector = service["spec"]["selector"]
        assert name in workloads, f"Service/{name} has no matching workload"
        for key, value in selector.items():
            assert workloads[name].get(key) == value, (
                f"Service/{name} selector {key}={value} does not match its workload"
            )


def test_named_target_ports_resolve_to_container_ports():
    containers = {}
    for workload in _workloads():
        names = set()
        for container in _workload_containers(workload):
            for port in container.get("ports", []) or []:
                if port.get("name"):
                    names.add(port["name"])
        containers[workload["metadata"]["name"]] = names

    for service in _by_kind("Service"):
        name = service["metadata"]["name"]
        for port in service["spec"]["ports"]:
            target = port.get("targetPort")
            if isinstance(target, str):
                assert target in containers[name], (
                    f"Service/{name} targetPort '{target}' is not a container port on the workload"
                )


def test_only_frontend_is_externally_exposed():
    external = {
        s["metadata"]["name"]: s["spec"].get("type", "ClusterIP")
        for s in _by_kind("Service")
        if s["spec"].get("type", "ClusterIP") != "ClusterIP"
    }
    assert external == {"frontend": "NodePort"}
    frontend = _named("Service", "frontend")
    assert frontend["spec"]["ports"][0]["nodePort"] == 30080


# ---------------------------------------------------------------------------
# Configuration separation
# ---------------------------------------------------------------------------

def test_shared_configmap_holds_non_secret_infrastructure_values():
    config = _named("ConfigMap", "sentryops-config")["data"]
    assert config["POSTGRES_HOST"] == "postgres"
    assert config["POSTGRES_DB"] == "sentryops"
    assert config["POSTGRES_USER"] == "sentryops"
    assert config["REDIS_URL"].startswith("redis://redis")


def test_loki_url_differs_between_backend_and_microservices():
    """The push URL and the query base URL are genuinely different values."""
    backend = _named("ConfigMap", "backend-config")["data"]
    micro = _named("ConfigMap", "microservices-config")["data"]
    assert backend["LOKI_URL"] == "http://loki:3100"
    assert micro["LOKI_URL"] == "http://loki:3100/loki/api/v1/push"


def test_backend_config_maps_dependency_endpoints_to_service_names():
    backend = _named("ConfigMap", "backend-config")["data"]
    assert backend["PROMETHEUS_URL"] == "http://prometheus:9090"
    assert backend["JAEGER_URL"] == "http://jaeger:16686"
    assert backend["FAULT_API_URL"] == "http://fault-injection:8005"
    # Deterministic mock LLM by default: no external model calls required.
    assert backend["MOCK_LLM"] == "true"


def test_backend_deployment_consumes_configmap_and_secret():
    backend = _named("Deployment", "backend")
    container = _named("Deployment", "backend")["spec"]["template"]["spec"]["containers"][0]
    sources = container["envFrom"]
    refs = {list(item.keys())[0]: list(item.values())[0]["name"] for item in sources}
    assert refs["configMapRef"] in {"sentryops-config", "backend-config"}
    assert "sentryops-secrets" in [i["secretRef"]["name"] for i in sources if "secretRef" in i]
    assert backend


def test_secret_holds_database_credentials_and_nothing_real():
    secret = _named("Secret", "sentryops-secrets")
    assert secret["type"] == "Opaque"
    keys = set(secret["stringData"])
    assert keys == {"POSTGRES_PASSWORD", "DATABASE_URL"}
    assert "postgres" in secret["stringData"]["DATABASE_URL"]
    raw = open(os.path.join(K8S_DIR, "secret.yaml"), encoding="utf-8").read()
    assert "LOCAL DEVELOPMENT" in raw.upper()


def test_no_obvious_secret_material_is_committed():
    suspicious = [
        r"AKIA[0-9A-Z]{16}",           # AWS access key id
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
        r"ghp_[A-Za-z0-9]{20,}",       # GitHub token
        r"sk-[A-Za-z0-9]{20,}",        # generic API key
    ]
    for root, _dirs, files in os.walk(REPO_ROOT):
        if any(part in root for part in (".git", "node_modules", "__pycache__")):
            continue
        for name in files:
            if not name.endswith((".yaml", ".yml", ".sh", ".env", ".example")):
                continue
            path = os.path.join(root, name)
            text = open(path, encoding="utf-8", errors="ignore").read()
            for pattern in suspicious:
                assert not re.search(pattern, text), f"{path} looks like it contains a real secret"


# ---------------------------------------------------------------------------
# Probes, resources, rolling updates
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", [
    "backend", "frontend", "redis", "api-gateway", "order-service",
    "payment-service", "notification-service", "user-service", "fault-injection",
])
def test_workloads_have_readiness_and_liveness_probes(name):
    workload = _named("Deployment", name)
    container = workload["spec"]["template"]["spec"]["containers"][0]
    assert "readinessProbe" in container, f"{name} has no readinessProbe"
    assert "livenessProbe" in container, f"{name} has no livenessProbe"


def test_backend_probes_use_the_existing_health_endpoint():
    container = _named("Deployment", "backend")["spec"]["template"]["spec"]["containers"][0]
    assert container["readinessProbe"]["httpGet"]["path"] == "/health"
    assert container["livenessProbe"]["httpGet"]["path"] == "/health"
    # A startup probe is required because importing the LangGraph app is slow.
    assert container["startupProbe"]["httpGet"]["path"] == "/health"


def test_microservice_probes_use_the_existing_health_endpoint():
    for name in ["api-gateway", "order-service", "payment-service",
                 "notification-service", "user-service"]:
        container = _named("Deployment", name)["spec"]["template"]["spec"]["containers"][0]
        assert container["readinessProbe"]["httpGet"]["path"] == "/health"


def test_postgres_probes_use_pg_isready():
    container = _named("StatefulSet", "postgres")["spec"]["template"]["spec"]["containers"][0]
    for probe in ("readinessProbe", "livenessProbe"):
        command = " ".join(container[probe]["exec"]["command"])
        assert "pg_isready" in command


def test_fault_injection_uses_tcp_probe_since_it_has_no_health_route():
    container = _named("Deployment", "fault-injection")["spec"]["template"]["spec"]["containers"][0]
    assert "tcpSocket" in container["readinessProbe"]


def test_startup_dependencies_use_readiness_polling_not_blind_sleeps():
    """Compose `depends_on` is replaced by init containers that wait for readiness."""
    backend_init = _named("Deployment", "backend")["spec"]["template"]["spec"]["initContainers"]
    assert any("pg_isready" in " ".join(c["command"]) for c in backend_init)

    payment_init = _named("Deployment", "payment-service")["spec"]["template"]["spec"]["initContainers"]
    assert any("redis-cli" in " ".join(c["command"]) for c in payment_init)

    # A bare `sleep 30`-style delay must not appear anywhere.
    for workload in _workloads():
        for container in _workload_containers(workload):
            command = " ".join(container.get("command", []) or [])
            assert not re.search(r"^\s*sleep\s+\d+\s*$", command)
            assert "sleep 30" not in command


def test_all_containers_define_resource_requests_and_limits():
    for workload in _workloads():
        for container in _workload_containers(workload):
            resources = container.get("resources", {})
            assert "requests" in resources and "limits" in resources, (
                f"{workload['metadata']['name']}/{container['name']} lacks resources"
            )
            assert resources["requests"].get("cpu") and resources["requests"].get("memory")
            assert resources["limits"].get("cpu") and resources["limits"].get("memory")


def test_resource_requests_stay_laptop_sized():
    for workload in _workloads():
        for container in _workload_containers(workload):
            memory = container["resources"]["limits"]["memory"]
            # Every limit is expressed in Mi and stays under 1Gi.
            assert memory.endswith("Mi"), f"{container['name']} limit {memory} is not in Mi"
            assert int(memory[:-2]) <= 1024


def test_application_workloads_are_single_replica_but_scalable():
    for name in ["backend", "frontend", "redis", "api-gateway"]:
        assert _named("Deployment", name)["spec"]["replicas"] == 1


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def test_postgres_declares_a_persistent_volume_claim():
    statefulset = _named("StatefulSet", "postgres")
    claims = statefulset["spec"]["volumeClaimTemplates"]
    assert len(claims) == 1
    claim = claims[0]
    assert claim["metadata"]["name"] == "data"
    assert "ReadWriteOnce" in claim["spec"]["accessModes"]
    storage = claim["spec"]["resources"]["requests"]["storage"]
    assert storage.endswith("Gi") and int(storage[:-2]) >= 1
    # The claim is actually mounted into the database container.
    container = statefulset["spec"]["template"]["spec"]["containers"][0]
    mounts = {m["name"]: m["mountPath"] for m in container["volumeMounts"]}
    assert mounts["data"] == "/var/lib/postgresql/data"


def test_redis_does_not_get_persistent_storage():
    """Redis only holds disposable fault-injection state."""
    docs = _documents()
    assert not [d for d in docs if d["kind"] == "PersistentVolumeClaim"]
    for doc in docs:
        if doc["kind"] in WORKLOAD_KINDS and doc["metadata"]["name"] == "redis":
            volumes = doc["spec"]["template"]["spec"].get("volumes", []) or []
            assert all("persistentVolumeClaim" not in v for v in volumes)


# ---------------------------------------------------------------------------
# Security and the remediation safety boundary
# ---------------------------------------------------------------------------

def test_no_rbac_objects_are_created():
    kinds = {d["kind"] for d in _documents()}
    for forbidden in ("ClusterRole", "ClusterRoleBinding", "Role", "RoleBinding", "ServiceAccount"):
        assert forbidden not in kinds, f"Phase 13 should not create {forbidden}"


def test_no_cluster_admin_reference_anywhere():
    for path in _iter_yaml_files():
        text = open(path, encoding="utf-8").read()
        assert "cluster-admin" not in text


def test_application_pods_never_mount_a_service_account_token():
    """Without a token an AI agent has no path to the Kubernetes API."""
    for workload in _workloads():
        pod_spec = workload["spec"]["template"]["spec"]
        assert pod_spec.get("automountServiceAccountToken") is False, (
            f"{workload['metadata']['name']} can mount a service account token"
        )


def test_no_privileged_or_host_level_access():
    for workload in _workloads():
        for container in _workload_containers(workload):
            security = container.get("securityContext", {})
            assert security.get("privileged") is not True
        for volume in workload["spec"]["template"]["spec"].get("volumes", []) or []:
            assert "hostPath" not in volume
        assert workload["spec"]["template"]["spec"].get("hostNetwork") is not True


def test_remediation_allowlist_is_not_exposed_through_kubernetes():
    """Kubernetes is deployment infrastructure, not an AI execution path.

    Only executable content is inspected: no container command, argument or image
    may invoke kubectl or a Kubernetes client. Documentation comments in the
    manifests are allowed to mention kubectl for operator instructions.
    """
    forbidden = ("kubectl", "kubernetes", "kubeconfig", "k8s.io/client-go", "@kubernetes")
    for workload in _workloads():
        for container in _workload_containers(workload):
            executable = " ".join([
                container.get("image", ""),
                " ".join(container.get("command", []) or []),
                " ".join(container.get("args", []) or []),
            ]).lower()
            for token in forbidden:
                assert token not in executable, (
                    f"{workload['metadata']['name']}/{container['name']} invokes {token}"
                )


# ---------------------------------------------------------------------------
# Images
# ---------------------------------------------------------------------------

PUBLIC_OBSERVABILITY_IMAGES = {
    "prom/prometheus:latest",
    "grafana/loki:latest",
    "jaegertracing/all-in-one:latest",
    "grafana/grafana:latest",
}

LOCAL_IMAGES = {
    "backend": "sentryops/backend:local",
    "frontend": "sentryops/frontend:local",
    "api-gateway": "sentryops/api-gateway:local",
    "order-service": "sentryops/order-service:local",
    "payment-service": "sentryops/payment-service:local",
    "notification-service": "sentryops/notification-service:local",
    "user-service": "sentryops/user-service:local",
    "fault-injection": "sentryops/fault-injection:local",
    "postgres": "pgvector/pgvector:pg16",
    "redis": "redis:7-alpine",
    "prometheus": "prom/prometheus:latest",
    "loki": "grafana/loki:latest",
    "jaeger": "jaegertracing/all-in-one:latest",
    "grafana": "grafana/grafana:latest",
}


@pytest.mark.parametrize("workload_name,image", sorted(LOCAL_IMAGES.items()))
def test_workloads_use_expected_images(workload_name, image):
    workload = _named("StatefulSet", workload_name) if workload_name == "postgres" \
        else _named("Deployment", workload_name)
    container = workload["spec"]["template"]["spec"]["containers"][0]
    assert container["image"] == image


def test_no_external_registry_required_for_locally_built_images():
    for name, image in LOCAL_IMAGES.items():
        if image in PUBLIC_OBSERVABILITY_IMAGES or name in {"postgres", "redis"}:
            continue
        workload = _named("Deployment", name)
        container = workload["spec"]["template"]["spec"]["containers"][0]
        assert container["imagePullPolicy"] == "IfNotPresent"
        assert "/" not in image or image.startswith("sentryops/")


def test_observability_config_is_reused_rather_than_duplicated():
    """ConfigMaps are generated from the Compose config files, not copied into k8s/."""
    deploy_script = open(os.path.join(REPO_ROOT, "scripts", "k8s-deploy.sh"), encoding="utf-8").read()
    for referenced in [
        "observability/prometheus/prometheus.yml",
        "observability/loki/loki-config.yml",
        "observability/grafana/provisioning/datasources/datasources.yml",
        "observability/grafana/provisioning/dashboards/dashboards.yml",
        "observability/grafana/dashboards/observability.json",
    ]:
        assert referenced in deploy_script
        assert os.path.exists(os.path.join(REPO_ROOT, referenced))

    # The config files must not be duplicated inside k8s/.
    for path in _iter_yaml_files():
        text = open(path, encoding="utf-8").read()
        assert "chunks_directory" not in text      # loki-config.yml content
        assert "scrape_configs" not in text        # prometheus.yml content
