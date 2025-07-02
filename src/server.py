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
    base_url: str = Field(
        default="https://api.wahooligan.com", description="Base URL for Wahoo API"
    )


class WorkoutSummary(BaseModel):
    """Workout summary/results data"""

    # This can be extended based on actual API response structure
    # For now, accepting any structure since it can be null
    pass


class Workout(BaseModel):
    """Wahoo workout model matching the Cloud API schema"""

    id: int = Field(description="Unique workout identifier")
    starts: str = Field(description="Workout start time in ISO 8601 format")
    minutes: int = Field(description="Workout duration in minutes")
    name: str = Field(description="Workout name")
    plan_id: Optional[int] = Field(None, description="Associated plan ID")
    route_id: Optional[int] = Field(None, description="Associated route ID")
    workout_token: str = Field(description="Application-specific identifier")
    workout_type_id: int = Field(description="Type of workout")
    workout_summary: Optional[WorkoutSummary] = Field(
        None, description="Workout results"
    )
    created_at: str = Field(description="Creation timestamp in ISO 8601 format")
    updated_at: str = Field(description="Last update timestamp in ISO 8601 format")

    def duration_str(self) -> str:
        """Format duration as a readable string"""
        if self.minutes < 60:
            return f"{self.minutes} minutes"
        hours = self.minutes // 60
        remaining_minutes = self.minutes % 60
        if remaining_minutes == 0:
            return f"{hours} hour{'s' if hours != 1 else ''}"
        return f"{hours}h {remaining_minutes}m"

    def formatted_start_time(self) -> str:
        """Format start time for display"""
        from datetime import datetime

        try:
            dt = datetime.fromisoformat(self.starts.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
        except Exception:
            return self.starts


class WahooAPIClient:
    def __init__(self, config: WahooConfig):
        self.config = config
        token_file = os.getenv("WAHOO_TOKEN_FILE")
        if not token_file:
            raise ValueError("WAHOO_TOKEN_FILE environment variable is required")
        self.token_store = TokenStore(token_file)
        self.token_data = self.token_store.get_current()
        if not self.token_data:
            raise ValueError(f"No valid tokens found in {token_file}")
        self.client = httpx.AsyncClient(
            base_url=config.base_url,
            headers=self._get_headers(),
        )

    def _get_headers(self) -> Dict[str, str]:
        """Get current headers with valid access token"""
        return {
            "Authorization": f"Bearer {self.token_data.access_token}",
            "Content-Type": "application/json",
        }

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
            # Prepare refresh token request
            data = {
                "client_id": client_id,
                "grant_type": "refresh_token",
                "refresh_token": self.token_data.refresh_token,
            }

            # Check if we should use client_secret (confidential client) or code_verifier (public client)
            client_secret = os.getenv("WAHOO_CLIENT_SECRET")
            if client_secret:
                # Confidential client: use client_secret
                data["client_secret"] = client_secret
                logger.info(
                    "Using client_secret for token refresh (confidential client)"
                )
            elif self.token_data.code_verifier:
                # Public client: use PKCE code_verifier
                data["code_verifier"] = self.token_data.code_verifier
                logger.info(
                    "Using code_verifier for token refresh (public client with PKCE)"
                )
            else:
                logger.warning(
                    "No client_secret or code_verifier available for token refresh"
                )

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
    ) -> List[Workout]:
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
        workouts_data = data.get("workouts", [])

        # Convert each workout dict to Workout object
        workouts = []
        for workout_dict in workouts_data:
            try:
                workout = Workout(**workout_dict)
                workouts.append(workout)
            except Exception as e:
                logger.warning(
                    f"Failed to parse workout {workout_dict.get('id', 'unknown')}: {e}"
                )
                # Continue with other workouts instead of failing completely
                continue

        return workouts

    async def get_workout(self, workout_id: int) -> Workout:
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
        workout_dict = response.json()

        try:
            return Workout(**workout_dict)
        except Exception as e:
            logger.error(f"Failed to parse workout {workout_id}: {e}")
            raise ValueError(f"Invalid workout data received from API: {e}")


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
    config = WahooConfig()

    try:
        async with WahooAPIClient(config) as client:
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
                    result += f"- ID: {workout.id}\n"
                    result += f"  Name: {workout.name}\n"
                    result += f"  Date: {workout.formatted_start_time()}\n"
                    result += f"  Duration: {workout.duration_str()}\n"
                    result += f"  Type ID: {workout.workout_type_id}\n"
                    if workout.plan_id:
                        result += f"  Plan ID: {workout.plan_id}\n"
                    if workout.route_id:
                        result += f"  Route ID: {workout.route_id}\n"
                    result += "\n"

                return [TextContent(type="text", text=result)]

            elif name == "get_workout":
                workout_id = arguments["workout_id"]
                workout = await client.get_workout(workout_id)

                result = f"Workout Details (ID: {workout.id}):\n"
                result += f"- Name: {workout.name}\n"
                result += f"- Start Time: {workout.formatted_start_time()}\n"
                result += f"- Duration: {workout.duration_str()}\n"
                result += f"- Workout Type ID: {workout.workout_type_id}\n"
                result += f"- Workout Token: {workout.workout_token}\n"

                if workout.plan_id:
                    result += f"- Plan ID: {workout.plan_id}\n"
                if workout.route_id:
                    result += f"- Route ID: {workout.route_id}\n"

                result += f"- Created: {workout.created_at}\n"
                result += f"- Updated: {workout.updated_at}\n"

                if workout.workout_summary:
                    result += "- Has Summary: Yes\n"
                else:
                    result += "- Has Summary: No\n"

                result += f"\nFull JSON:\n{json.dumps(workout.model_dump(), indent=2)}"

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
