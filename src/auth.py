#!/usr/bin/env python3
"""
OAuth authentication helper for Wahoo API
Run this script to obtain an access token
"""

import asyncio
import webbrowser
from urllib.parse import urlencode
from aiohttp import web
import secrets
import base64
import hashlib
import logging
import sys
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

print("\n=== Wahoo OAuth Authentication Helper ===\n")

# Get configuration from environment or use defaults
HOST = os.getenv("WAHOO_AUTH_HOST", "localhost")
PORT = int(os.getenv("WAHOO_AUTH_PORT", "8080"))
REDIRECT_HOST = os.getenv(
    "WAHOO_REDIRECT_HOST", HOST
)  # Defaults to AUTH_HOST if not specified
REDIRECT_PORT = int(
    os.getenv("WAHOO_REDIRECT_PORT", str(PORT))
)  # Defaults to AUTH_PORT if not specified
REDIRECT_SCHEME = os.getenv(
    "WAHOO_REDIRECT_SCHEME", "http"
)  # Support https for production
AUTH_URL = os.getenv("WAHOO_AUTH_URL", "https://api.wahooligan.com/oauth/authorize")
TOKEN_URL = os.getenv("WAHOO_TOKEN_URL", "https://api.wahooligan.com/oauth/token")

# Check for client credentials in environment first
CLIENT_ID = os.getenv("WAHOO_CLIENT_ID")
CLIENT_SECRET = os.getenv("WAHOO_CLIENT_SECRET")

if not CLIENT_ID:
    CLIENT_ID = input("Enter your Wahoo Client ID: ")
if not CLIENT_SECRET:
    CLIENT_SECRET = input("Enter your Wahoo Client Secret: ")

# Build redirect URI with potentially different host
if REDIRECT_PORT == 443 and REDIRECT_SCHEME == "https":
    # Don't include port 443 for https
    REDIRECT_URI = f"{REDIRECT_SCHEME}://{REDIRECT_HOST}/callback"
elif REDIRECT_PORT == 80 and REDIRECT_SCHEME == "http":
    # Don't include port 80 for http
    REDIRECT_URI = f"{REDIRECT_SCHEME}://{REDIRECT_HOST}/callback"
else:
    # Include port for non-standard ports
    REDIRECT_URI = f"{REDIRECT_SCHEME}://{REDIRECT_HOST}:{REDIRECT_PORT}/callback"

logger.info("Auth server configuration:")
logger.info(f"  Server binding: {HOST}:{PORT}")
logger.info(f"  Redirect URI: {REDIRECT_URI}")
if REDIRECT_HOST != HOST or REDIRECT_PORT != PORT:
    logger.info("  Note: Redirect host/port differs from server binding")

# Generate PKCE challenge
logger.info("Generating PKCE challenge...")
code_verifier = (
    base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("utf-8").rstrip("=")
)
code_challenge = (
    base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest())
    .decode("utf-8")
    .rstrip("=")
)
logger.info("PKCE challenge generated successfully")

access_token = None


