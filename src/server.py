#!/usr/bin/env python3
import logging
import os
from typing import Any

import httpx
from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool
from pydantic import BaseModel, Field

from .fit_analysis import (
    FitFileAnalyzer,
    compress_html,
    enhance_workout_with_fit_analysis,
    format_fit_analysis,
    html_to_base64,
)
from .models import Plan, PowerZone, Route, Workout
from .token_store import TokenStore

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

    async def get_workout(
        self, workout_id: int, include_fit_analysis: bool = False
    ) -> Workout:
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
            workout = Workout(**workout_dict)

            # Enhance with FIT analysis if requested
            if include_fit_analysis:
                enhanced_data = await enhance_workout_with_fit_analysis(workout_dict)
                # Store the FIT analysis data in the workout object for later formatting
                if "fit_analysis" in enhanced_data:
                    workout.fit_analysis = enhanced_data["fit_analysis"]

            return workout
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
        if response.status_code == 401:
            logger.info("Got 401, attempting to refresh token")
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
        if response.status_code == 401:
            logger.info("Got 401, attempting to refresh token")
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
        if response.status_code == 401:
            logger.info("Got 401, attempting to refresh token")
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
        if response.status_code == 401:
            logger.info("Got 401, attempting to refresh token")
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

    async def list_power_zones(self) -> list[PowerZone]:
        await self._ensure_valid_token()

        response = await self.client.get("/v1/power_zones")

        # Handle 401 by refreshing token and retrying once
        if response.status_code == 401:
            logger.info("Got 401, attempting to refresh token")
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
        if response.status_code == 401:
            logger.info("Got 401, attempting to refresh token")
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


app = Server("wahoo-mcp")


