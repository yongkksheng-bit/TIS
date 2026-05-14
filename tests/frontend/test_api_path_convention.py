"""
Frontend API Path Convention Test.

Validates that all Vue/TS files calling apiClient use correct /api/ prefix
matching the backend router prefixes.

Convention:
- projects.py:  /api/projects/...
- rag.py:       /api/v1/projects/...
- evaluations.py: /api/v1/...
- pricing.py:   /api/v1/...
- formal_review.py: /api/v1/...

This test scans all .vue and .ts files in frontend/src/ for apiClient calls
and verifies the URL path starts with /api/ (matching nginx location /api/ proxy).
"""
import re
from pathlib import Path

import pytest


# Known backend router prefixes (from app/api/v1/endpoints/*.py)
VALID_PROJECT_PATHS = {
    "/api/projects",      # projects.py
}
VALID_V1_PATHS = {
    "/api/v1",           # evaluations, formal_review, pricing, review
    "/api/v1/projects",   # rag.py (prefix="/api/v1/projects")
}
VALID_DOCUMENT_PATHS = {
    "/api/document-images",  # served statically, not via router
}

# Routes that should NOT have /api prefix (external services)
EXTERNAL_PATHS = {
    "/ai_service",
    "/minio",
}


class TestFrontendApiPathConvention:
    """Scan all frontend source files for apiClient calls and validate paths."""

    @pytest.fixture
    def vue_and_ts_files(self):
        """Find all Vue and TypeScript source files."""
        src_dir = Path("frontend/src")
        files = []
        for pattern in ["**/*.vue", "**/*.ts"]:
            files.extend(src_dir.glob(pattern))
        # Exclude test files, type definition files, and node_modules
        files = [
            f for f in files
            if "/node_modules/" not in str(f)
            and not f.name.endswith(".d.ts")
            and not f.name.endswith(".test.ts")
            and not f.name.endswith(".spec.ts")
        ]
        return files

    def _extract_api_calls(self, content: str) -> list[tuple[str, str]]:
        """
        Extract all apiClient method calls from file content.
        Returns list of (http_method, url_path) tuples.
        """
        # Match: apiClient.get(`/some/path`), apiClient.post('/other/path'), etc.
        pattern = r"apiClient\.(get|post|put|delete|patch)\s*\(\s*[`'\"]([^`'\"]+)[`'\"]"
        matches = re.findall(pattern, content)
        return matches

    def _is_valid_path(self, _method: str, path: str) -> bool:
        """Check if API path has correct /api/ prefix.

        Args:
            _method: HTTP method (unused, reserved for future stricter validation).
            path: The URL path used in the apiClient call.
        """
        # Skip external URLs
        if path.startswith("http://") or path.startswith("https://"):
            return True

        # Skip external service paths
        for ext in EXTERNAL_PATHS:
            if path.startswith(ext):
                return True

        # Must start with /api/
        if not path.startswith("/api/"):
            return False

        # After /api/, the path must map to a known backend router
        # Each router prefix is a separate namespace
        remainder = path[4:]  # strip leading /api

        # /api/projects/* → projects.py (prefix=/api/projects)
        if remainder.startswith("/projects"):
            return any(path.startswith(v) for v in VALID_PROJECT_PATHS)

        # /api/v1/* → evaluations/pricing/formal_review/rag/review routers
        # These all share /api/v1 prefix but different sub-paths
        # Known sub-paths after /api/v1: /projects, /evaluations, /formal-review,
        #   /pricing, /review, /cost-estimates, /tech-proposal
        if remainder.startswith("/v1"):
            # Strip the /v1 prefix to get the subpath for matching
            v1_remainder = remainder[3:]  # strip /v1
            v1_subpaths = ("/projects", "/evaluations", "/formal-review",
                            "/pricing", "/review", "/cost-estimates", "/tech-proposal")
            return v1_remainder.startswith(v1_subpaths)

        # /api/document-images/* → static file serving
        if remainder.startswith("/document-images"):
            return True

        # Allow any path that has /api/ prefix and doesn't match above exclusions
        # This is a permissive fallback for future routers
        return True

    def test_all_api_calls_have_correct_prefix(self, vue_and_ts_files):
        """
        Every apiClient call must use /api/ prefix to match nginx routing.

        nginx config:
            location /api/ { proxy_pass http://backend:8000$request_uri; }

        Without /api/, requests hit 'location /' (SPA catch-all) and return
        HTML instead of being proxied to FastAPI.
        """
        violations = []

        for file_path in vue_and_ts_files:
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            calls = self._extract_api_calls(content)
            for method, path in calls:
                if not self._is_valid_path(method, path):
                    rel_path = str(file_path).replace("\\", "/")
                    violations.append({
                        "file": rel_path,
                        "method": method,
                        "path": path,
                    })

        if violations:
            msg = "\n".join(
                f"  {v['file']}: apiClient.{v['method']}('{v['path']}') - missing /api/ prefix"
                for v in violations
            )
            pytest.fail(f"API path convention violations:\n{msg}")

    def test_confirmation_view_has_api_prefix(self):
        """
        Specific test for ConfirmationView.vue - confirms the fix for the
        critical bug discovered in the 2026-05-14 audit.

        Before fix:
          - apiClient.get(`/projects/${projectId}/confirmation-data`)
          - apiClient.post(`/projects/${projectId}/confirm-parsing`)

        After fix:
          - apiClient.get(`/api/projects/${projectId}/confirmation-data`)
          - apiClient.post(`/api/projects/${projectId}/confirm-parsing`)
        """
        file_path = Path("frontend/src/views/ConfirmationView.vue")
        content = file_path.read_text(encoding="utf-8")
        calls = self._extract_api_calls(content)

        # Find the two confirmation-data and confirm-parsing calls
        confirmation_calls = [
            (m, p) for m, p in calls
            if "confirmation-data" in p or "confirm-parsing" in p
        ]

        assert len(confirmation_calls) >= 2, (
            f"Expected at least 2 confirmation-related API calls, "
            f"found {len(confirmation_calls)}"
        )

        for method, path in confirmation_calls:
            assert path.startswith("/api/"), (
                f"ConfirmationView.vue: apiClient.{method}('{path}') "
                f"is missing /api/ prefix. "
                f"Expected: /api/projects/..., Got: /projects/..."
            )
