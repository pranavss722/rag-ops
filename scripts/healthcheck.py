"""Docker healthcheck script — hits /health and returns exit code."""

import sys

import httpx


def check_health(url: str = "http://localhost:8000") -> int:
    """Check the health endpoint. Returns 0 on success, 1 on failure."""
    try:
        resp = httpx.get(f"{url}/health", timeout=5)
        if resp.status_code == 200 and resp.json().get("status") == "ok":
            return 0
    except Exception:
        pass
    return 1


if __name__ == "__main__":
    sys.exit(check_health())
