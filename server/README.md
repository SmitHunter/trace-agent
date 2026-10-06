# Trace Agent server

Python package for the weather MCP server, agent loop, and FastAPI app.

The API process is an MCP client. It discovers tools with `list_tools` and
invokes them with `call_tool`. Default transport is stdio
(`python3 -m mcp_server.server`). Pytest sets `MCP_TRANSPORT=inprocess`.

```bash
python3 -m pip install -e ".[dev]"
DEMO_MODE=true python3 -m uvicorn api.main:app --host 0.0.0.0 --port 8742
python3 -m mcp_server.server
python3 -m pytest -v
python3 -m ruff check .
```
