import base64
import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


READ_ONLY_FIELDS = {
    "id",
    "created_at",
    "updated_at",
    "intern_name",
    "project_name",
    "dependencies",
    "ai_usage",
    "review_comments",
    "is_on_hold",
    "is_overdue",
}


class InternMateApiError(RuntimeError):
    pass


class InternMateApiClient:
    def __init__(self):
        base_url = os.getenv("INTERNMATE_BASE_URL", "http://127.0.0.1:8001").strip()
        self.base_url = base_url.rstrip("/")

        self.username = os.getenv("INTERNMATE_API_USERNAME", "").strip()
        self.password = os.getenv("INTERNMATE_API_PASSWORD", "").strip()
        if not self.username or not self.password:
            raise InternMateApiError(
                "INTERNMATE_API_USERNAME and INTERNMATE_API_PASSWORD must be set for MCP API access."
            )

    def _auth_header(self) -> str:
        encoded = base64.b64encode(f"{self.username}:{self.password}".encode("utf-8")).decode("utf-8")
        return f"Basic {encoded}"

    def _request(self, method: str, path: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        payload = None
        headers = {
            "Accept": "application/json",
            "Authorization": self._auth_header(),
        }

        if data is not None:
            payload = json.dumps(data).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = Request(url=url, data=payload, method=method.upper(), headers=headers)
        try:
            with urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8")
                if not raw:
                    return {}
                return json.loads(raw)
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise InternMateApiError(f"HTTP {exc.code} for {method} {path}: {body}") from exc
        except URLError as exc:
            raise InternMateApiError(
                f"Could not connect to InternMate API at {self.base_url}. Ensure the FastAPI backend is running."
            ) from exc

    def list_daily_logs(
        self,
        page: int = 1,
        intern_id: int | None = None,
        project_id: int | None = None,
        workflow_state: str | None = None,
        blocked: bool | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"page": page}
        if intern_id is not None:
            params["intern_profile"] = intern_id
        if project_id is not None:
            params["project"] = project_id
        if workflow_state:
            params["workflow_state"] = workflow_state
        if blocked is not None:
            params["blocker_flag"] = str(blocked).lower()
        return self._request("GET", f"/api/daily-logs/?{urlencode(params)}")

    def get_daily_log(self, entry_id: int) -> dict[str, Any]:
        return self._request("GET", f"/api/daily-logs/{entry_id}/")

    def update_daily_log(self, entry_id: int, updates: dict[str, Any]) -> dict[str, Any]:
        current = self.get_daily_log(entry_id)
        payload = {k: v for k, v in current.items() if k not in READ_ONLY_FIELDS}
        payload.update(updates)
        return self._request("PUT", f"/api/daily-logs/{entry_id}/", payload)

    def list_interns(self, page: int = 1) -> dict[str, Any]:
        return self._request("GET", f"/api/interns/?{urlencode({'page': page})}")

    def list_projects(self, page: int = 1) -> dict[str, Any]:
        return self._request("GET", f"/api/projects/?{urlencode({'page': page})}")

