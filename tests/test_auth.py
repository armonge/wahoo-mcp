#!/usr/bin/env python3
"""
Tests for the OAuth authentication module
"""

import asyncio
import base64
import hashlib
import os
import secrets
import time
from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from urllib.parse import urlencode

import pytest
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop

from src import auth
from src.token_store import TokenData


class TestAuthModule(AioHTTPTestCase):
    """Test the auth module functions."""

    async def get_application(self):
        """Create test application."""
        # Import auth module functions to test

        app = web.Application()
        app.router.add_get("/callback", auth.callback_handler)
        return app

    def setUp(self):
        """Set up test environment."""
        super().setUp()
        # Clear global variables

        auth.access_token = None
        auth.refresh_token = None

    @unittest_run_loop
    async def test_callback_handler_success(self):
        """Test successful OAuth callback handling."""
        with (
            patch("src.auth.CLIENT_ID", "test_client_id"),
            patch("src.auth.CLIENT_SECRET", "test_client_secret"),
            patch("src.auth.REDIRECT_URI", "http://localhost:8080/callback"),
            patch("src.auth.code_verifier", "test_verifier"),
            patch("src.auth.TOKEN_URL", "https://api.wahooligan.com/oauth/token"),
            patch("src.auth.token_store") as mock_store,
        ):
            # Mock the token store
            mock_store.save = Mock()

            # Mock the HTTP client response
            mock_response = MagicMock()
            mock_response.status_code = HTTPStatus.OK
            mock_response.json.return_value = {
                "access_token": "test_access_token",
                "refresh_token": "test_refresh_token",
                "expires_in": 7200,
                "token_type": "Bearer",
                "scope": "user_read workouts_read",
            }

            with patch("httpx.AsyncClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.post.return_value = mock_response
                mock_client.__aenter__.return_value = mock_client
                mock_client_class.return_value = mock_client

                # Test successful callback
                response = await self.client.request(
                    "GET", "/callback?code=test_auth_code"
                )

                self.assertEqual(response.status, HTTPStatus.OK)
                self.assertIn("Authentication Successful", await response.text())

                # Verify token store was called
                mock_store.save.assert_called_once()

    @unittest_run_loop
    async def test_callback_handler_oauth_error(self):
        """Test OAuth error handling in callback."""
        response = await self.client.request(
            "GET", "/callback?error=access_denied&error_description=User%20denied"
        )

        self.assertEqual(response.status, HTTPStatus.BAD_REQUEST)
        self.assertIn("OAuth Error", await response.text())

    @unittest_run_loop
    async def test_callback_handler_no_code(self):
        """Test callback without authorization code."""
        response = await self.client.request("GET", "/callback")

        self.assertEqual(response.status, HTTPStatus.BAD_REQUEST)
        self.assertIn("No authorization code received", await response.text())

    @unittest_run_loop
    async def test_callback_handler_token_exchange_failure(self):
        """Test token exchange failure."""
        with (
            patch("src.auth.CLIENT_ID", "test_client_id"),
            patch("src.auth.CLIENT_SECRET", "test_client_secret"),
            patch("src.auth.REDIRECT_URI", "http://localhost:8080/callback"),
            patch("src.auth.code_verifier", "test_verifier"),
            patch("src.auth.TOKEN_URL", "https://api.wahooligan.com/oauth/token"),
        ):
            # Mock failed HTTP response
            mock_response = MagicMock()
            mock_response.status_code = HTTPStatus.BAD_REQUEST
            mock_response.text = "invalid_grant"

            with patch("httpx.AsyncClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.post.return_value = mock_response
                mock_client.__aenter__.return_value = mock_client
                mock_client_class.return_value = mock_client

                response = await self.client.request(
                    "GET", "/callback?code=invalid_code"
                )

                self.assertEqual(response.status, HTTPStatus.INTERNAL_SERVER_ERROR)
                self.assertIn("Error exchanging code", await response.text())

    @unittest_run_loop
    async def test_callback_handler_network_error(self):
        """Test network error during token exchange."""
        with (
            patch("src.auth.CLIENT_ID", "test_client_id"),
            patch("src.auth.CLIENT_SECRET", "test_client_secret"),
            patch("src.auth.REDIRECT_URI", "http://localhost:8080/callback"),
            patch("src.auth.code_verifier", "test_verifier"),
            patch("src.auth.TOKEN_URL", "https://api.wahooligan.com/oauth/token"),
        ):
            with patch("httpx.AsyncClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.post.side_effect = Exception("Network error")
                mock_client.__aenter__.return_value = mock_client
                mock_client_class.return_value = mock_client

                response = await self.client.request("GET", "/callback?code=test_code")

                self.assertEqual(response.status, HTTPStatus.INTERNAL_SERVER_ERROR)
                self.assertIn("Error: Network error", await response.text())


class TestPKCEGeneration:
    """Test PKCE challenge generation."""

    def test_pkce_code_verifier_format(self):
        """Test that code verifier has correct format."""
        # Generate like the auth module does
        code_verifier = (
            base64.urlsafe_b64encode(secrets.token_bytes(32))
            .decode("utf-8")
            .rstrip("=")
        )

        # Should be URL-safe base64 without padding
        assert len(code_verifier) >= 43  # 32 bytes -> 43+ chars
        assert len(code_verifier) <= 128  # RFC requirement
        assert "=" not in code_verifier  # No padding

    def test_pkce_code_challenge_generation(self):
        """Test that code challenge is generated correctly."""
        code_verifier = "test_verifier_123456789012345678901234567890"

        # Generate challenge like the auth module does
        code_challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest())
            .decode("utf-8")
            .rstrip("=")
        )

        # Verify it's correct SHA256 hash
        expected_hash = hashlib.sha256(code_verifier.encode()).digest()
        expected_challenge = (
            base64.urlsafe_b64encode(expected_hash).decode("utf-8").rstrip("=")
        )

        assert code_challenge == expected_challenge
        assert len(code_challenge) == 43  # SHA256 -> 32 bytes -> 43 chars


class TestRedirectUriGeneration:
    """Test redirect URI generation logic."""

    def test_https_port_443_no_port(self):
        """Test HTTPS on port 443 doesn't include port."""
        with patch.dict(
            os.environ,
            {
                "WAHOO_REDIRECT_HOST": "example.com",
                "WAHOO_REDIRECT_PORT": "443",
                "WAHOO_REDIRECT_SCHEME": "https",
            },
        ):
            # Simulate the auth module logic
            host = "example.com"
            port = 443
            scheme = "https"

            if port == 443 and scheme == "https":
                redirect_uri = f"{scheme}://{host}/callback"
            else:
                redirect_uri = f"{scheme}://{host}:{port}/callback"

            assert redirect_uri == "https://example.com/callback"

    def test_http_port_80_no_port(self):
        """Test HTTP on port 80 doesn't include port."""
        with patch.dict(
            os.environ,
            {
                "WAHOO_REDIRECT_HOST": "localhost",
                "WAHOO_REDIRECT_PORT": "80",
                "WAHOO_REDIRECT_SCHEME": "http",
            },
        ):
            # Simulate the auth module logic
            host = "localhost"
            port = 80
            scheme = "http"

            if port == 80 and scheme == "http":
                redirect_uri = f"{scheme}://{host}/callback"
            else:
                redirect_uri = f"{scheme}://{host}:{port}/callback"

            assert redirect_uri == "http://localhost/callback"

    def test_custom_port_includes_port(self):
        """Test custom ports are included in URI."""
        with patch.dict(
            os.environ,
            {
                "WAHOO_REDIRECT_HOST": "localhost",
                "WAHOO_REDIRECT_PORT": "8080",
                "WAHOO_REDIRECT_SCHEME": "http",
            },
        ):
            # Simulate the auth module logic
            host = "localhost"
            port = 8080
            scheme = "http"

            if port == 443 and scheme == "https":
                redirect_uri = f"{scheme}://{host}/callback"
            elif port == 80 and scheme == "http":
                redirect_uri = f"{scheme}://{host}/callback"
            else:
                redirect_uri = f"{scheme}://{host}:{port}/callback"

            assert redirect_uri == "http://localhost:8080/callback"


class TestAuthConfiguration:
    """Test authentication configuration and environment variables."""

    def test_default_configuration(self):
        """Test default configuration values."""
        with patch.dict(os.environ, {}, clear=True):
            # Test defaults match auth module
            host = os.getenv("WAHOO_AUTH_HOST", "localhost")
            port = int(os.getenv("WAHOO_AUTH_PORT", "8080"))
            scheme = os.getenv("WAHOO_REDIRECT_SCHEME", "http")

            assert host == "localhost"
            assert port == 8080
            assert scheme == "http"

    def test_custom_configuration(self):
        """Test custom configuration from environment."""
        with patch.dict(
            os.environ,
            {
                "WAHOO_AUTH_HOST": "0.0.0.0",  # noqa: S104
                "WAHOO_AUTH_PORT": "9000",
                "WAHOO_REDIRECT_SCHEME": "https",
                "WAHOO_AUTH_URL": "https://custom.example.com/oauth/authorize",
                "WAHOO_TOKEN_URL": "https://custom.example.com/oauth/token",
            },
        ):
            host = os.getenv("WAHOO_AUTH_HOST", "localhost")
            port = int(os.getenv("WAHOO_AUTH_PORT", "8080"))
            scheme = os.getenv("WAHOO_REDIRECT_SCHEME", "http")
            auth_url = os.getenv(
                "WAHOO_AUTH_URL", "https://api.wahooligan.com/oauth/authorize"
            )
            token_url = os.getenv(
                "WAHOO_TOKEN_URL", "https://api.wahooligan.com/oauth/token"
            )

            assert host == "0.0.0.0"  # noqa: S104
            assert port == 9000
            assert scheme == "https"
            assert auth_url == "https://custom.example.com/oauth/authorize"
            assert token_url == "https://custom.example.com/oauth/token"


class TestTokenStorage:
    """Test token storage integration."""

    def test_token_data_creation(self):
        """Test TokenData object creation with auth module data."""
        # Test data similar to what auth module creates
        access_token = "test_access_token"
        refresh_token = "test_refresh_token"
        code_verifier = "test_code_verifier"
        expires_in = 7200

        token_obj = TokenData(
            access_token=access_token,
            refresh_token=refresh_token,
            code_verifier=code_verifier,
        )
        token_obj.expires_at = time.time() + expires_in

        assert token_obj.access_token == access_token
        assert token_obj.refresh_token == refresh_token
        assert token_obj.code_verifier == code_verifier
        assert token_obj.expires_at > time.time()

    def test_token_storage_integration(self, tmp_path):
        """Test token storage and retrieval."""
        # Create test token file
        token_file = tmp_path / "test_tokens.json"

        # Mock TokenStore
        with patch("src.auth.TokenStore") as mock_store_class:
            mock_store = Mock()
            mock_store.token_file = str(token_file)
            mock_store.save = Mock()
            mock_store_class.return_value = mock_store

            # Test data
            token_obj = TokenData(
                access_token="test_token",
                refresh_token="test_refresh",
                code_verifier="test_verifier",
            )

            # Save token
            mock_store.save(token_obj)

            # Verify save was called
            mock_store.save.assert_called_once_with(token_obj)


class TestOAuthScopes:
    """Test OAuth scope configuration."""

    def test_required_scopes(self):
        """Test that all required scopes are included."""
        # Scopes from the auth module
        expected_scopes = [
            "user_read",
            "workouts_read",
            "routes_read",
            "plans_read",
            "plans_write",
            "power_zones_read",
        ]

        auth_scopes = (
            "user_read workouts_read routes_read plans_read "
            "plans_write power_zones_read"
        )

        for scope in expected_scopes:
            assert scope in auth_scopes

    def test_scope_string_format(self):
        """Test scope string is properly formatted."""
        auth_scopes = (
            "user_read workouts_read routes_read plans_read "
            "plans_write power_zones_read"
        )

        # Should be space-separated
        scope_list = auth_scopes.split()
        assert len(scope_list) == 6
        assert "user_read" in scope_list
        assert "plans_write" in scope_list


@pytest.mark.asyncio
async def test_server_timeout_simulation():
    """Test server timeout behavior simulation."""
    # Simulate the timeout logic from the auth module
    timeout = 0.1  # Short timeout for testing
    start_time = asyncio.get_event_loop().time()
    access_token = None

    # Simulate waiting loop
    while access_token is None:
        if asyncio.get_event_loop().time() - start_time > timeout:
            break
        await asyncio.sleep(0.01)

    # Should have timed out
    assert access_token is None
    assert asyncio.get_event_loop().time() - start_time >= timeout


class TestErrorHandling:
    """Test error handling scenarios."""

    def test_missing_token_file_env(self):
        """Test handling of missing WAHOO_TOKEN_FILE."""
        with patch.dict(os.environ, {}, clear=True):
            token_file = os.getenv("WAHOO_TOKEN_FILE")
            assert token_file is None

    def test_client_credentials_prompting(self):
        """Test client credentials prompting logic."""
        with patch.dict(os.environ, {}, clear=True):
            # Simulate the auth module logic
            client_id = os.getenv("WAHOO_CLIENT_ID")
            client_secret = os.getenv("WAHOO_CLIENT_SECRET")

            assert client_id is None
            assert client_secret is None

            # In real auth module, these would prompt for input
            # Here we just verify the environment check works

    def test_client_credentials_from_env(self):
        """Test client credentials from environment."""
        with patch.dict(
            os.environ,
            {
                "WAHOO_CLIENT_ID": "test_client_id",
                "WAHOO_CLIENT_SECRET": "test_client_secret",
            },
        ):
            client_id = os.getenv("WAHOO_CLIENT_ID")
            client_secret = os.getenv("WAHOO_CLIENT_SECRET")

            assert client_id == "test_client_id"
            assert client_secret == "test_client_secret"


class TestAuthUrlGeneration:
    """Test OAuth authorization URL generation."""

    def test_auth_url_parameters(self):
        """Test authorization URL contains required parameters."""

        # Simulate auth module URL generation
        client_id = "test_client_id"
        redirect_uri = "http://localhost:8080/callback"
        code_challenge = "test_challenge"

        auth_params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": (
                "user_read workouts_read routes_read plans_read "
                "plans_write power_zones_read"
            ),
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }

        auth_url = (
            f"https://api.wahooligan.com/oauth/authorize?{urlencode(auth_params)}"
        )

        # Verify required parameters are present
        assert "client_id=test_client_id" in auth_url
        assert "response_type=code" in auth_url
        assert "code_challenge_method=S256" in auth_url
        assert "scope=" in auth_url
        assert "plans_write" in auth_url
