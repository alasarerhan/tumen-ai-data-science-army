from __future__ import annotations

"""CloudOps tools — Infrastructure as Code, Containerization, CI/CD (M16).

All tools are pure-Python code generators that require no external API calls.
They return a human-readable text summary **and** a structured artefact dict via
``response_format="content_and_artifact"``.

Available tools
---------------
IaC / Terraform
    scaffold_terraform_resource   Generate a Terraform resource block (HCL).
    list_terraform_providers      List common Terraform providers + descriptions.
    estimate_monthly_cost         Rough monthly cost lookup for common resource types.
    validate_hcl_syntax           Basic structural validation of an HCL string.

Containerization
    generate_dockerfile           Generate a Dockerfile for common languages/runtimes.
    generate_docker_compose_yaml  Generate a docker-compose.yml from a service list.
    generate_k8s_manifest         Generate a Kubernetes YAML manifest.

CI/CD
    generate_github_actions_workflow  Generate a GitHub Actions workflow YAML.
    generate_gitlab_ci_pipeline       Generate a .gitlab-ci.yml pipeline definition.
"""
import json  # noqa: E402, F401
import textwrap  # noqa: E402, F401
from decimal import ROUND_HALF_UP, Decimal  # noqa: E402, F401
from typing import Any, Dict, List, Tuple  # noqa: E402, F401

from langchain.tools import tool  # noqa: E402, F401

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _indent(text: str, spaces: int = 2) -> str:
    return textwrap.indent(text, " " * spaces)


# ===========================================================================
# IaC / Terraform tools
# ===========================================================================

# Catalogue used by scaffold + cost estimation
_TERRAFORM_PROVIDERS: Dict[str, str] = {
    "aws": "Amazon Web Services — EC2, S3, RDS, Lambda, EKS, …",
    "azurerm": "Microsoft Azure — VMs, Blob, AKS, Functions, …",
    "google": "Google Cloud Platform — GCE, GCS, GKE, Cloud Run, …",
    "kubernetes": "Kubernetes cluster resources (Deployments, Services, …)",
    "helm": "Helm chart releases on Kubernetes",
    "docker": "Docker container images and networks",
    "github": "GitHub repositories, teams, branch protection rules",
    "datadog": "Datadog monitors, dashboards, SLOs",
    "random": "Utility — random IDs, pets, UUIDs",
    "null": "Utility — triggers and local provisioners",
}

_RESOURCE_TEMPLATES: Dict[str, str] = {
    "aws_instance": """\
resource "aws_instance" "{name}" {{
  ami           = var.ami_id
  instance_type = "{size}"
  subnet_id     = var.subnet_id

  tags = {{
    Name        = "{name}"
    Environment = var.environment
    ManagedBy   = "terraform"
  }}
}}""",
    "aws_s3_bucket": """\
resource "aws_s3_bucket" "{name}" {{
  bucket = "{name}-${{var.environment}}"

  tags = {{
    Name        = "{name}"
    Environment = var.environment
    ManagedBy   = "terraform"
  }}
}}

resource "aws_s3_bucket_versioning" "{name}_versioning" {{
  bucket = aws_s3_bucket.{name}.id
  versioning_configuration {{
    status = "Enabled"
  }}
}}""",
    "aws_rds_instance": """\
resource "aws_db_instance" "{name}" {{
  identifier        = "{name}-${{var.environment}}"
  engine            = "postgres"
  engine_version    = "15.4"
  instance_class    = "db.{size}"
  allocated_storage = 20
  db_name           = replace("{name}", "-", "_")
  username          = var.db_username
  password          = var.db_password
  skip_final_snapshot = true

  tags = {{
    Name        = "{name}"
    Environment = var.environment
    ManagedBy   = "terraform"
  }}
}}""",
    "aws_lambda_function": """\
resource "aws_lambda_function" "{name}" {{
  function_name = "{name}-${{var.environment}}"
  runtime       = "python3.11"
  handler       = "handler.lambda_handler"
  role          = aws_iam_role.{name}_exec.arn
  filename      = "${{path.module}}/lambda.zip"

  environment {{
    variables = {{
      ENVIRONMENT = var.environment
    }}
  }}

  tags = {{
    Name        = "{name}"
    Environment = var.environment
    ManagedBy   = "terraform"
  }}
}}""",
    "google_compute_instance": """\
resource "google_compute_instance" "{name}" {{
  name         = "{name}-${{var.environment}}"
  machine_type = "{size}"
  zone         = "{region}-a"

  boot_disk {{
    initialize_params {{
      image = "debian-cloud/debian-12"
    }}
  }}

  network_interface {{
    network = "default"
    access_config {{}}
  }}

  labels = {{
    environment = var.environment
    managed_by  = "terraform"
  }}
}}""",
    "azurerm_virtual_machine": """\
resource "azurerm_linux_virtual_machine" "{name}" {{
  name                = "{name}-${{var.environment}}"
  resource_group_name = azurerm_resource_group.main.name
  location            = "{region}"
  size                = "{size}"

  admin_username      = var.admin_username

  network_interface_ids = [azurerm_network_interface.{name}.id]

  os_disk {{
    caching              = "ReadWrite"
    storage_account_type = "Standard_LRS"
  }}

  source_image_reference {{
    publisher = "Canonical"
    offer     = "0001-com-ubuntu-server-jammy"
    sku       = "22_04-lts"
    version   = "latest"
  }}

  tags = {{
    environment = var.environment
    managed_by  = "terraform"
  }}
}}""",
}

