# tests/week1/test_integration_upload_flow.py
import pytest
import subprocess
import time
import requests
import os


@pytest.mark.integration
def test_docker_compose_health():
    """Verify all services start via docker-compose and /health returns 200."""
    compose_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    compose_file = os.path.join(compose_dir, 'docker-compose.yml')

    # Bring down any existing containers
    subprocess.run(
        ['docker-compose', '-f', compose_file, 'down', '--volumes'],
        cwd=compose_dir,
        capture_output=True
    )

    # Build and start
    result = subprocess.run(
        ['docker-compose', '-f', compose_file, 'up', '-d', '--build'],
        cwd=compose_dir,
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        pytest.fail(f"docker-compose up failed: {result.stderr}")

    # Wait for app to be ready (max 60s)
    max_wait = 60
    for i in range(max_wait):
        try:
            r = requests.get('http://localhost:8000/health', timeout=2)
            if r.status_code == 200:
                break
        except Exception:
            pass
        time.sleep(1)
    else:
        subprocess.run(['docker-compose', '-f', compose_file, 'down'], cwd=compose_dir)
        pytest.fail("App did not become healthy within 60 seconds")

    # Verify health endpoint
    r = requests.get('http://localhost:8000/health')
    assert r.status_code == 200, f"Health check failed: {r.text}"

    # Cleanup
    subprocess.run(
        ['docker-compose', '-f', compose_file, 'down', '--volumes'],
        cwd=compose_dir
    )
