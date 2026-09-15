import argparse
from typing import Any

from mcp.server.fastmcp import FastMCP

from .internmate_client import InternMateApiClient, InternMateApiError

mcp = FastMCP("InternMate_HTTP_MCP_Server")


def _client() -> InternMateApiClient:
    return InternMateApiClient()


@mcp.tool(name="InternMate_get_daily_logs")
def internmate_get_daily_logs(
    page: int = 1,
    intern_id: int | None = None,
    project_id: int | None = None,
    workflow_state: str | None = None,
    blocked: bool | None = None,
) -> dict[str, Any]:
    """Get paginated daily log entries from InternMate."""
    try:
        return _client().list_daily_logs(
            page=page,
            intern_id=intern_id,
            project_id=project_id,
            workflow_state=workflow_state,
            blocked=blocked,
        )
    except InternMateApiError as exc:
        return {"error": str(exc)}


@mcp.tool(name="InternMate_get_task")
def internmate_get_task(task_id: int) -> dict[str, Any]:
    """Get one task (daily log entry) by id."""
    try:
        return _client().get_daily_log(task_id)
    except InternMateApiError as exc:
        return {"error": str(exc)}


@mcp.tool(name="InternMate_update_task")
def internmate_update_task(task_id: int, updates: dict[str, Any]) -> dict[str, Any]:
    """Update one task by id. updates must contain writable daily-log fields only."""
    if not updates:
        return {"error": "updates payload is required"}
    try:
        return _client().update_daily_log(task_id, updates)
    except InternMateApiError as exc:
        return {"error": str(exc)}


@mcp.tool(name="InternMate_list_interns")
def internmate_list_interns(page: int = 1) -> dict[str, Any]:
    """List intern profiles."""
    try:
        return _client().list_interns(page=page)
    except InternMateApiError as exc:
        return {"error": str(exc)}


@mcp.tool(name="InternMate_list_projects")
def internmate_list_projects(page: int = 1) -> dict[str, Any]:
    """List projects."""
    try:
        return _client().list_projects(page=page)
    except InternMateApiError as exc:
        return {"error": str(exc)}


def _run_streamable_http(host: str, port: int, path: str):
    # mcp>=1.27.0 reads host/port/path from FastMCP settings.
    mcp.settings.host = host
    mcp.settings.port = port
    mcp.settings.streamable_http_path = path
    mcp.run(transport="streamable-http")


def main():
    parser = argparse.ArgumentParser(description="InternMate MCP server")
    parser.add_argument("--transport", choices=["http", "stdio"], default="http")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9001)
    parser.add_argument("--path", default="/mcp")
    args = parser.parse_args()

    if args.transport == "stdio":
        mcp.run(transport="stdio")
        return

    _run_streamable_http(args.host, args.port, args.path)


if __name__ == "__main__":
    main()