# Fallback generic template
_GENERIC_HCL_TEMPLATE = """\
resource "{resource_type}" "{name}" {{
  # TODO: configure {resource_type} attributes
  # Provider: {provider}
  # Region: {region}

  tags = {{
    Name        = "{name}"
    Environment = var.environment
    ManagedBy   = "terraform"
  }}
}}"""

# Monthly cost lookup table (USD, approximate) - using Decimal for monetary precision
_COST_TABLE: Dict[str, Dict[str, Decimal]] = {
    "aws_instance": {
        "micro": Decimal("8.50"),
        "small": Decimal("17.00"),
        "medium": Decimal("34.00"),
        "large": Decimal("68.00"),
        "xlarge": Decimal("136.00"),
    },
    "aws_s3_bucket": {
        "small": Decimal("2.50"),
        "medium": Decimal("10.00"),
        "large": Decimal("50.00"),
    },
    "aws_rds_instance": {
        "micro": Decimal("15.00"),
        "small": Decimal("30.00"),
        "medium": Decimal("60.00"),
        "large": Decimal("120.00"),
    },
    "aws_lambda_function": {
        "small": Decimal("0.50"),
        "medium": Decimal("2.00"),
        "large": Decimal("8.00"),
    },
    "google_compute_instance": {
        "micro": Decimal("7.00"),
        "small": Decimal("14.00"),
        "medium": Decimal("28.00"),
        "large": Decimal("56.00"),
    },
    "azurerm_virtual_machine": {
        "small": Decimal("20.00"),
        "medium": Decimal("40.00"),
        "large": Decimal("80.00"),
    },
}

_SIZE_MAP = {
    "micro": "t3.micro",
    "small": "t3.small",
    "medium": "t3.medium",
    "large": "t3.large",
    "xlarge": "t3.xlarge",
}


@tool(response_format="content_and_artifact")
def scaffold_terraform_resource(
    resource_type: str,
    name: str,
    provider: str = "aws",
    region: str = "us-east-1",
    size: str = "small",
) -> Tuple[str, Dict[str, Any]]:
    """Generate a Terraform HCL resource block for the requested resource type.

    Parameters
    ----------
    resource_type : str
        Terraform resource type, e.g. ``aws_instance``, ``aws_s3_bucket``,
        ``google_compute_instance``, ``azurerm_virtual_machine``.
    name : str
        Logical name for the resource (used as the Terraform resource label).
    provider : str
        Terraform provider, default ``"aws"``.
    region : str
        Cloud region, default ``"us-east-1"``.
    size : str
        Resource size hint: ``micro | small | medium | large | xlarge``.
    """
    instance_type = _SIZE_MAP.get(size, size)
    template = _RESOURCE_TEMPLATES.get(
        resource_type,
        _GENERIC_HCL_TEMPLATE,
    )
    hcl = template.format(
        resource_type=resource_type,
        name=name,
        provider=provider,
        region=region,
        size=instance_type,
    )

    text = (
        f"# Terraform resource: {resource_type}.{name}\n"
        f"# Provider: {provider}  |  Region: {region}  |  Size: {size}\n\n" + hcl
    )

    artifact: Dict[str, Any] = {
        "resource_type": resource_type,
        "name": name,
        "provider": provider,
        "region": region,
        "size": size,
        "hcl": hcl,
        "known_template": resource_type in _RESOURCE_TEMPLATES,
    }
    return text, artifact


@tool(response_format="content_and_artifact")
def list_terraform_providers() -> Tuple[str, Dict[str, Any]]:
    """List common Terraform providers with short descriptions.

    Returns a formatted catalogue of well-known providers and their use-cases.
    """
    lines = ["## Common Terraform Providers\n"]
    for name, desc in _TERRAFORM_PROVIDERS.items():
        lines.append(f"- **{name}**: {desc}")
    text = "\n".join(lines)
    artifact: Dict[str, Any] = {"providers": _TERRAFORM_PROVIDERS}
    return text, artifact


@tool(response_format="content_and_artifact")
def estimate_monthly_cost(
    resource_type: str,
    size: str = "small",
    region: str = "us-east-1",
) -> Tuple[str, Dict[str, Any]]:
    """Return an approximate monthly USD cost for a given Terraform resource type.

    Parameters
    ----------
    resource_type : str
        Terraform resource type, e.g. ``aws_instance``, ``aws_rds_instance``.
    size : str
        Resource size tier: ``micro | small | medium | large | xlarge``.
    region : str
        Cloud region (affects pricing in real providers; used as label here).

    Returns
    -------
    tuple
        (text_summary, artifact_dict) where artifact_dict contains the cost as
        a string to preserve Decimal precision for JSON serialization.
    """
    sizes = _COST_TABLE.get(resource_type, {})
    cost: Decimal | None = sizes.get(size) or sizes.get("small")

    if cost is None:
        text = (
            f"No built-in cost estimate for `{resource_type}` (size={size}). "
            "Consult cloud provider pricing pages."
        )
        artifact: Dict[str, Any] = {
            "resource_type": resource_type,
            "size": size,
            "region": region,
            "estimated_usd_monthly": None,
            "known": False,
        }
    else:
        # Format cost with proper decimal places for display
        cost_display = str(cost.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        text = (
            f"Approximate monthly cost for `{resource_type}` "
            f"(size={size}, region={region}): **~${cost_display} USD**\n\n"
            "⚠️  Estimate is based on a static lookup table; actual costs depend "
            "on usage, data transfer, and cloud provider pricing changes."
        )
        artifact = {
            "resource_type": resource_type,
            "size": size,
            "region": region,
            "estimated_usd_monthly": float(cost),
            "estimated_usd_monthly_decimal": str(cost),
            "known": True,
        }
    return text, artifact


@tool(response_format="content_and_artifact")
def validate_hcl_syntax(hcl: str) -> Tuple[str, Dict[str, Any]]:
    """Perform basic structural validation of a Terraform HCL string.

    Checks: balanced braces, presence of at least one ``resource`` block,
    no obvious syntax errors (unclosed strings, missing ``=``).

    Parameters
    ----------
    hcl : str
        HCL text to validate.
    """
    errors: List[str] = []
    warnings: List[str] = []

    # Brace balance
    depth = 0
    for ch in hcl:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        if depth < 0:
            errors.append("Unmatched closing brace `}` detected.")
            break
    if depth > 0:
        errors.append(f"Unclosed brace block: {depth} `{{` without matching `}}`.")

    # Basic keyword presence
    if (
        "resource" not in hcl
        and "data" not in hcl
        and "variable" not in hcl
        and "output" not in hcl
    ):
        warnings.append("No recognized top-level block (resource, data, variable, output) found.")

    # Unclosed string (odd number of double-quotes per line)
    for i, line in enumerate(hcl.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if stripped.count('"') % 2 != 0:
            errors.append(f'Line {i}: odd number of `"` — possible unclosed string.')

    valid = len(errors) == 0
    if valid:
        status_text = "✅ HCL syntax looks valid (basic structural check passed)."
        if warnings:
            status_text += "\n⚠️  Warnings:\n" + "\n".join(f"  - {w}" for w in warnings)
    else:
        status_text = "❌ HCL validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        if warnings:
            status_text += "\n⚠️  Warnings:\n" + "\n".join(f"  - {w}" for w in warnings)

    artifact: Dict[str, Any] = {
        "valid": valid,
        "errors": errors,
        "warnings": warnings,
        "brace_depth_final": depth,
    }
    return status_text, artifact


# ===========================================================================
# Containerization tools
# ===========================================================================

_DOCKERFILE_BASES: Dict[str, Dict[str, str]] = {
    "python": {
        "base": "python:{version}-slim",
        "install": "pip install --no-cache-dir -r requirements.txt",
        "start": "python app.py",
    },
    "node": {
        "base": "node:{version}-alpine",
        "install": "npm ci --omit=dev",
        "start": "node server.js",
    },
    "java": {
        "base": "eclipse-temurin:{version}-jre-alpine",
        "install": "# copy pre-built jar",
        "start": "java -jar app.jar",
    },
    "go": {
        "base": "golang:{version}-alpine AS builder",
        "install": "go build -o app .",
        "start": "./app",
    },
    "rust": {
        "base": "rust:{version}-slim AS builder",
        "install": "cargo build --release",
        "start": "./target/release/app",
    },
}


@tool(response_format="content_and_artifact")
def generate_dockerfile(
    language: str,
    version: str = "latest",
    port: int = 8000,
    app_dir: str = "/app",
    start_command: str = "",
) -> Tuple[str, Dict[str, Any]]:
    """Generate a production-ready Dockerfile for the specified language/runtime.

    Parameters
    ----------
    language : str
        Runtime language: ``python | node | java | go | rust``.
    version : str
        Runtime version tag, e.g. ``"3.11"``, ``"20"``, ``"21"``.
    port : int
        Port the application listens on (used in EXPOSE directive).
    app_dir : str
        Working directory inside the container.
    start_command : str
        Override the default start command.  Leave empty to use the default.
    """
    lang = language.lower()
    cfg = _DOCKERFILE_BASES.get(
        lang,
        {
            "base": f"{lang}:{version}",
            "install": f"# install {lang} dependencies",
            "start": "./entrypoint.sh",
        },
    )
    base_image = cfg["base"].format(version=version)
    install_cmd = cfg["install"]
    start_cmd = start_command or cfg["start"]

    if lang == "python":
        dockerfile = f"""\
FROM {base_image}

# Security: run as non-root
RUN useradd --create-home appuser
WORKDIR {app_dir}

# Install dependencies first (Docker layer caching)
COPY requirements.txt .
RUN {install_cmd}

COPY . .
RUN chown -R appuser:appuser {app_dir}
USER appuser

EXPOSE {port}
ENV PORT={port}

CMD ["{start_cmd.split()[0]}", {"" if len(start_cmd.split()) < 2 else '", "'.join(start_cmd.split()[1:])}"]
"""
    elif lang == "node":
        dockerfile = f"""\
FROM {base_image}

RUN addgroup -S appgroup && adduser -S appuser -G appgroup
WORKDIR {app_dir}

COPY package*.json .
RUN {install_cmd}

COPY . .
RUN chown -R appuser:appgroup {app_dir}
USER appuser

EXPOSE {port}
ENV PORT={port}

CMD ["node", "{start_cmd.replace("node ", "")}"]
"""
    else:
        dockerfile = f"""\
FROM {base_image}

WORKDIR {app_dir}
COPY . .

RUN {install_cmd}

EXPOSE {port}
CMD ["{start_cmd}"]
"""

    text = f"# Dockerfile — {language}:{version} | port {port}\n\n" + dockerfile

    artifact: Dict[str, Any] = {
        "language": language,
        "version": version,
        "port": port,
        "app_dir": app_dir,
        "base_image": base_image,
        "start_command": start_cmd,
        "dockerfile": dockerfile,
    }
    return text, artifact


@tool(response_format="content_and_artifact")
def generate_docker_compose_yaml(services_json: str) -> Tuple[str, Dict[str, Any]]:
    """Generate a docker-compose.yml from a JSON description of services.

    Parameters
    ----------
    services_json : str
        JSON-encoded list of service objects.  Each object may contain:
        ``name`` (required), ``image``, ``port``, ``env`` (dict),
        ``depends_on`` (list), ``volumes`` (list).

    Example input::

        '[{"name":"api","image":"myapp:latest","port":8000,"env":{"DEBUG":"false"}},
          {"name":"db","image":"postgres:15","port":5432}]'
    """
    try:
        services: List[Dict[str, Any]] = json.loads(services_json)
    except json.JSONDecodeError as exc:
        error_text = f"❌ Invalid JSON: {exc}"
        return error_text, {"valid": False, "error": str(exc)}

    lines = ["services:"]
    service_names: List[str] = []

    for svc in services:
        name = svc.get("name", "service")
        service_names.append(name)
        image = svc.get("image", f"{name}:latest")
        port = svc.get("port")
        env = svc.get("env", {})
        depends = svc.get("depends_on", [])
        volumes = svc.get("volumes", [])

        lines.append(f"  {name}:")
        lines.append(f"    image: {image}")

        if port:
            lines.append("    ports:")
            lines.append(f'      - "{port}:{port}"')

        if env:
            lines.append("    environment:")
            for k, v in env.items():
                lines.append(f"      {k}: {v!r}")

        if depends:
            lines.append("    depends_on:")
            for d in depends:
                lines.append(f"      - {d}")

        if volumes:
            lines.append("    volumes:")
            for vol in volumes:
                lines.append(f"      - {vol}")

        lines.append("")

    compose_yaml = "\n".join(lines)
    text = (
        f"# docker-compose.yml — {len(services)} service(s): {', '.join(service_names)}\n\n"
        + compose_yaml
    )

    artifact: Dict[str, Any] = {
        "service_count": len(services),
        "service_names": service_names,
        "compose_yaml": compose_yaml,
        "valid": True,
    }
    return text, artifact


_K8S_TEMPLATES: Dict[str, str] = {
    "Deployment": """\
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {name}
  namespace: {namespace}
  labels:
    app: {name}
spec:
  replicas: {replicas}
  selector:
    matchLabels:
      app: {name}
  template:
    metadata:
      labels:
        app: {name}
    spec:
      containers:
        - name: {name}
          image: {image}
          ports:
            - containerPort: {port}
          resources:
            requests:
              cpu: "100m"
              memory: "128Mi"
            limits:
              cpu: "500m"
              memory: "512Mi"
""",
    "Service": """\
apiVersion: v1
kind: Service
metadata:
  name: {name}
  namespace: {namespace}
spec:
  selector:
    app: {name}
  ports:
    - protocol: TCP
      port: 80
      targetPort: {port}
  type: ClusterIP
""",
    "ConfigMap": """\
apiVersion: v1
kind: ConfigMap
metadata:
  name: {name}
  namespace: {namespace}
data:
  # Add key-value configuration here
  APP_NAME: "{name}"
  LOG_LEVEL: "info"
""",
    "Namespace": """\
apiVersion: v1
kind: Namespace
metadata:
  name: {name}
  labels:
    managed-by: terraform
""",
}


@tool(response_format="content_and_artifact")
def generate_k8s_manifest(
    resource_kind: str,
    name: str,
    image: str = "nginx:latest",
    replicas: int = 1,
    port: int = 8080,
    namespace: str = "default",
) -> Tuple[str, Dict[str, Any]]:
    """Generate a Kubernetes YAML manifest.

    Parameters
    ----------
    resource_kind : str
        One of: ``Deployment``, ``Service``, ``ConfigMap``, ``Namespace``.
    name : str
        Kubernetes resource name (must be DNS-compatible).
    image : str
        Container image (used for Deployment resources).
    replicas : int
        Number of pod replicas (Deployment only).
    port : int
        Container/service port.
    namespace : str
        Kubernetes namespace, default ``"default"``.
    """
    template = _K8S_TEMPLATES.get(resource_kind)
    if template is None:
        known = list(_K8S_TEMPLATES.keys())
        text = f"❌ Unknown resource kind `{resource_kind}`. Supported: {', '.join(known)}"
        return text, {"valid": False, "resource_kind": resource_kind, "known_kinds": known}

    yaml_text = template.format(
        name=name,
        namespace=namespace,
        image=image,
        replicas=replicas,
        port=port,
    )
    text = f"# Kubernetes {resource_kind}: {name} (namespace: {namespace})\n\n" + yaml_text

    artifact: Dict[str, Any] = {
        "resource_kind": resource_kind,
        "name": name,
        "namespace": namespace,
        "image": image,
        "replicas": replicas,
        "port": port,
        "yaml": yaml_text,
        "valid": True,
    }
    return text, artifact


# ===========================================================================
# CI/CD tools
# ===========================================================================


@tool(response_format="content_and_artifact")
def generate_github_actions_workflow(
    trigger: str = "push",
    branches: str = "main",
    python_version: str = "3.11",
    test_command: str = "pytest tests/ -v",
    name: str = "CI",
) -> Tuple[str, Dict[str, Any]]:
    """Generate a GitHub Actions workflow YAML file.

    Parameters
    ----------
    trigger : str
        Event(s) to trigger the workflow: ``push | pull_request | push,pull_request``.
    branches : str
        Comma-separated branch names, e.g. ``"main,develop"``.
    python_version : str
        Python version to set up.
    test_command : str
        Command to run tests.
    name : str
        Workflow display name.
    """
    branch_list = [b.strip() for b in branches.split(",")]
    trigger_list = [t.strip() for t in trigger.split(",")]

    # Build on/push/branches block
    on_block_parts: List[str] = []
    for trig in trigger_list:
        if trig in ("push", "pull_request"):
            branch_yaml = "\n".join(f"      - {b}" for b in branch_list)
            on_block_parts.append(f"  {trig}:\n    branches:\n{branch_yaml}")
        else:
            on_block_parts.append(f"  {trig}:")

    on_block = "\n".join(on_block_parts)

    yaml_text = f"""\
name: {name}

on:
{on_block}

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python {python_version}
        uses: actions/setup-python@v5
        with:
          python-version: "{python_version}"
          cache: "pip"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Run tests
        run: {test_command}

      - name: Upload coverage report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: coverage-report
          path: htmlcov/
          if-no-files-found: ignore
"""

    text = f"# GitHub Actions: {name} workflow\n\n" + yaml_text

    artifact: Dict[str, Any] = {
        "workflow_name": name,
        "triggers": trigger_list,
        "branches": branch_list,
        "python_version": python_version,
        "test_command": test_command,
        "yaml": yaml_text,
    }
    return text, artifact


@tool(response_format="content_and_artifact")
def generate_gitlab_ci_pipeline(
    stages: str = "install,test,build",
    docker_image: str = "python:3.11-slim",
    test_command: str = "pytest tests/ -v",
    before_script: str = "pip install -r requirements.txt",
) -> Tuple[str, Dict[str, Any]]:
    """Generate a .gitlab-ci.yml pipeline definition.

    Parameters
    ----------
    stages : str
        Comma-separated stage names, e.g. ``"install,test,build,deploy"``.
    docker_image : str
        Default Docker image for all jobs.
    test_command : str
        Command used in the ``test`` stage job.
    before_script : str
        Shell command(s) run before every job.
    """
    stage_list = [s.strip() for s in stages.split(",")]
    stages_yaml = "\n".join(f"  - {s}" for s in stage_list)

    # Build jobs for each standard stage we recognise
    job_blocks: List[str] = []
    for stage in stage_list:
        if stage == "install":
            job_blocks.append("""\
install:dependencies:
  stage: install
  script:
    - pip install --upgrade pip
    - pip install -r requirements.txt
  artifacts:
    paths:
      - .venv/
    expire_in: 1 hour
""")
        elif stage == "test":
            job_blocks.append(f"""\
test:unit:
  stage: test
  script:
    - {test_command}
  coverage: '/TOTAL.*\\s+(\\d+%)$/'
  artifacts:
    reports:
      coverage_report:
        coverage_format: cobertura
        path: coverage.xml
""")
        elif stage == "build":
            job_blocks.append("""\
build:docker:
  stage: build
  image: docker:24
  services:
    - docker:24-dind
  script:
    - docker build -t $CI_REGISTRY_IMAGE:$CI_COMMIT_SHORT_SHA .
    - docker push $CI_REGISTRY_IMAGE:$CI_COMMIT_SHORT_SHA
  only:
    - main
""")
        elif stage == "deploy":
            job_blocks.append("""\
deploy:production:
  stage: deploy
  script:
    - echo "Deploy to production"
    - # Add your deployment commands here
  environment:
    name: production
  only:
    - main
  when: manual
""")
        else:
            job_blocks.append(f"""\
{stage}:job:
  stage: {stage}
  script:
    - echo "Running stage: {stage}"
""")

    yaml_text = f"""\
image: {docker_image}

stages:
{stages_yaml}

before_script:
  - {before_script}

{"".join(job_blocks)}"""

    text = f"# .gitlab-ci.yml — stages: {', '.join(stage_list)}\n\n" + yaml_text

    artifact: Dict[str, Any] = {
        "stages": stage_list,
        "docker_image": docker_image,
        "test_command": test_command,
        "yaml": yaml_text,
    }
    return text, artifact