@app.list_tools()
async def list_tools() -> list[Tool]:
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
                        "description": (
                            "Filter workouts created after this date (ISO 8601 format)"
                        ),
                    },
                    "end_date": {
                        "type": "string",
                        "description": (
                            "Filter workouts created before this date (ISO 8601 format)"
                        ),
                    },
                },
            },
        ),
        Tool(
            name="get_workout",
            description="Get detailed workout information with optional FIT analysis",
            inputSchema={
                "type": "object",
                "properties": {
                    "workout_id": {
                        "type": "integer",
                        "description": "The ID of the workout to retrieve",
                    },
                    "include_fit_analysis": {
                        "type": "boolean",
                        "description": "Include FIT file analysis (GPS, HR, power)",
                        "default": True,
                    },
                },
                "required": ["workout_id"],
            },
        ),
        Tool(
            name="list_routes",
            description="List routes from Wahoo Cloud API",
            inputSchema={
                "type": "object",
                "properties": {
                    "external_id": {
                        "type": "string",
                        "description": "Filter routes by external ID",
                    },
                },
            },
        ),
        Tool(
            name="get_route",
            description="Get detailed information about a specific route",
            inputSchema={
                "type": "object",
                "properties": {
                    "route_id": {
                        "type": "integer",
                        "description": "The ID of the route to retrieve",
                    }
                },
                "required": ["route_id"],
            },
        ),
        Tool(
            name="list_plans",
            description="List plans from Wahoo Cloud API",
            inputSchema={
                "type": "object",
                "properties": {
                    "external_id": {
                        "type": "string",
                        "description": "Filter plans by external ID",
                    },
                },
            },
        ),
        Tool(
            name="get_plan",
            description="Get detailed information about a specific plan",
            inputSchema={
                "type": "object",
                "properties": {
                    "plan_id": {
                        "type": "integer",
                        "description": "The ID of the plan to retrieve",
                    }
                },
                "required": ["plan_id"],
            },
        ),
        Tool(
            name="list_power_zones",
            description="List power zones from Wahoo Cloud API",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="get_power_zone",
            description="Get detailed information about a specific power zone",
            inputSchema={
                "type": "object",
                "properties": {
                    "power_zone_id": {
                        "type": "integer",
                        "description": "The ID of the power zone to retrieve",
                    }
                },
                "required": ["power_zone_id"],
            },
        ),
        Tool(
            name="generate_workout_visualizations",
            description="Generate interactive HTML visualizations for workout FIT data",
            inputSchema={
                "type": "object",
                "properties": {
                    "workout_id": {
                        "type": "integer",
                        "description": "The ID of the workout to visualize",
                    },
                    "include_route_map": {
                        "type": "boolean",
                        "description": "Generate interactive route map with elevation",
                        "default": True,
                    },
                    "include_elevation_chart": {
                        "type": "boolean",
                        "description": "Generate elevation profile and HR chart",
                        "default": True,
                    },
                    "optimize_size": {
                        "type": "boolean",
                        "description": "Optimize artifact size by reducing data points",
                        "default": True,
                    },
                    "max_artifacts": {
                        "type": "integer",
                        "description": "Maximum number of artifacts to return (1 or 2)",
                        "default": 2,
                        "minimum": 1,
                        "maximum": 2,
                    },
                },
                "required": ["workout_id"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
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

                formatted_workouts = "\n\n".join(
                    workout.format_summary() for workout in workouts
                )
                result = f"Found {len(workouts)} workouts:\n\n{formatted_workouts}"
                return [TextContent(type="text", text=result)]

            elif name == "get_workout":
                workout_id = arguments["workout_id"]
                include_fit = arguments.get(
                    "include_fit_analysis", True
                )  # Default to True
                workout = await client.get_workout(
                    workout_id, include_fit_analysis=include_fit
                )

                # Format FIT analysis if available
                fit_analysis_text = ""
                if hasattr(workout, "fit_analysis") and workout.fit_analysis:
                    fit_analysis_text = format_fit_analysis(workout.fit_analysis)

                return [
                    TextContent(
                        type="text",
                        text=workout.format_details(
                            include_fit_analysis=fit_analysis_text
                        ),
                    )
                ]

            elif name == "list_routes":
                routes = await client.list_routes(
                    external_id=arguments.get("external_id")
                )

                if not routes:
                    return [TextContent(type="text", text="No routes found.")]

                formatted_routes = "\n\n".join(
                    route.format_summary() for route in routes
                )
                result = f"Found {len(routes)} routes:\n\n{formatted_routes}"
                return [TextContent(type="text", text=result)]

            elif name == "get_route":
                route_id = arguments["route_id"]
                route = await client.get_route(route_id)
                return [TextContent(type="text", text=route.format_details())]

            elif name == "list_plans":
                plans = await client.list_plans(
                    external_id=arguments.get("external_id")
                )

                if not plans:
                    return [TextContent(type="text", text="No plans found.")]

                formatted_plans = "\n\n".join(plan.format_summary() for plan in plans)
                result = f"Found {len(plans)} plans:\n\n{formatted_plans}"
                return [TextContent(type="text", text=result)]

            elif name == "get_plan":
                plan_id = arguments["plan_id"]
                plan = await client.get_plan(plan_id)
                return [TextContent(type="text", text=plan.format_details())]

            elif name == "list_power_zones":
                power_zones = await client.list_power_zones()

                if not power_zones:
                    return [TextContent(type="text", text="No power zones found.")]

                formatted_zones = "\n\n".join(pz.format_summary() for pz in power_zones)
                result = f"Found {len(power_zones)} power zones:\n\n{formatted_zones}"
                return [TextContent(type="text", text=result)]

            elif name == "get_power_zone":
                power_zone_id = arguments["power_zone_id"]
                power_zone = await client.get_power_zone(power_zone_id)
                return [TextContent(type="text", text=power_zone.format_details())]

            elif name == "generate_workout_visualizations":
                workout_id = arguments["workout_id"]
                include_route = arguments.get("include_route_map", True)
                include_elevation = arguments.get("include_elevation_chart", True)
                optimize_size = arguments.get("optimize_size", True)
                max_artifacts = arguments.get("max_artifacts", 2)

                # If max_artifacts is 1, prioritize route map over elevation chart
                if max_artifacts == 1:
                    if include_route and include_elevation:
                        include_elevation = False  # Prioritize route map

                # Get workout data to extract FIT file URL
                workout = await client.get_workout(workout_id)
                workout_dict = workout.model_dump()

                # Check if workout has FIT file URL
                fit_url = None
                if workout_dict.get("workout_summary"):
                    if isinstance(workout_dict["workout_summary"], dict):
                        fit_url = (
                            workout_dict["workout_summary"].get("file", {}).get("url")
                        )

                if not fit_url:
                    return [
                        TextContent(
                            type="text",
                            text=f"❌ No FIT file available for workout {workout_id}. "
                            "Visualizations require GPS/sensor data from FIT files.",
                        )
                    ]

                # Create analyzer and parse FIT file
                analyzer = FitFileAnalyzer(fit_url)
                success = await analyzer.download_and_parse()

                if not success:
                    return [
                        TextContent(
                            type="text",
                            text="❌ Failed to download or parse FIT file from URL",
                        )
                    ]

                if not analyzer.records:
                    return [
                        TextContent(
                            type="text",
                            text="❌ No GPS data found in FIT file. "
                            "Visualizations require GPS coordinates.",
                        )
                    ]

                # Generate visualizations
                result_data = {
                    "workout_id": workout_id,
                    "ready_for_artifacts": True,
                    "artifacts": [],
                    "metadata": {
                        "gps_points": len(analyzer.records),
                        "optimized": optimize_size,
                        "original_gps_points": len(analyzer.records),
                    },
                }

                # Add route map if requested
                if include_route:
                    route_map = analyzer.create_route_map()
                    if route_map:
                        map_html = route_map._repr_html_()

                        # Compress the HTML
                        compressed_html = compress_html(map_html)

                        if optimize_size:
                            # Test both compressed and base64 - use the smaller one
                            base64_content = html_to_base64(map_html)
                            if len(base64_content) < len(compressed_html):
                                content = base64_content
                                content_type = "text/html;base64"
                            else:
                                content = compressed_html
                                content_type = "text/html;compressed"
                        else:
                            content = compressed_html
                            content_type = "text/html"

                        result_data["artifacts"].append(
                            {
                                "id": f"route_map_{workout_id}",
                                "type": content_type,
                                "title": f"Route Map - Workout {workout_id}",
                                "content": content,
                            }
                        )

                # Add elevation chart if requested
                if include_elevation:
                    elevation_chart = analyzer.create_elevation_chart()
                    if elevation_chart:
                        # Use CDN for Plotly to reduce size
                        if optimize_size:
                            # Use minimal Plotly config for smaller charts
                            chart_html = elevation_chart.to_html(
                                include_plotlyjs="cdn",
                                config={"displayModeBar": False, "staticPlot": True},
                            )
                        else:
                            chart_html = elevation_chart.to_html(include_plotlyjs="cdn")

                        # Compress the HTML
                        compressed_html = compress_html(chart_html)

                        if optimize_size:
                            # Test both compressed and base64 - use the smaller one
                            base64_content = html_to_base64(chart_html)
                            if len(base64_content) < len(compressed_html):
                                content = base64_content
                                content_type = "text/html;base64"
                            else:
                                content = compressed_html
                                content_type = "text/html;compressed"
                        else:
                            content = compressed_html
                            content_type = "text/html"

                        result_data["artifacts"].append(
                            {
                                "id": f"elevation_chart_{workout_id}",
                                "type": content_type,
                                "title": f"Elevation Profile - Workout {workout_id}",
                                "content": content,
                            }
                        )

                # Add summary statistics to metadata
                summary = analyzer.get_workout_summary()
                if summary:
                    result_data["metadata"].update(
                        {
                            "total_distance_km": summary.get("total_distance_km"),
                            "elevation_gain_m": summary.get("elevation_gain_m"),
                            "max_elevation_m": summary.get("max_elevation_m"),
                            "min_elevation_m": summary.get("min_elevation_m"),
                            "avg_heart_rate": summary.get("avg_heart_rate"),
                            "max_heart_rate": summary.get("max_heart_rate"),
                            "avg_power": summary.get("avg_power"),
                            "max_power": summary.get("max_power"),
                            "avg_speed_kmh": summary.get("avg_speed_kmh"),
                            "max_speed_kmh": summary.get("max_speed_kmh"),
                        }
                    )

                import json

                return [
                    TextContent(
                        type="text", text=json.dumps(result_data, indent=2, default=str)
                    )
                ]

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