async def callback_handler(request):
    global access_token
    logger.info(f"Received callback request from {request.remote}")

    code = request.query.get("code")
    error = request.query.get("error")

    if error:
        logger.error(f"OAuth error: {error}")
        error_desc = request.query.get("error_description", "Unknown error")
        return web.Response(text=f"OAuth Error: {error} - {error_desc}", status=400)

    if not code:
        logger.error("No authorization code received in callback")
        return web.Response(text="Error: No authorization code received", status=400)

    logger.info(f"Received authorization code: {code[:10]}...")

    # Exchange code for token
    logger.info("Exchanging authorization code for access token...")
    import httpx

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                TOKEN_URL,
                data={
                    "client_id": CLIENT_ID,
                    "client_secret": CLIENT_SECRET,
                    "code": code,
                    "redirect_uri": REDIRECT_URI,
                    "grant_type": "authorization_code",
                    "code_verifier": code_verifier,
                },
            )

            if response.status_code == 200:
                token_data = response.json()
                access_token = token_data["access_token"]
                logger.info("Successfully obtained access token")

                # Log token details (without exposing the full token)
                logger.info(f"Token type: {token_data.get('token_type', 'bearer')}")
                if "expires_in" in token_data:
                    logger.info(f"Token expires in: {token_data['expires_in']} seconds")
                if "scope" in token_data:
                    logger.info(f"Token scope: {token_data['scope']}")

                return web.Response(
                    text=f"""
                    <html>
                    <body style="font-family: Arial, sans-serif; padding: 40px;">
                    <h1 style="color: #2e7d32;">✅ Authentication Successful!</h1>
                    <p>Your access token has been obtained.</p>
                    <p>You can close this window and return to the terminal.</p>
                    <details style="margin-top: 20px;">
                    <summary style="cursor: pointer;">Access Token (click to show)</summary>
                    <pre style="background: #f5f5f5; padding: 10px; margin-top: 10px; overflow-x: auto;">{access_token}</pre>
                    </details>
                    </body>
                    </html>
                """,
                    content_type="text/html",
                )
            else:
                logger.error(
                    f"Token exchange failed with status {response.status_code}"
                )
                logger.error(f"Response: {response.text}")
                return web.Response(
                    text=f"Error exchanging code for token: {response.status_code} - {response.text}",
                    status=500,
                )
        except Exception as e:
            logger.exception("Error during token exchange")
            return web.Response(text=f"Error: {str(e)}", status=500)


async def start_server():
    logger.info("Initializing OAuth callback server...")

    app = web.Application()
    app.router.add_get("/callback", callback_handler)

    # Add a root route for testing
    async def root_handler(request):
        return web.Response(
            text="Wahoo OAuth callback server is running. Waiting for OAuth callback..."
        )

    app.router.add_get("/", root_handler)

    runner = web.AppRunner(app)
    await runner.setup()

    try:
        site = web.TCPSite(runner, HOST, PORT)
        await site.start()
        logger.info(f"OAuth callback server started on http://{HOST}:{PORT}")
        logger.info(f"Callback endpoint: http://{HOST}:{PORT}/callback")
    except OSError as e:
        logger.error(f"Failed to start server: {e}")
        if "Address already in use" in str(e):
            logger.error(
                f"Port {PORT} is already in use. Please close any other applications using this port."
            )
        await runner.cleanup()
        return

    # Build authorization URL
    auth_params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": "user_read workouts_read",
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }

    auth_url = f"{AUTH_URL}?{urlencode(auth_params)}"

    logger.info("Opening browser for Wahoo OAuth authentication...")
    print("\n📌 Opening browser for authentication...")
    print("If browser doesn't open automatically, visit this URL:")
    print(f"\n{auth_url}\n")

    # Small delay to ensure server is ready
    await asyncio.sleep(0.5)

    if not webbrowser.open(auth_url):
        logger.warning("Failed to open browser automatically")

    logger.info("Waiting for OAuth callback...")
    print("⏳ Waiting for authentication callback...")

    # Wait for callback with timeout
    timeout = 300  # 5 minutes
    start_time = asyncio.get_event_loop().time()

    while access_token is None:
        if asyncio.get_event_loop().time() - start_time > timeout:
            logger.error(
                "Authentication timeout - no callback received within 5 minutes"
            )
            print("\n❌ Authentication timeout. Please try again.")
            break
        await asyncio.sleep(1)

    if access_token:
        print("\n✅ Success! Your access token has been obtained.")
        print("\n📋 Set it as an environment variable:")
        print(f'export WAHOO_ACCESS_TOKEN="{access_token}"')
        print("\n💡 You can also save this token securely for future use.")

    logger.info("Shutting down OAuth callback server...")
    await runner.cleanup()
    logger.info("Server shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(start_server())
    except KeyboardInterrupt:
        logger.info("Authentication process cancelled by user")
        print("\n\nAuthentication cancelled.")
    except Exception as e:
        logger.exception("Unexpected error during authentication")
        print(f"\n❌ Error: {e}")
