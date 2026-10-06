"""Tests for the FastAPI application."""

import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


class TestHealthEndpoint:
    def test_health_check(self, client):
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "demo_mode" in data
        assert "timestamp" in data


class TestChatEndpoint:
    def test_chat_without_session(self, client):
        response = client.post("/chat", json={"message": "What's the weather in Sydney?"})

        assert response.status_code == 200
        data = response.json()
        assert "response" in data
        assert "session_id" in data
        assert "trace" in data
        assert "tool_results" in data
        assert "demo_mode" in data
        mcp_events = [event for event in data["trace"] if event["content"].startswith("MCP tools/")]
        assert mcp_events
        assert any(event["metadata"].get("protocol") == "mcp" for event in mcp_events)

    def test_chat_with_session(self, client):
        response1 = client.post("/chat", json={"message": "Hello"})
        session_id = response1.json()["session_id"]

        response2 = client.post(
            "/chat", json={"message": "What's the weather?", "session_id": session_id}
        )

        assert response2.status_code == 200
        assert response2.json()["session_id"] == session_id

    def test_chat_empty_message(self, client):
        response = client.post("/chat", json={"message": ""})

        assert response.status_code == 422


class TestSessionEndpoints:
    def test_create_session(self, client):
        response = client.post("/sessions")

        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert "message_count" in data
        assert data["message_count"] == 0

    def test_get_session(self, client):
        create_response = client.post("/sessions")
        session_id = create_response.json()["session_id"]

        response = client.get(f"/sessions/{session_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == session_id

    def test_get_nonexistent_session(self, client):
        response = client.get("/sessions/nonexistent-id")

        assert response.status_code == 404

    def test_delete_session(self, client):
        create_response = client.post("/sessions")
        session_id = create_response.json()["session_id"]

        response = client.delete(f"/sessions/{session_id}")

        assert response.status_code == 200
        assert response.json()["status"] == "deleted"

        get_response = client.get(f"/sessions/{session_id}")
        assert get_response.status_code == 404

    def test_get_session_history(self, client):
        response1 = client.post("/chat", json={"message": "Hello"})
        session_id = response1.json()["session_id"]

        response = client.get(f"/sessions/{session_id}/history")

        assert response.status_code == 200
        data = response.json()
        assert "messages" in data
        assert "trace" in data
        assert "tool_results" in data
        assert len(data["messages"]) >= 2  # At least user + assistant


class TestCORSHeaders:
    def test_cors_headers_on_get(self, client):
        response = client.get("/health", headers={"Origin": "http://localhost:3000"})

        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers
