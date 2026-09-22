# InternMate MCP Server (HTTP Transport)

This MCP server exposes InternMate tools with the required naming convention:

- `InternMate_get_daily_logs`
- `InternMate_get_task`
- `InternMate_list_interns`
- `InternMate_list_projects`

## 1) Install dependencies

```bash
. .venv/bin/activate
pip install -r requirements.txt
```

## 2) Required environment variables

```bash
export INTERNMATE_BASE_URL="http://127.0.0.1:8011"
export INTERNMATE_API_USERNAME="read_only_account"
export INTERNMATE_API_PASSWORD="pass1234"
export MCP_API_TOKEN="use-a-long-random-secret"
```

## 3) Run InternMate FastAPI app

```bash
.venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8011
```

## 4) Use the same InternMate port

With `MCP_API_TOKEN` present in the InternMate service environment, FastAPI mounts
the read-only MCP endpoint at `http://127.0.0.1:8011/mcp`. Do **not** run the
standalone server on port 9001 for the embedded deployment.

## 5) Codex CLI MCP config example

Add a server entry in your Codex CLI MCP config:

```json
{
  "mcpServers": {
    "InternMate_HTTP_MCP_Server": {
      "transport": {
        "type": "http",
        "url": "http://127.0.0.1:8011/mcp",
        "headers": {
          "Authorization": "Bearer YOUR_MCP_API_TOKEN"
        }
      }
    }
  }
}
```

Restart Codex CLI after editing config.

## Notes

- This server is read-only. Website users perform create, update, and delete actions through the role-protected InternMate assistant UI.
- Keep credentials scoped to a read-only InternMate account.
- The mounted `/mcp` endpoint rejects requests without its separate bearer token.
