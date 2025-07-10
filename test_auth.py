#!/usr/bin/env python3
"""Test script to validate Wahoo API credentials"""

import asyncio
import os
import sys
import time
from http import HTTPStatus

import httpx
from dotenv import load_dotenv

from src.server import WahooAPIClient, WahooConfig
from src.token_store import TokenData, TokenStore

# Load environment variables
load_dotenv()

CLIENT_ID = os.getenv("WAHOO_CLIENT_ID")


def _validate_client_id() -> bool:
    """Validate that CLIENT_ID is available."""
    if not CLIENT_ID:
        print("❌ Error: WAHOO_CLIENT_ID not found in environment")
        return False
    return True


def _print_token_info(token_data: TokenData) -> None:
    """Print token information for debugging."""
    print(f"   Client ID: {CLIENT_ID}")
    print(f"   Refresh token: {token_data.refresh_token[:10]}...")
    print(f"   Code verifier: {token_data.code_verifier[:10]}...")


def _prepare_refresh_data(token_data: TokenData) -> dict:
    """Prepare refresh request data with client credentials."""
    refresh_data = {
        "client_id": CLIENT_ID,
        "grant_type": "refresh_token",
        "refresh_token": token_data.refresh_token,
    }

    # Check if we should use client_secret (confidential client) or
    # code_verifier (public client)
    client_secret = os.getenv("WAHOO_CLIENT_SECRET")
    if client_secret:
        # Confidential client: use client_secret
        refresh_data["client_secret"] = client_secret
        print("   App type: Confidential client (using client_secret)")
    elif token_data.code_verifier:
        # Public client: use PKCE code_verifier
        refresh_data["code_verifier"] = token_data.code_verifier
        print("   App type: Public client (using PKCE code_verifier)")
    else:
        print("   ⚠️  Warning: No client_secret or code_verifier available")

    return refresh_data


def _log_request_data(refresh_data: dict, token_data: TokenData) -> None:
    """Log the request data for debugging."""
    print("\n   Request data:")
    print(f"   - client_id: {CLIENT_ID}")
    print("   - grant_type: refresh_token")
    print(f"   - refresh_token: {token_data.refresh_token[:20]}...")
    if "code_verifier" in refresh_data:
        print(f"   - code_verifier: {refresh_data['code_verifier'][:20]}...")
    if "client_secret" in refresh_data:
        print("   - client_secret: [REDACTED]")


async def _test_new_token(client, new_token_data: TokenData) -> bool:
    """Test the new access token by making an API call."""
    print("\n   Testing new access token...")
    test_url = "https://api.wahooligan.com/v1/workouts"
    test_headers = {
        "Authorization": f"Bearer {new_token_data.access_token}",
        "Content-Type": "application/json",
    }
    test_params = {"page": 1, "per_page": 1}

    test_response = await client.get(test_url, headers=test_headers, params=test_params)

    if test_response.status_code == HTTPStatus.OK:
        print("   ✅ New token is valid!")
        return True
    else:
        print(f"   ❌ New token test failed: {test_response.status_code}")
        return False


def _handle_refresh_error(response) -> None:
    """Handle and log refresh token errors."""
    print(f"   ❌ Refresh failed: {response.status_code}")
    print(f"   Response: {response.text}")

    # Try to parse error response
    try:
        error_data = response.json()
        if "error_description" in error_data:
            print(f"\n   Error details: {error_data['error_description']}")

        # Check if this is a client authentication issue
        if error_data.get("error") == "invalid_client":
            print("\n   💡 Possible solutions:")
            print("   1. Ensure WAHOO_CLIENT_ID is correct")
            print(
                "   2. Your app might require a client_secret (set WAHOO_CLIENT_SECRET)"
            )
            print("   3. The refresh token or code_verifier might be invalid")
            print("   4. Re-authenticate with 'make auth' to get fresh tokens")
    except Exception:
        pass


async def test_refresh_token(token_data: TokenData, token_store: TokenStore) -> bool:
    """Test the refresh token functionality"""
    if not _validate_client_id():
        return False

    _print_token_info(token_data)
    refresh_data = _prepare_refresh_data(token_data)
    _log_request_data(refresh_data, token_data)

    async with httpx.AsyncClient() as client:
        try:
            print("\n   Requesting new access token...")
            headers = {"Content-Type": "application/x-www-form-urlencoded"}
            response = await client.post(
                "https://api.wahooligan.com/oauth/token",
                data=refresh_data,
                headers=headers,
            )

            if response.status_code == HTTPStatus.OK:
                refresh_response = response.json()
                print("   ✅ Refresh successful!")

                # Update tokens
                new_token_data = token_store.update_from_response(refresh_response)

                print(f"   New access token: {new_token_data.access_token[:10]}...")
                if new_token_data.expires_at:
                    expires_in = int(new_token_data.expires_at - time.time())
                    print(f"   Expires in: {expires_in} seconds")

                return await _test_new_token(client, new_token_data)
            else:
                _handle_refresh_error(response)
                return False

        except Exception as e:
            print(f"   ❌ Error during refresh: {str(e)}")
            return False


