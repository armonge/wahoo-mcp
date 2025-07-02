#!/usr/bin/env python3
import os
import json
import logging
from typing import Any, Dict, List, Optional
import httpx
from pydantic import BaseModel, Field
from mcp.server import Server
from mcp.types import Tool, TextContent
from mcp.server.stdio import stdio_server
from dotenv import load_dotenv
from .token_store import TokenStore

# Load environment variables
load_dotenv()

# Set up logging
logger = logging.getLogger(__name__)


class WahooConfig(BaseModel):
    access_token: Optional[str] = Field(
        default=None, description="Wahoo API access token"
    )
    base_url: str = Field(
        default="https://api.wahooligan.com", description="Base URL for Wahoo API"
    )


class Workout(BaseModel):
    id: int
    starts: str
    minutes: int
    name: str
    workout_type_id: int
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class WahooAPIClient:
    def __init__(self, config: WahooConfig, token_store: Optional[TokenStore] = None):
        self.config = config
        self.token_store = token_store or TokenStore(os.getenv("WAHOO_TOKEN_FILE"))
        self.token_data = self.token_store.get_current()
        self.client = httpx.AsyncClient(
            base_url=config.base_url,
            headers=self._get_headers(),
        )

    def _get_headers(self) -> Dict[str, str]:
        """Get current headers with valid access token"""
        if self.token_data and self.token_data.access_token:
            return {
                "Authorization": f"Bearer {self.token_data.access_token}",
                "Content-Type": "application/json",
            }
        elif self.config.access_token:
            return {
                "Authorization": f"Bearer {self.config.access_token}",
                "Content-Type": "application/json",
            }
        return {"Content-Type": "application/json"}

    async def _refresh_access_token(self) -> bool:
        """Refresh the access token using refresh token"""
        if not self.token_data or not self.token_data.refresh_token:
            logger.error("No refresh token available")
            return False

        client_id = os.getenv("WAHOO_CLIENT_ID")
        if not client_id:
            logger.error("WAHOO_CLIENT_ID not set, cannot refresh token")
            return False

        try:
            # Use PKCE flow if code_verifier is available
            data = {
                "client_id": client_id,
                "grant_type": "refresh_token",
                "refresh_token": self.token_data.refresh_token,
            }

            if self.token_data.code_verifier:
                data["code_verifier"] = self.token_data.code_verifier
            else:
                # Fall back to standard flow if client_secret is available
                client_secret = os.getenv("WAHOO_CLIENT_SECRET")
                if client_secret:
                    data["client_secret"] = client_secret

            async with httpx.AsyncClient() as refresh_client:
                response = await refresh_client.post(
                    f"{self.config.base_url}/oauth/token",
                    data=data,
                )

                if response.status_code == 200:
                    token_response = response.json()
                    self.token_data = self.token_store.update_from_response(
                        token_response
                    )
                    # Update client headers with new token
                    self.client.headers.update(self._get_headers())
                    logger.info("Successfully refreshed access token")
                    return True
                else:
                    logger.error(
                        f"Failed to refresh token: {response.status_code} - {response.text}"
                    )
                    return False

        except Exception as e:
            logger.error(f"Error refreshing token: {e}")
            return False

    async def _ensure_valid_token(self) -> bool:
        """Ensure we have a valid access token, refreshing if necessary"""
        if not self.token_data:
            return False

        if self.token_data.is_expired():
            logger.info("Access token expired, attempting to refresh")
            return await self._refresh_access_token()

        return True

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

    async def list_workouts(
        self,
        page: int = 1,
        per_page: int = 30,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        await self._ensure_valid_token()

        params = {"page": page, "per_page": per_page}
        if start_date:
            params["created_after"] = start_date
        if end_date:
            params["created_before"] = end_date

        response = await self.client.get("/v1/workouts", params=params)

        # Handle 401 by refreshing token and retrying once
        if response.status_code == 401:
            logger.info("Got 401, attempting to refresh token")
            if await self._refresh_access_token():
                response = await self.client.get("/v1/workouts", params=params)
            else:
                raise httpx.HTTPStatusError(
                    "Authentication failed and token refresh was unsuccessful",
                    request=response.request,
                    response=response,
                )

        response.raise_for_status()
        data = response.json()
        return data.get("workouts", [])

    async def get_workout(self, workout_id: int) -> Dict[str, Any]:
        await self._ensure_valid_token()

        response = await self.client.get(f"/v1/workouts/{workout_id}")

        # Handle 401 by refreshing token and retrying once
        if response.status_code == 401:
            logger.info("Got 401, attempting to refresh token")
            if await self._refresh_access_token():
                response = await self.client.get(f"/v1/workouts/{workout_id}")
            else:
                raise httpx.HTTPStatusError(
                    "Authentication failed and token refresh was unsuccessful",
                    request=response.request,
                    response=response,
                )

        response.raise_for_status()
        return response.json()


app = Server("wahoo-mcp")


@app.list_tools()
async def list_tools() -> List[Tool]:
    return [
        Tool(
            name="list_workouts",
            description="List workouts from Wahoo Cloud API",
            inputSchema={
                "type": "object",
                "properties": {
                    "page": {
                        "type": "integer",
                        "description": "Page number (default: 1)",
                        "default": 1,
                    },
                    "per_page": {
                        "type": "integer",
                        "description": "Number of items per page (default: 30)",
                        "default": 30,
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Filter workouts created after this date (ISO 8601 format)",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "Filter workouts created before this date (ISO 8601 format)",
                    },
                },
            },
        ),
        Tool(
            name="get_workout",
            description="Get detailed information about a specific workout",
            inputSchema={
                "type": "object",
                "properties": {
                    "workout_id": {
                        "type": "integer",
                        "description": "The ID of the workout to retrieve",
                    }
                },
                "required": ["workout_id"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> List[TextContent]:
    # Try to load tokens from store first
    token_store = TokenStore(os.getenv("WAHOO_TOKEN_FILE"))
    token_data = token_store.load()

    if not token_data:
        # Fall back to environment variable
        access_token = os.getenv("WAHOO_ACCESS_TOKEN")
        if not access_token:
            return [
                TextContent(
                    type="text",
                    text="Error: No authentication tokens found. Please set WAHOO_ACCESS_TOKEN environment variable or run the auth.py script to obtain tokens.",
                )
            ]
        config = WahooConfig(access_token=access_token)
    else:
        config = WahooConfig(access_token=token_data.access_token)

    try:
        async with WahooAPIClient(config, token_store) as client:
            if name == "list_workouts":
                workouts = await client.list_workouts(
                    page=arguments.get("page", 1),
                    per_page=arguments.get("per_page", 30),
                    start_date=arguments.get("start_date"),
                    end_date=arguments.get("end_date"),
                )

                if not workouts:
                    return [TextContent(type="text", text="No workouts found.")]

                result = f"Found {len(workouts)} workouts:\n\n"
                for workout in workouts:
                    result += f"- ID: {workout['id']}\n"
                    result += f"  Name: {workout['name']}\n"
                    result += f"  Date: {workout['starts']}\n"
                    result += f"  Duration: {workout['minutes']} minutes\n"
                    result += f"  Type ID: {workout['workout_type_id']}\n\n"

                return [TextContent(type="text", text=result)]

            elif name == "get_workout":
                workout_id = arguments["workout_id"]
                workout = await client.get_workout(workout_id)

                result = f"Workout Details (ID: {workout['id']}):\n"
                result += f"- Name: {workout['name']}\n"
                result += f"- Start Time: {workout['starts']}\n"
                result += f"- Duration: {workout['minutes']} minutes\n"
                result += f"- Workout Type ID: {workout['workout_type_id']}\n"

                if "created_at" in workout:
                    result += f"- Created: {workout['created_at']}\n"
                if "updated_at" in workout:
                    result += f"- Updated: {workout['updated_at']}\n"

                result += f"\nFull JSON:\n{json.dumps(workout, indent=2)}"

                return [TextContent(type="text", text=result)]

            else:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]

    except httpx.HTTPStatusError as e:
        return [
            TextContent(
                type="text",
                text=f"HTTP Error {e.response.status_code}: {e.response.text}",
            )
        ]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
