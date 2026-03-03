"""Tests for feedback API endpoints."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from rossum_agent.api.main import app

from .conftest import create_mock_httpx_client


@pytest.fixture
def client(mock_chat_service, mock_agent_service, mock_file_service):
    app.state.chat_service = mock_chat_service
    app.state.agent_service = mock_agent_service
    app.state.file_service = mock_file_service

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


class TestSubmitFeedback:
    """Tests for PUT /api/v1/chats/{chat_id}/feedback endpoint."""

    @patch("rossum_agent.api.dependencies.httpx.AsyncClient")
    def test_submit_feedback_success(self, mock_httpx, client, mock_chat_service, valid_headers):
        mock_httpx.return_value = create_mock_httpx_client()
        mock_chat_service.chat_exists.return_value = True
        mock_chat_service.save_feedback.return_value = True

        response = client.put(
            "/api/v1/chats/chat_123/feedback",
            headers=valid_headers,
            json={"turn_index": 0, "is_positive": True},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["turn_index"] == 0
        assert data["is_positive"] is True
        mock_chat_service.save_feedback.assert_called_once_with("12345", "chat_123", 0, True)

    @patch("rossum_agent.api.dependencies.httpx.AsyncClient")
    def test_submit_negative_feedback(self, mock_httpx, client, mock_chat_service, valid_headers):
        mock_httpx.return_value = create_mock_httpx_client()
        mock_chat_service.chat_exists.return_value = True
        mock_chat_service.save_feedback.return_value = True

        response = client.put(
            "/api/v1/chats/chat_123/feedback",
            headers=valid_headers,
            json={"turn_index": 2, "is_positive": False},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["turn_index"] == 2
        assert data["is_positive"] is False

    @patch("rossum_agent.api.dependencies.httpx.AsyncClient")
    def test_submit_feedback_chat_not_found(self, mock_httpx, client, mock_chat_service, valid_headers):
        mock_httpx.return_value = create_mock_httpx_client()
        mock_chat_service.chat_exists.return_value = False

        response = client.put(
            "/api/v1/chats/chat_missing/feedback",
            headers=valid_headers,
            json={"turn_index": 0, "is_positive": True},
        )

        assert response.status_code == 404

    @patch("rossum_agent.api.dependencies.httpx.AsyncClient")
    def test_submit_feedback_negative_turn_index(self, mock_httpx, client, mock_chat_service, valid_headers):
        mock_httpx.return_value = create_mock_httpx_client()
        mock_chat_service.chat_exists.return_value = True

        response = client.put(
            "/api/v1/chats/chat_123/feedback",
            headers=valid_headers,
            json={"turn_index": -1, "is_positive": True},
        )

        assert response.status_code == 422

    def test_submit_feedback_missing_auth(self, client):
        response = client.put(
            "/api/v1/chats/chat_123/feedback",
            headers={"X-Rossum-Api-Url": "https://api.rossum.ai"},
            json={"turn_index": 0, "is_positive": True},
        )

        assert response.status_code == 422


class TestGetFeedback:
    """Tests for GET /api/v1/chats/{chat_id}/feedback endpoint."""

    @patch("rossum_agent.api.dependencies.httpx.AsyncClient")
    def test_get_feedback_success(self, mock_httpx, client, mock_chat_service, valid_headers):
        mock_httpx.return_value = create_mock_httpx_client()
        mock_chat_service.chat_exists.return_value = True
        mock_chat_service.get_feedback.return_value = {0: True, 2: False}

        response = client.get("/api/v1/chats/chat_123/feedback", headers=valid_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["feedback"] == {"0": True, "2": False}

    @patch("rossum_agent.api.dependencies.httpx.AsyncClient")
    def test_get_feedback_empty(self, mock_httpx, client, mock_chat_service, valid_headers):
        mock_httpx.return_value = create_mock_httpx_client()
        mock_chat_service.chat_exists.return_value = True
        mock_chat_service.get_feedback.return_value = {}

        response = client.get("/api/v1/chats/chat_123/feedback", headers=valid_headers)

        assert response.status_code == 200
        assert response.json() == {"feedback": {}}

    @patch("rossum_agent.api.dependencies.httpx.AsyncClient")
    def test_get_feedback_chat_not_found(self, mock_httpx, client, mock_chat_service, valid_headers):
        mock_httpx.return_value = create_mock_httpx_client()
        mock_chat_service.chat_exists.return_value = False

        response = client.get("/api/v1/chats/chat_missing/feedback", headers=valid_headers)

        assert response.status_code == 404


class TestDeleteFeedback:
    """Tests for DELETE /api/v1/chats/{chat_id}/feedback/{turn_index} endpoint."""

    @patch("rossum_agent.api.dependencies.httpx.AsyncClient")
    def test_delete_feedback_success(self, mock_httpx, client, mock_chat_service, valid_headers):
        mock_httpx.return_value = create_mock_httpx_client()
        mock_chat_service.chat_exists.return_value = True
        mock_chat_service.delete_feedback.return_value = True

        response = client.delete("/api/v1/chats/chat_123/feedback/0", headers=valid_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] is True
        mock_chat_service.delete_feedback.assert_called_once_with("12345", "chat_123", 0)

    @patch("rossum_agent.api.dependencies.httpx.AsyncClient")
    def test_delete_feedback_not_found(self, mock_httpx, client, mock_chat_service, valid_headers):
        mock_httpx.return_value = create_mock_httpx_client()
        mock_chat_service.chat_exists.return_value = True
        mock_chat_service.delete_feedback.return_value = False

        response = client.delete("/api/v1/chats/chat_123/feedback/5", headers=valid_headers)

        assert response.status_code == 200
        assert response.json()["deleted"] is False

    @patch("rossum_agent.api.dependencies.httpx.AsyncClient")
    def test_delete_feedback_chat_not_found(self, mock_httpx, client, mock_chat_service, valid_headers):
        mock_httpx.return_value = create_mock_httpx_client()
        mock_chat_service.chat_exists.return_value = False

        response = client.delete("/api/v1/chats/chat_missing/feedback/0", headers=valid_headers)

        assert response.status_code == 404
