"""Tests for Docker deployment readiness."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_dockerfile_exists_and_valid():
    dockerfile = PROJECT_ROOT / "Dockerfile"
    assert dockerfile.exists(), "Dockerfile not found"

    content = dockerfile.read_text(encoding="utf-8")
    assert "FROM python" in content, "Dockerfile must use a Python base image"
    assert "EXPOSE" in content, "Dockerfile must EXPOSE a port"
    assert "uvicorn" in content, "Dockerfile must run uvicorn"


def test_compose_has_app_service():
    compose_file = PROJECT_ROOT / "docker-compose.yml"
    assert compose_file.exists()

    with compose_file.open(encoding="utf-8") as f:
        config = yaml.safe_load(f)

    services = config.get("services", {})
    assert "app" in services, "docker-compose.yml must have an 'app' service"

    app_svc = services["app"]
    deps = app_svc.get("depends_on", {})
    assert "langfuse" in deps or "langfuse" in str(deps), "app must depend on langfuse"

    ports = app_svc.get("ports", [])
    assert any("8000" in str(p) for p in ports), "app must expose port 8000"


def test_healthcheck_script_returns_status():
    from scripts.healthcheck import check_health

    with patch("scripts.healthcheck.httpx") as mock_httpx:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok"}
        mock_httpx.get.return_value = mock_response

        result = check_health("http://localhost:8000")

    assert result == 0


def test_healthcheck_script_returns_failure():
    from scripts.healthcheck import check_health

    with patch("scripts.healthcheck.httpx") as mock_httpx:
        mock_httpx.get.side_effect = Exception("Connection refused")

        result = check_health("http://localhost:8000")

    assert result == 1
