#!/usr/bin/env python3
"""Test script to validate Wahoo API credentials"""

import asyncio
import os
import sys
import time

import httpx
from dotenv import load_dotenv

from src.server import WahooAPIClient, WahooConfig
from src.token_store import TokenData, TokenStore

# Load environment variables
load_dotenv()

CLIENT_ID = os.getenv("WAHOO_CLIENT_ID")


async def test_refresh_token(token_data: TokenData, token_store: TokenStore) -> bool:
    """Test the refresh token functionality"""

    if not CLIENT_ID:
        print("❌ Error: WAHOO_CLIENT_ID not found in environment")
        return False

    print(f"   Client ID: {CLIENT_ID}")
    print(f"   Refresh token: {token_data.refresh_token[:10]}...")
    print(f"   Code verifier: {token_data.code_verifier[:10]}...")

    # Prepare refresh request
    # PKCE flow for public clients requires the code_verifier
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

    # Log the request for debugging
    print("\n   Request data:")
    print(f"   - client_id: {CLIENT_ID}")
    print("   - grant_type: refresh_token")
    print(f"   - refresh_token: {token_data.refresh_token[:20]}...")
    if "code_verifier" in refresh_data:
        print(f"   - code_verifier: {refresh_data['code_verifier'][:20]}...")
    if "client_secret" in refresh_data:
        print("   - client_secret: [REDACTED]")

    async with httpx.AsyncClient() as client:
        try:
            print("\n   Requesting new access token...")
            headers = {"Content-Type": "application/x-www-form-urlencoded"}
            response = await client.post(
                "https://api.wahooligan.com/oauth/token",
                data=refresh_data,
                headers=headers,
            )

            if response.status_code == 200:
                refresh_response = response.json()
                print("   ✅ Refresh successful!")

                # Update tokens
                new_token_data = token_store.update_from_response(refresh_response)

                print(f"   New access token: {new_token_data.access_token[:10]}...")
                if new_token_data.expires_at:
                    expires_in = int(new_token_data.expires_at - time.time())
                    print(f"   Expires in: {expires_in} seconds")

                # Test the new token
                print("\n   Testing new access token...")
                test_url = "https://api.wahooligan.com/v1/workouts"
                test_headers = {
                    "Authorization": f"Bearer {new_token_data.access_token}",
                    "Content-Type": "application/json",
                }
                test_params = {"page": 1, "per_page": 1}

                test_response = await client.get(
                    test_url, headers=test_headers, params=test_params
                )

                if test_response.status_code == 200:
                    print("   ✅ New token is valid!")
                    return True
                else:
                    print(f"   ❌ New token test failed: {test_response.status_code}")
                    return False

            else:
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
                            "   2. Your app might require a client_secret "
                            "(set WAHOO_CLIENT_SECRET)"
                        )
                        print(
                            "   3. The refresh token or code_verifier might be invalid"
                        )
                        print(
                            "   4. Re-authenticate with 'make auth' to get fresh tokens"
                        )
                except Exception:
                    pass

                return False

        except Exception as e:
            print(f"   ❌ Error during refresh: {str(e)}")
            return False


async def test_wahoo_credentials():
    """Test if Wahoo credentials are valid using the WahooAPIClient"""

    # Get token file path
    token_file = os.getenv("WAHOO_TOKEN_FILE")
    if not token_file:
        print("❌ Error: WAHOO_TOKEN_FILE environment variable is required")
        print(
            "Set it to the path where tokens should be stored "
            "(e.g., export WAHOO_TOKEN_FILE=token.json)"
        )
        return False

    # Try to load token from TokenStore
    try:
        token_store = TokenStore(token_file)
        token_data = token_store.load()
    except Exception as e:
        print(f"❌ Error initializing token store: {e}")
        return False

    if not token_data or not token_data.access_token:
        print(f"❌ Error: No valid token found in {token_file}")
        print("Run 'make auth' to obtain an access token")
        return False

    print("🔍 Testing Wahoo API credentials...")
    print(f"   Token: {token_data.access_token[:10]}...")
    print(f"   Source: Token file ({token_store.token_file})")

    # Check if token is expired
    if token_data.expires_at:
        if token_data.is_expired(buffer_seconds=0):
            print("   ⚠️  Warning: Token appears to be expired")
        elif token_data.is_expired():
            print("   ⚠️  Warning: Token will expire soon")

    # Use WahooAPIClient to test endpoints
    try:
        config = WahooConfig()
        async with WahooAPIClient(config) as client:
            # Test workouts endpoint
            workouts = await client.list_workouts(page=1, per_page=1)
            print("✅ Success! Credentials are valid")
            print(f"   Found {len(workouts)} workout(s)")

            # Test the new endpoints
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

            # Test refresh token if available
            if token_data.refresh_token and token_data.code_verifier:
                print("\n🔄 Testing refresh token...")
                refresh_success = await test_refresh_token(token_data, token_store)
                return refresh_success
            else:
                print("\n⚠️  No refresh token available to test")
                if not token_data.refresh_token:
                    print("   Missing: refresh_token")
                if not token_data.code_verifier:
                    print("   Missing: code_verifier")
            return True

    except Exception as e:
        if "401" in str(e) or "Authentication failed" in str(e):
            print("❌ Invalid credentials: Authentication failed")
            print("   The access token may be expired or invalid")
        else:
            print(f"❌ Error testing credentials: {str(e)}")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_wahoo_credentials())
    sys.exit(0 if success else 1)
