"""Tests for rossum_agent.bedrock_client module."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest
from rossum_agent.bedrock_client import (
    HAIKU_MODEL_ID,
    OPUS_MODEL_ID,
    create_bedrock_client,
    get_model_id,
    get_small_model_id,
)


@pytest.fixture
def mock_credentials():
    credentials = MagicMock()
    frozen = MagicMock()
    frozen.access_key = "key"
    frozen.secret_key = "secret"
    frozen.token = None
    credentials.get_frozen_credentials.return_value = frozen
    return credentials


class TestCreateBedrockClient:
    def test_creates_client_with_explicit_session(self):
        mock_creds = MagicMock()
        mock_creds.access_key = "test_access_key"
        mock_creds.secret_key = "test_secret_key"
        mock_creds.token = "test_token"

        mock_frozen = MagicMock()
        mock_frozen.access_key = "test_access_key"
        mock_frozen.secret_key = "test_secret_key"
        mock_frozen.token = "test_token"
        mock_creds.get_frozen_credentials.return_value = mock_frozen

        mock_session = MagicMock()
        mock_session.get_credentials.return_value = mock_creds
        mock_session.region_name = "us-west-2"

        with patch("rossum_agent.bedrock_client.AnthropicBedrock") as mock_anthropic:
            create_bedrock_client(session=mock_session)

            mock_anthropic.assert_called_once_with(
                aws_access_key="test_access_key",
                aws_secret_key="test_secret_key",
                aws_session_token="test_token",
                aws_region="us-west-2",
                max_retries=5,
            )

    def test_creates_client_with_profile_name(self, mock_credentials):
        with (
            patch("rossum_agent.bedrock_client.boto3.Session") as mock_session_class,
            patch("rossum_agent.bedrock_client.AnthropicBedrock") as mock_anthropic,
        ):
            mock_session = MagicMock()
            mock_session.get_credentials.return_value = mock_credentials
            mock_session.region_name = "eu-central-1"
            mock_session_class.return_value = mock_session

            create_bedrock_client(aws_profile="my-profile", aws_region="eu-central-1")

            mock_session_class.assert_called_once_with(
                profile_name="my-profile",
                region_name="eu-central-1",
            )
            mock_anthropic.assert_called_once()

    def test_uses_default_region_from_environment(self, mock_credentials):
        with (
            patch.dict(os.environ, {"AWS_REGION": "ap-southeast-1"}),
            patch("rossum_agent.bedrock_client.boto3.Session") as mock_session_class,
            patch("rossum_agent.bedrock_client.AnthropicBedrock"),
        ):
            mock_session = MagicMock()
            mock_session.get_credentials.return_value = mock_credentials
            mock_session.region_name = "ap-southeast-1"
            mock_session_class.return_value = mock_session

            create_bedrock_client()

            mock_session_class.assert_called_once_with(
                profile_name=None,
                region_name="ap-southeast-1",
            )

    def test_uses_none_region_when_no_env_var(self, mock_credentials):
        with (
            patch.dict(os.environ, {}, clear=True),
            patch("rossum_agent.bedrock_client.boto3.Session") as mock_session_class,
            patch("rossum_agent.bedrock_client.AnthropicBedrock"),
        ):
            mock_session = MagicMock()
            mock_session.get_credentials.return_value = mock_credentials
            mock_session.region_name = None
            mock_session_class.return_value = mock_session

            create_bedrock_client()

            mock_session_class.assert_called_once_with(
                profile_name=None,
                region_name=None,
            )

    def test_raises_error_when_no_credentials_found(self):
        with patch("rossum_agent.bedrock_client.boto3.Session") as mock_session_class:
            mock_session = MagicMock()
            mock_session.get_credentials.return_value = None
            mock_session_class.return_value = mock_session

            with pytest.raises(RuntimeError, match="No AWS credentials found"):
                create_bedrock_client()

    def test_explicit_region_overrides_environment(self, mock_credentials):
        with (
            patch.dict(os.environ, {"AWS_REGION": "ap-southeast-1"}),
            patch("rossum_agent.bedrock_client.boto3.Session") as mock_session_class,
            patch("rossum_agent.bedrock_client.AnthropicBedrock"),
        ):
            mock_session = MagicMock()
            mock_session.get_credentials.return_value = mock_credentials
            mock_session.region_name = "us-east-1"
            mock_session_class.return_value = mock_session

            create_bedrock_client(aws_region="us-east-1")

            mock_session_class.assert_called_once_with(
                profile_name=None,
                region_name="us-east-1",
            )


class TestGetModelId:
    def test_returns_default_model_id(self):
        with patch.dict(os.environ, {}, clear=True):
            model_id = get_model_id()

            assert model_id == OPUS_MODEL_ID

    def test_returns_model_arn_when_set(self):
        model_arn = "arn:aws:bedrock:us-east-1:123456789012:provisioned-model/abc123"

        with patch.dict(os.environ, {"AWS_BEDROCK_MODEL_ARN": model_arn}):
            result = get_model_id()

            assert result == model_arn


class TestGetSmallModelId:
    def test_returns_default_haiku_model_id(self):
        with patch.dict(os.environ, {}, clear=True):
            model_id = get_small_model_id()

            assert model_id == HAIKU_MODEL_ID

    def test_returns_model_arn_small_when_set(self):
        model_arn = "arn:aws:bedrock:us-east-1:123456789012:provisioned-model/haiku123"

        with patch.dict(os.environ, {"AWS_BEDROCK_MODEL_ARN_SMALL": model_arn}):
            result = get_small_model_id()

            assert result == model_arn
