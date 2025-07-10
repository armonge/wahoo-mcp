#!/usr/bin/env python3
import base64
import json
import logging
import os
from http import HTTPStatus
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool
from pydantic import BaseModel, Field

from .models import (
    CreatePlanRequest,
    CreatePlanResponse,
    Plan,
    PowerZone,
    Route,
    Workout,
    WorkoutInterval,
    WorkoutPlan,
    WorkoutTarget,
)
from .token_store import TokenStore

# Type aliases for cleaner function signatures
ToolResponse = list[TextContent]
Arguments = dict[str, Any]

# Load environment variables
load_dotenv()

# Set up logging
logger = logging.getLogger(__name__)


class WahooConfig(BaseModel):
    base_url: str = Field(
        default="https://api.wahooligan.com", description="Base URL for Wahoo API"
    )


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

    def _get_headers(self) -> dict[str, str]:
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

            # Check if we should use client_secret (confidential client) or
            # code_verifier (public client)
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

                if response.status_code == HTTPStatus.OK:
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
                        f"Failed to refresh token: {response.status_code} - "
                        f"{response.text}"
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
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[Workout]:
        await self._ensure_valid_token()

        params = {"page": page, "per_page": per_page}
        if start_date:
            params["created_after"] = start_date
        if end_date:
            params["created_before"] = end_date

        response = await self.client.get("/v1/workouts", params=params)

        # Handle 401 by refreshing token and retrying once
        if response.status_code == HTTPStatus.UNAUTHORIZED:
            logger.info("Got 401 Unauthorized, attempting to refresh token")
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
        if response.status_code == HTTPStatus.UNAUTHORIZED:
            logger.info("Got 401 Unauthorized, attempting to refresh token")
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
            raise ValueError(f"Invalid workout data received from API: {e}") from e

    async def list_routes(self, external_id: str | None = None) -> list[Route]:
        await self._ensure_valid_token()

        params = {}
        if external_id:
            params["external_id"] = external_id

        response = await self.client.get("/v1/routes", params=params)

        # Handle 401 by refreshing token and retrying once
        if response.status_code == HTTPStatus.UNAUTHORIZED:
            logger.info("Got 401 Unauthorized, attempting to refresh token")
            if await self._refresh_access_token():
                response = await self.client.get("/v1/routes", params=params)
            else:
                raise httpx.HTTPStatusError(
                    "Authentication failed and token refresh was unsuccessful",
                    request=response.request,
                    response=response,
                )

        response.raise_for_status()
        data = response.json()
        # Handle both dict and list response formats
        if isinstance(data, dict):
            routes_data = data.get("routes", [])
        elif isinstance(data, list):
            routes_data = data
        else:
            routes_data = []

        # Convert each route dict to Route object
        routes = []
        for route_dict in routes_data:
            try:
                route = Route(**route_dict)
                routes.append(route)
            except Exception as e:
                logger.warning(
                    f"Failed to parse route {route_dict.get('id', 'unknown')}: {e}"
                )
                # Continue with other routes instead of failing completely
                continue

        return routes

    async def get_route(self, route_id: int) -> Route:
        await self._ensure_valid_token()

        response = await self.client.get(f"/v1/routes/{route_id}")

        # Handle 401 by refreshing token and retrying once
        if response.status_code == HTTPStatus.UNAUTHORIZED:
            logger.info("Got 401 Unauthorized, attempting to refresh token")
            if await self._refresh_access_token():
                response = await self.client.get(f"/v1/routes/{route_id}")
            else:
                raise httpx.HTTPStatusError(
                    "Authentication failed and token refresh was unsuccessful",
                    request=response.request,
                    response=response,
                )

        response.raise_for_status()
        route_dict = response.json()

        try:
            return Route(**route_dict)
        except Exception as e:
            logger.error(f"Failed to parse route {route_id}: {e}")
            raise ValueError(f"Invalid route data received from API: {e}") from e

    async def list_plans(self, external_id: str | None = None) -> list[Plan]:
        await self._ensure_valid_token()

        params = {}
        if external_id:
            params["external_id"] = external_id

        response = await self.client.get("/v1/plans", params=params)

        # Handle 401 by refreshing token and retrying once
        if response.status_code == HTTPStatus.UNAUTHORIZED:
            logger.info("Got 401 Unauthorized, attempting to refresh token")
            if await self._refresh_access_token():
                response = await self.client.get("/v1/plans", params=params)
            else:
                raise httpx.HTTPStatusError(
                    "Authentication failed and token refresh was unsuccessful",
                    request=response.request,
                    response=response,
                )

        response.raise_for_status()
        data = response.json()
        # Handle both dict and list response formats
        if isinstance(data, dict):
            plans_data = data.get("plans", [])
        elif isinstance(data, list):
            plans_data = data
        else:
            plans_data = []

        # Convert each plan dict to Plan object
        plans = []
        for plan_dict in plans_data:
            try:
                plan = Plan(**plan_dict)
                plans.append(plan)
            except Exception as e:
                logger.warning(
                    f"Failed to parse plan {plan_dict.get('id', 'unknown')}: {e}"
                )
                # Continue with other plans instead of failing completely
                continue

        return plans

    async def get_plan(self, plan_id: int) -> Plan:
        await self._ensure_valid_token()

        response = await self.client.get(f"/v1/plans/{plan_id}")

        # Handle 401 by refreshing token and retrying once
        if response.status_code == HTTPStatus.UNAUTHORIZED:
            logger.info("Got 401 Unauthorized, attempting to refresh token")
            if await self._refresh_access_token():
                response = await self.client.get(f"/v1/plans/{plan_id}")
            else:
                raise httpx.HTTPStatusError(
                    "Authentication failed and token refresh was unsuccessful",
                    request=response.request,
                    response=response,
                )

        response.raise_for_status()
        plan_dict = response.json()

        try:
            return Plan(**plan_dict)
        except Exception as e:
            logger.error(f"Failed to parse plan {plan_id}: {e}")
            raise ValueError(f"Invalid plan data received from API: {e}") from e

    async def create_plan(self, plan_request: CreatePlanRequest) -> CreatePlanResponse:
        """Create a new plan in the user's library"""
        await self._ensure_valid_token()

        # Convert structured plan data to Wahoo plan JSON format
        plan_json = plan_request.plan.to_wahoo_format()

        # Encode as base64
        plan_json_str = json.dumps(plan_json, separators=(",", ":"))
        plan_base64 = base64.b64encode(plan_json_str.encode("utf-8")).decode("utf-8")

        # Prepare form data for the API call
        form_data = {
            "plan[file]": f"data:application/json;base64,{plan_base64}",
            "plan[external_id]": plan_request.external_id,
            "plan[provider_updated_at]": plan_request.provider_updated_at,
        }

        if plan_request.filename:
            form_data["plan[filename]"] = plan_request.filename

        response = await self.client.post(
            "/v1/plans",
            data=form_data,
            headers={
                "Authorization": f"Bearer {self.token_data.access_token}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )

        # Handle 401 by refreshing token and retrying once
        if response.status_code == HTTPStatus.UNAUTHORIZED:
            logger.info("Got 401 Unauthorized, attempting to refresh token")
            if await self._refresh_access_token():
                response = await self.client.post(
                    "/v1/plans",
                    data=form_data,
                    headers={
                        "Authorization": f"Bearer {self.token_data.access_token}",
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                )
            else:
                raise httpx.HTTPStatusError(
                    "Authentication failed and token refresh was unsuccessful",
                    request=response.request,
                    response=response,
                )

        response.raise_for_status()
        plan_dict = response.json()

        try:
            return CreatePlanResponse(**plan_dict)
        except Exception as e:
            logger.error(f"Failed to parse created plan: {e}")
            raise ValueError(f"Invalid plan data received from API: {e}") from e

    async def list_power_zones(self) -> list[PowerZone]:
        await self._ensure_valid_token()

        response = await self.client.get("/v1/power_zones")

        # Handle 401 by refreshing token and retrying once
        if response.status_code == HTTPStatus.UNAUTHORIZED:
            logger.info("Got 401 Unauthorized, attempting to refresh token")
            if await self._refresh_access_token():
                response = await self.client.get("/v1/power_zones")
            else:
                raise httpx.HTTPStatusError(
                    "Authentication failed and token refresh was unsuccessful",
                    request=response.request,
                    response=response,
                )

        response.raise_for_status()
        data = response.json()
        # Handle both dict and list response formats
        if isinstance(data, dict):
            power_zones_data = data.get("power_zones", [])
        elif isinstance(data, list):
            power_zones_data = data
        else:
            power_zones_data = []

        # Convert each power zone dict to PowerZone object
        power_zones = []
        for power_zone_dict in power_zones_data:
            try:
                power_zone = PowerZone(**power_zone_dict)
                power_zones.append(power_zone)
            except Exception as e:
                logger.warning(
                    f"Failed to parse power zone "
                    f"{power_zone_dict.get('id', 'unknown')}: {e}"
                )
                # Continue with other power zones instead of failing completely
                continue

        return power_zones

    async def get_power_zone(self, power_zone_id: int) -> PowerZone:
        await self._ensure_valid_token()

        response = await self.client.get(f"/v1/power_zones/{power_zone_id}")

        # Handle 401 by refreshing token and retrying once
        if response.status_code == HTTPStatus.UNAUTHORIZED:
            logger.info("Got 401 Unauthorized, attempting to refresh token")
            if await self._refresh_access_token():
                response = await self.client.get(f"/v1/power_zones/{power_zone_id}")
            else:
                raise httpx.HTTPStatusError(
                    "Authentication failed and token refresh was unsuccessful",
                    request=response.request,
                    response=response,
                )

        response.raise_for_status()
        power_zone_dict = response.json()

        try:
            return PowerZone(**power_zone_dict)
        except Exception as e:
            logger.error(f"Failed to parse power zone {power_zone_id}: {e}")
            raise ValueError(f"Invalid power zone data received from API: {e}") from e


def load_json_schema(schema: str) -> dict:
    """Load a JSON schema from a file."""
    return json.loads((Path("src/schemas") / schema).read_text())


app = Server("wahoo-mcp")


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="list_workouts",
            description="List workouts from Wahoo Cloud API",
            inputSchema=load_json_schema("list_workouts.json"),
        ),
        Tool(
            name="get_workout",
            description="Get detailed information about a specific workout",
            inputSchema=load_json_schema("get_workout.json"),
        ),
        Tool(
            name="list_routes",
            description="List routes from Wahoo Cloud API",
            inputSchema=load_json_schema("list_routes.json"),
        ),
        Tool(
            name="get_route",
            description="Get detailed information about a specific route",
            inputSchema=load_json_schema("get_route.json"),
        ),
        Tool(
            name="list_plans",
            description="List plans from Wahoo Cloud API",
            inputSchema=load_json_schema("list_plans.json"),
        ),
        Tool(
            name="get_plan",
            description="Get detailed information about a specific plan",
            inputSchema=load_json_schema("get_plan.json"),
        ),
        Tool(
            name="create_plan",
            description="Create a new plan in the user's library",
            inputSchema=load_json_schema("create_plan.json"),
        ),
        Tool(
            name="list_power_zones",
            description="List power zones from Wahoo Cloud API",
            inputSchema=load_json_schema("list_power_zones.json"),
        ),
        Tool(
            name="get_power_zone",
            description="Get detailed information about a specific power zone",
            inputSchema=load_json_schema("get_power_zone.json"),
        ),
    ]


async def _handle_list_workouts(
    client: WahooAPIClient, arguments: Arguments
) -> ToolResponse:
    """Handle list_workouts tool request."""
    workouts = await client.list_workouts(
        page=arguments.get("page", 1),
        per_page=arguments.get("per_page", 30),
        start_date=arguments.get("start_date"),
        end_date=arguments.get("end_date"),
    )

    if not workouts:
        return [TextContent(type="text", text="No workouts found.")]

    formatted_workouts = "\n\n".join(workout.format_summary() for workout in workouts)
    result = f"Found {len(workouts)} workouts:\n\n{formatted_workouts}"
    return [TextContent(type="text", text=result)]


async def _handle_get_workout(
    client: WahooAPIClient, arguments: Arguments
) -> ToolResponse:
    """Handle get_workout tool request."""
    workout_id = arguments["workout_id"]
    workout = await client.get_workout(workout_id)
    return [TextContent(type="text", text=workout.format_details())]


async def _handle_list_routes(
    client: WahooAPIClient, arguments: Arguments
) -> ToolResponse:
    """Handle list_routes tool request."""
    routes = await client.list_routes(external_id=arguments.get("external_id"))

    if not routes:
        return [TextContent(type="text", text="No routes found.")]

    formatted_routes = "\n\n".join(route.format_summary() for route in routes)
    result = f"Found {len(routes)} routes:\n\n{formatted_routes}"
    return [TextContent(type="text", text=result)]


async def _handle_get_route(
    client: WahooAPIClient, arguments: Arguments
) -> ToolResponse:
    """Handle get_route tool request."""
    route_id = arguments["route_id"]
    route = await client.get_route(route_id)
    return [TextContent(type="text", text=route.format_details())]


async def _handle_list_plans(
    client: WahooAPIClient, arguments: Arguments
) -> ToolResponse:
    """Handle list_plans tool request."""
    plans = await client.list_plans(external_id=arguments.get("external_id"))

    if not plans:
        return [TextContent(type="text", text="No plans found.")]

    formatted_plans = "\n\n".join(plan.format_summary() for plan in plans)
    result = f"Found {len(plans)} plans:\n\n{formatted_plans}"
    return [TextContent(type="text", text=result)]


async def _handle_get_plan(
    client: WahooAPIClient, arguments: Arguments
) -> ToolResponse:
    """Handle get_plan tool request."""
    plan_id = arguments["plan_id"]
    plan = await client.get_plan(plan_id)
    return [TextContent(type="text", text=plan.format_details())]


def _build_workout_intervals(intervals_data: list) -> list[WorkoutInterval]:
    """Build list of WorkoutInterval objects from raw data."""
    intervals = []
    for interval_data in intervals_data:
        targets = [
            WorkoutTarget(**target_data) for target_data in interval_data["targets"]
        ]

        interval = WorkoutInterval(
            duration=interval_data["duration"],
            targets=targets,
            name=interval_data.get("name"),
            interval_type=interval_data.get("interval_type", "work"),
        )
        intervals.append(interval)
    return intervals


def _format_plan_result(created_plan) -> str:
    """Format the plan creation result message."""
    result = f"""Plan created successfully!

Plan Details:
- ID: {created_plan.id}
- Name: {created_plan.name}
- External ID: {created_plan.external_id}
- User ID: {created_plan.user_id}
- Created: {created_plan.created_at}
- Updated: {created_plan.updated_at}
- File URL: {created_plan.file.url}"""

    if created_plan.description:
        result += f"\n- Description: {created_plan.description}"

    return result


async def _handle_create_plan(
    client: WahooAPIClient, arguments: Arguments
) -> ToolResponse:
    """Handle create_plan tool request."""
    plan_data = arguments["plan"]

    # Build intervals from data
    intervals = _build_workout_intervals(plan_data["intervals"])

    # Create WorkoutPlan with only essential fields to avoid API validation errors
    plan = WorkoutPlan(
        name=plan_data["name"],
        description=plan_data.get("description"),
        intervals=intervals,
        workout_type=plan_data.get("workout_type", "bike"),
        # Skip optional fields that cause Wahoo API validation errors:
        # - estimated_duration: calculated automatically from intervals
        # - estimated_tss: not accepted by API
        # - author: not accepted by API
    )

    plan_request = CreatePlanRequest(
        plan=plan,
        filename=arguments.get("filename"),
        external_id=arguments["external_id"],
        provider_updated_at=arguments["provider_updated_at"],
    )
    created_plan = await client.create_plan(plan_request)

    result = _format_plan_result(created_plan)
    return [TextContent(type="text", text=result)]


async def _handle_list_power_zones(
    client: WahooAPIClient, arguments: Arguments
) -> ToolResponse:
    """Handle list_power_zones tool request."""
    power_zones = await client.list_power_zones()

    if not power_zones:
        return [TextContent(type="text", text="No power zones found.")]

    formatted_zones = "\n\n".join(pz.format_summary() for pz in power_zones)
    result = f"Found {len(power_zones)} power zones:\n\n{formatted_zones}"
    return [TextContent(type="text", text=result)]


async def _handle_get_power_zone(
    client: WahooAPIClient, arguments: Arguments
) -> ToolResponse:
    """Handle get_power_zone tool request."""
    power_zone_id = arguments["power_zone_id"]
    power_zone = await client.get_power_zone(power_zone_id)
    return [TextContent(type="text", text=power_zone.format_details())]


# Tool handler mapping
TOOL_HANDLERS = {
    "list_workouts": _handle_list_workouts,
    "get_workout": _handle_get_workout,
    "list_routes": _handle_list_routes,
    "get_route": _handle_get_route,
    "list_plans": _handle_list_plans,
    "get_plan": _handle_get_plan,
    "create_plan": _handle_create_plan,
    "list_power_zones": _handle_list_power_zones,
    "get_power_zone": _handle_get_power_zone,
}


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Main tool dispatcher."""
    config = WahooConfig()

    # Check if tool exists
    if name not in TOOL_HANDLERS:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]

    try:
        async with WahooAPIClient(config) as client:
            handler = TOOL_HANDLERS[name]
            return await handler(client, arguments)
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
