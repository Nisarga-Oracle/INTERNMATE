# InternMate MCP Server (HTTP Transport)

This MCP server exposes InternMate tools with the required naming convention:

- `InternMate_get_daily_logs`
- `InternMate_get_task`
- `InternMate_update_task`
- `InternMate_list_interns`
- `InternMate_list_projects`

## 1) Install dependencies

```bash
. .venv/bin/activate
pip install -r requirements.txt
```

## 2) Required environment variables

```bash
export INTERNMATE_BASE_URL="http://127.0.0.1:8001"
export INTERNMATE_API_USERNAME="manager"      # or other role account
export INTERNMATE_API_PASSWORD="pass1234"
```

## 3) Run InternMate FastAPI app

```bash
.venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8001
```

## 4) Run MCP server with HTTP transport

```bash
.venv/bin/python -m mcp_server.server --transport http --host 127.0.0.1 --port 9001 --path /mcp
```

## 5) Codex CLI MCP config example

Add a server entry in your Codex CLI MCP config:

```json
{
  "mcpServers": {
    "InternMate_HTTP_MCP_Server": {
      "transport": {
        "type": "http",
        "url": "http://127.0.0.1:9001/mcp"
      }
    }
  }
}
```

Restart Codex CLI after editing config.

## Notes

- This server calls InternMate REST APIs using Basic Auth to avoid CSRF/session automation complexity in local development.
- Keep credentials scoped to non-admin where possible.
- No delete tools are implemented in this version.

