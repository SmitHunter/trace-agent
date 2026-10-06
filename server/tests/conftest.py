"""Test defaults: in-process MCP so unit tests do not spawn a stdio child."""

import os

os.environ.setdefault("MCP_TRANSPORT", "inprocess")
os.environ.setdefault("DEMO_MODE", "true")