def _validate_token_file() -> tuple[str | None, str | None]:
    """Validate token file exists and return path and error message."""
    token_file = os.getenv("WAHOO_TOKEN_FILE")
    if not token_file:
        error_msg = (
            "❌ Error: WAHOO_TOKEN_FILE environment variable is required\n"
            "Set it to the path where tokens should be stored "
            "(e.g., export WAHOO_TOKEN_FILE=token.json)"
        )
        return None, error_msg
    return token_file, None


def _load_token_data(
    token_file: str,
) -> tuple[TokenData | None, TokenStore | None, str | None]:
    """Load token data from file and return data, store, and error message."""
    try:
        token_store = TokenStore(token_file)
        token_data = token_store.load()
    except Exception as e:
        return None, None, f"❌ Error initializing token store: {e}"

    if not token_data or not token_data.access_token:
        error_msg = (
            f"❌ Error: No valid token found in {token_file}\n"
            "Run 'make auth' to obtain an access token"
        )
        return None, None, error_msg

    return token_data, token_store, None


def _print_token_status(token_data: TokenData, token_store: TokenStore) -> None:
    """Print token status information."""
    print("🔍 Testing Wahoo API credentials...")
    print(f"   Token: {token_data.access_token[:10]}...")
    print(f"   Source: Token file ({token_store.token_file})")

    # Check if token is expired
    if token_data.expires_at:
        if token_data.is_expired(buffer_seconds=0):
            print("   ⚠️  Warning: Token appears to be expired")
        elif token_data.is_expired():
            print("   ⚠️  Warning: Token will expire soon")


async def _test_additional_endpoints(client) -> None:
    """Test additional API endpoints and print results."""
    print("\n🔍 Testing additional API endpoints...")

    # Test routes endpoint
    try:
        routes = await client.list_routes()
        print(f"   Routes: ✅ Found {len(routes)} route(s)")
    except Exception as e:
        print(f"   Routes: ❌ Failed ({str(e)})")

    # Test plans endpoint
    try:
        plans = await client.list_plans()
        print(f"   Plans: ✅ Found {len(plans)} plan(s)")
    except Exception as e:
        print(f"   Plans: ❌ Failed ({str(e)})")

    # Test power zones endpoint
    try:
        power_zones = await client.list_power_zones()
        print(f"   Power Zones: ✅ Found {len(power_zones)} power zone(s)")
    except Exception as e:
        print(f"   Power Zones: ❌ Failed ({str(e)})")


def _check_refresh_token_availability(token_data: TokenData) -> bool:
    """Check if refresh token is available and print status."""
    if token_data.refresh_token and token_data.code_verifier:
        return True
    else:
        print("\n⚠️  No refresh token available to test")
        if not token_data.refresh_token:
            print("   Missing: refresh_token")
        if not token_data.code_verifier:
            print("   Missing: code_verifier")
        return False


def _handle_api_error(e: Exception) -> None:
    """Handle and log API errors."""
    if "401" in str(e) or "Authentication failed" in str(e):
        print("❌ Invalid credentials: Authentication failed")
        print("   The access token may be expired or invalid")
    else:
        print(f"❌ Error testing credentials: {str(e)}")


async def test_wahoo_credentials():
    """Test if Wahoo credentials are valid using the WahooAPIClient"""
    # Validate token file
    token_file, error = _validate_token_file()
    if error:
        print(error)
        return False

    # Load token data
    token_data, token_store, error = _load_token_data(token_file)
    if error:
        print(error)
        return False

    _print_token_status(token_data, token_store)

    # Use WahooAPIClient to test endpoints
    try:
        config = WahooConfig()
        async with WahooAPIClient(config) as client:
            # Test workouts endpoint
            workouts = await client.list_workouts(page=1, per_page=1)
            print("✅ Success! Credentials are valid")
            print(f"   Found {len(workouts)} workout(s)")

            await _test_additional_endpoints(client)

            # Test refresh token if available
            if _check_refresh_token_availability(token_data):
                print("\n🔄 Testing refresh token...")
                refresh_success = await test_refresh_token(token_data, token_store)
                return refresh_success
            return True

    except Exception as e:
        _handle_api_error(e)
        return False


if __name__ == "__main__":
    success = asyncio.run(test_wahoo_credentials())
    sys.exit(0 if success else 1)
