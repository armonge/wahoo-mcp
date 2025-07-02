#!/usr/bin/env python3
import os
import json
import logging
from typing import Any, Dict, List, Optional
from enum import Enum
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


class WorkoutTypeLocation(Enum):
    """Workout type locations"""

    OUTDOOR = "Outdoor"
    INDOOR = "Indoor"
    UNKNOWN = "Unknown"


class WorkoutTypeFamily(Enum):
    """Workout type families"""

    BIKING = "Biking"
    RUNNING = "Running"
    WALKING = "Walking"
    TRACK = "Track"
    TRAIL = "Trail"
    SWIMMING = "Swimming"
    SNOW_SPORT = "Snow Sport"
    SKATING = "Skating"
    WATER_SPORTS = "Water Sports"
    GYM = "Gym"
    OTHER = "Other"
    NA = "N/A"
    UNKNOWN = "Unknown"


class WorkoutType(Enum):
    """Wahoo workout types with their descriptions, locations, and families"""

    # Format: (id, description, location, family)
    BIKING = (0, "Biking", WorkoutTypeLocation.OUTDOOR, WorkoutTypeFamily.BIKING)
    RUNNING = (1, "Running", WorkoutTypeLocation.OUTDOOR, WorkoutTypeFamily.RUNNING)
    FE = (2, "Fitness Equipment", WorkoutTypeLocation.INDOOR, WorkoutTypeFamily.NA)
    RUNNING_TRACK = (
        3,
        "Running Track",
        WorkoutTypeLocation.OUTDOOR,
        WorkoutTypeFamily.TRACK,
    )
    RUNNING_TRAIL = (
        4,
        "Running Trail",
        WorkoutTypeLocation.OUTDOOR,
        WorkoutTypeFamily.TRAIL,
    )
    RUNNING_TREADMILL = (
        5,
        "Running Treadmill",
        WorkoutTypeLocation.INDOOR,
        WorkoutTypeFamily.RUNNING,
    )
    WALKING = (6, "Walking", WorkoutTypeLocation.OUTDOOR, WorkoutTypeFamily.WALKING)
    WALKING_SPEED = (
        7,
        "Speed Walking",
        WorkoutTypeLocation.OUTDOOR,
        WorkoutTypeFamily.WALKING,
    )
    WALKING_NORDIC = (
        8,
        "Nordic Walking",
        WorkoutTypeLocation.OUTDOOR,
        WorkoutTypeFamily.WALKING,
    )
    HIKING = (9, "Hiking", WorkoutTypeLocation.OUTDOOR, WorkoutTypeFamily.WALKING)
    MOUNTAINEERING = (
        10,
        "Mountaineering",
        WorkoutTypeLocation.OUTDOOR,
        WorkoutTypeFamily.WALKING,
    )
    BIKING_CYCLECROSS = (
        11,
        "Cyclocross",
        WorkoutTypeLocation.OUTDOOR,
        WorkoutTypeFamily.BIKING,
    )
    BIKING_INDOOR = (
        12,
        "Indoor Biking",
        WorkoutTypeLocation.INDOOR,
        WorkoutTypeFamily.BIKING,
    )
    BIKING_MOUNTAIN = (
        13,
        "Mountain Biking",
        WorkoutTypeLocation.OUTDOOR,
        WorkoutTypeFamily.BIKING,
    )
    BIKING_RECUMBENT = (
        14,
        "Recumbent Biking",
        WorkoutTypeLocation.OUTDOOR,
        WorkoutTypeFamily.BIKING,
    )
    BIKING_ROAD = (
        15,
        "Road Biking",
        WorkoutTypeLocation.OUTDOOR,
        WorkoutTypeFamily.BIKING,
    )
    BIKING_TRACK = (
        16,
        "Track Biking",
        WorkoutTypeLocation.OUTDOOR,
        WorkoutTypeFamily.BIKING,
    )
    BIKING_MOTOCYCLING = (
        17,
        "Motorcycling",
        WorkoutTypeLocation.OUTDOOR,
        WorkoutTypeFamily.BIKING,
    )
    FE_GENERAL = (
        18,
        "General Fitness Equipment",
        WorkoutTypeLocation.INDOOR,
        WorkoutTypeFamily.NA,
    )
    FE_TREADMILL = (
        19,
        "Fitness Equipment Treadmill",
        WorkoutTypeLocation.INDOOR,
        WorkoutTypeFamily.NA,
    )
    FE_ELLIPTICAL = (
        20,
        "Elliptical",
        WorkoutTypeLocation.INDOOR,
        WorkoutTypeFamily.GYM,
    )
    FE_BIKE = (
        21,
        "Fitness Equipment Bike",
        WorkoutTypeLocation.INDOOR,
        WorkoutTypeFamily.NA,
    )
    FE_ROWER = (22, "Rowing Machine", WorkoutTypeLocation.INDOOR, WorkoutTypeFamily.GYM)
    FE_CLIMBER = (
        23,
        "Climbing Machine",
        WorkoutTypeLocation.INDOOR,
        WorkoutTypeFamily.NA,
    )
    SWIMMING_LAP = (
        25,
        "Lap Swimming",
        WorkoutTypeLocation.INDOOR,
        WorkoutTypeFamily.SWIMMING,
    )
    SWIMMING_OPEN_WATER = (
        26,
        "Open Water Swimming",
        WorkoutTypeLocation.OUTDOOR,
        WorkoutTypeFamily.SWIMMING,
    )
    SNOWBOARDING = (
        27,
        "Snowboarding",
        WorkoutTypeLocation.OUTDOOR,
        WorkoutTypeFamily.SNOW_SPORT,
    )
    SKIING = (28, "Skiing", WorkoutTypeLocation.OUTDOOR, WorkoutTypeFamily.SNOW_SPORT)
    SKIING_DOWNHILL = (
        29,
        "Downhill Skiing",
        WorkoutTypeLocation.OUTDOOR,
        WorkoutTypeFamily.SNOW_SPORT,
    )
    SKIING_CROSS_COUNTRY = (
        30,
        "Cross Country Skiing",
        WorkoutTypeLocation.OUTDOOR,
        WorkoutTypeFamily.SNOW_SPORT,
    )
    SKATING = (31, "Skating", WorkoutTypeLocation.OUTDOOR, WorkoutTypeFamily.SKATING)
    SKATING_ICE = (
        32,
        "Ice Skating",
        WorkoutTypeLocation.INDOOR,
        WorkoutTypeFamily.SKATING,
    )
    SKATING_INLINE = (
        33,
        "Inline Skating",
        WorkoutTypeLocation.INDOOR,
        WorkoutTypeFamily.SKATING,
    )
    LONG_BOARDING = (
        34,
        "Longboarding",
        WorkoutTypeLocation.OUTDOOR,
        WorkoutTypeFamily.SKATING,
    )
    SAILING = (
        35,
        "Sailing",
        WorkoutTypeLocation.OUTDOOR,
        WorkoutTypeFamily.WATER_SPORTS,
    )
    WINDSURFING = (
        36,
        "Windsurfing",
        WorkoutTypeLocation.OUTDOOR,
        WorkoutTypeFamily.WATER_SPORTS,
    )
    CANOEING = (
        37,
        "Canoeing",
        WorkoutTypeLocation.OUTDOOR,
        WorkoutTypeFamily.WATER_SPORTS,
    )
    KAYAKING = (
        38,
        "Kayaking",
        WorkoutTypeLocation.OUTDOOR,
        WorkoutTypeFamily.WATER_SPORTS,
    )
    ROWING = (39, "Rowing", WorkoutTypeLocation.OUTDOOR, WorkoutTypeFamily.WATER_SPORTS)
    KITEBOARDING = (
        40,
        "Kiteboarding",
        WorkoutTypeLocation.OUTDOOR,
        WorkoutTypeFamily.WATER_SPORTS,
    )
    STAND_UP_PADDLE_BOARD = (
        41,
        "Stand Up Paddle Board",
        WorkoutTypeLocation.OUTDOOR,
        WorkoutTypeFamily.WATER_SPORTS,
    )
    WORKOUT = (42, "Workout", WorkoutTypeLocation.INDOOR, WorkoutTypeFamily.GYM)
    CARDIO_CLASS = (
        43,
        "Cardio Class",
        WorkoutTypeLocation.INDOOR,
        WorkoutTypeFamily.GYM,
    )
    STAIR_CLIMBER = (
        44,
        "Stair Climber",
        WorkoutTypeLocation.INDOOR,
        WorkoutTypeFamily.GYM,
    )
    WHEELCHAIR = (
        45,
        "Wheelchair",
        WorkoutTypeLocation.OUTDOOR,
        WorkoutTypeFamily.OTHER,
    )
    GOLFING = (46, "Golfing", WorkoutTypeLocation.OUTDOOR, WorkoutTypeFamily.OTHER)
    OTHER = (47, "Other", WorkoutTypeLocation.OUTDOOR, WorkoutTypeFamily.OTHER)
    BIKING_INDOOR_CYCLING_CLASS = (
        49,
        "Indoor Cycling Class",
        WorkoutTypeLocation.INDOOR,
        WorkoutTypeFamily.BIKING,
    )
    WALKING_TREADMILL = (
        56,
        "Walking Treadmill",
        WorkoutTypeLocation.INDOOR,
        WorkoutTypeFamily.WALKING,
    )
    BIKING_INDOOR_TRAINER = (
        61,
        "Indoor Trainer",
        WorkoutTypeLocation.INDOOR,
        WorkoutTypeFamily.BIKING,
    )
    MULTISPORT = (62, "Multisport", WorkoutTypeLocation.OUTDOOR, WorkoutTypeFamily.NA)
    TRANSITION = (63, "Transition", WorkoutTypeLocation.OUTDOOR, WorkoutTypeFamily.NA)
    EBIKING = (64, "E-Biking", WorkoutTypeLocation.OUTDOOR, WorkoutTypeFamily.BIKING)
    TICKR_OFFLINE = (
        65,
        "TICKR Offline",
        WorkoutTypeLocation.OUTDOOR,
        WorkoutTypeFamily.NA,
    )
    YOGA = (66, "Yoga", WorkoutTypeLocation.INDOOR, WorkoutTypeFamily.GYM)
    RUNNING_RACE = (
        67,
        "Running Race",
        WorkoutTypeLocation.OUTDOOR,
        WorkoutTypeFamily.RUNNING,
    )
    BIKING_INDOOR_VIRTUAL = (
        68,
        "Indoor Virtual Biking",
        WorkoutTypeLocation.INDOOR,
        WorkoutTypeFamily.BIKING,
    )
    MENTAL_STRENGTH = (
        69,
        "Mental Strength",
        WorkoutTypeLocation.INDOOR,
        WorkoutTypeFamily.OTHER,
    )
    HANDCYCLING = (
        70,
        "Handcycling",
        WorkoutTypeLocation.OUTDOOR,
        WorkoutTypeFamily.BIKING,
    )
    RUNNING_INDOOR_VIRTUAL = (
        71,
        "Indoor Virtual Running",
        WorkoutTypeLocation.INDOOR,
        WorkoutTypeFamily.RUNNING,
    )
    UNKNOWN = (255, "Unknown", WorkoutTypeLocation.UNKNOWN, WorkoutTypeFamily.UNKNOWN)

    def __init__(
        self,
        id: int,
        description: str,
        location: WorkoutTypeLocation,
        family: WorkoutTypeFamily,
    ):
        self.id = id
        self.description = description
        self.location = location
        self.family = family

    @classmethod
    def from_id(cls, workout_type_id: int) -> "WorkoutType":
        """Get WorkoutType from ID, returns UNKNOWN if not found"""
        for workout_type in cls:
            if workout_type.id == workout_type_id:
                return workout_type
        return cls.UNKNOWN

    def __str__(self) -> str:
        return self.description


class WahooConfig(BaseModel):
    base_url: str = Field(
        default="https://api.wahooligan.com", description="Base URL for Wahoo API"
    )


class RouteFile(BaseModel):
    """Route file information"""

    url: str = Field(description="URL to the route file")


class Route(BaseModel):
    """Wahoo route model matching the Cloud API schema"""

    id: int = Field(description="Unique route identifier")
    user_id: int = Field(description="User ID who owns the route")
    name: str = Field(description="Route name")
    description: Optional[str] = Field(None, description="Route description")
    file: RouteFile = Field(description="Route file information")
    workout_type_family_id: int = Field(description="Workout type family ID")
    external_id: Optional[str] = Field(None, description="External route ID")
    start_lat: Optional[float] = Field(None, description="Starting latitude")
    start_lng: Optional[float] = Field(None, description="Starting longitude")
    distance: Optional[float] = Field(None, description="Route distance")
    ascent: Optional[float] = Field(None, description="Route ascent")
    descent: Optional[float] = Field(None, description="Route descent")


class PlanFile(BaseModel):
    """Plan file information"""

    url: str = Field(description="URL to the plan file")


class Plan(BaseModel):
    """Wahoo plan model matching the Cloud API schema"""

    id: int = Field(description="Unique plan identifier")
    user_id: int = Field(description="User ID who owns the plan")
    name: str = Field(description="Plan name")
    description: Optional[str] = Field(None, description="Plan description")
    file: PlanFile = Field(description="Plan file information")
    workout_type_family_id: int = Field(description="Workout type family ID")
    external_id: Optional[str] = Field(None, description="External plan ID")
    provider_updated_at: Optional[str] = Field(
        None, description="Provider update timestamp"
    )
    deleted: bool = Field(default=False, description="Whether the plan is deleted")


class PowerZone(BaseModel):
    """Wahoo power zone model matching the Cloud API schema"""

    id: int = Field(description="Unique power zone identifier")
    user_id: int = Field(description="User ID who owns the power zones")
    zone_1: int = Field(description="Zone 1 power value")
    zone_2: int = Field(description="Zone 2 power value")
    zone_3: int = Field(description="Zone 3 power value")
    zone_4: int = Field(description="Zone 4 power value")
    zone_5: int = Field(description="Zone 5 power value")
    zone_6: int = Field(description="Zone 6 power value")
    zone_7: int = Field(description="Zone 7 power value")
    ftp: int = Field(description="Functional Threshold Power")
    zone_count: int = Field(description="Number of zones")
    workout_type_id: int = Field(description="Workout type ID")
    workout_type_family_id: int = Field(description="Workout type family ID")
    workout_type_location_id: int = Field(description="Workout type location ID")
    critical_power: Optional[int] = Field(None, description="Critical power")
    created_at: str = Field(description="Creation timestamp in ISO 8601 format")
    updated_at: str = Field(description="Last update timestamp in ISO 8601 format")

    def get_workout_type(self) -> WorkoutType:
        """Get the WorkoutType enum for this power zone"""
        return WorkoutType.from_id(self.workout_type_id)


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
    workout_summary: Optional[Dict[str, Any]] = Field(
        None, description="Workout results/summary data"
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

    def get_workout_type(self) -> WorkoutType:
        """Get the WorkoutType enum for this workout"""
        return WorkoutType.from_id(self.workout_type_id)

    def workout_type_description(self) -> str:
        """Get the human-readable workout type description"""
        return str(self.get_workout_type())


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

    async def list_routes(self, external_id: Optional[str] = None) -> List[Route]:
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
        routes_data = data.get("routes", [])

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
            raise ValueError(f"Invalid route data received from API: {e}")

    async def list_plans(self, external_id: Optional[str] = None) -> List[Plan]:
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
        plans_data = data.get("plans", [])

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
            raise ValueError(f"Invalid plan data received from API: {e}")

    async def list_power_zones(self) -> List[PowerZone]:
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
        power_zones_data = data.get("power_zones", [])

        # Convert each power zone dict to PowerZone object
        power_zones = []
        for power_zone_dict in power_zones_data:
            try:
                power_zone = PowerZone(**power_zone_dict)
                power_zones.append(power_zone)
            except Exception as e:
                logger.warning(
                    f"Failed to parse power zone {power_zone_dict.get('id', 'unknown')}: {e}"
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
            raise ValueError(f"Invalid power zone data received from API: {e}")


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
                    workout_type = workout.get_workout_type()
                    result += f"- ID: {workout.id}\n"
                    result += f"  Name: {workout.name}\n"
                    result += f"  Date: {workout.formatted_start_time()}\n"
                    result += f"  Duration: {workout.duration_str()}\n"
                    result += f"  Type: {workout_type.description} ({workout_type.location.value}, {workout_type.family.value})\n"
                    if workout.plan_id:
                        result += f"  Plan ID: {workout.plan_id}\n"
                    if workout.route_id:
                        result += f"  Route ID: {workout.route_id}\n"
                    result += "\n"

                return [TextContent(type="text", text=result)]

            elif name == "get_workout":
                workout_id = arguments["workout_id"]
                workout = await client.get_workout(workout_id)

                workout_type = workout.get_workout_type()
                result = f"Workout Details (ID: {workout.id}):\n"
                result += f"- Name: {workout.name}\n"
                result += f"- Start Time: {workout.formatted_start_time()}\n"
                result += f"- Duration: {workout.duration_str()}\n"
                result += f"- Type: {workout_type.description}\n"
                result += f"- Location: {workout_type.location.value}\n"
                result += f"- Family: {workout_type.family.value}\n"
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

            elif name == "list_routes":
                routes = await client.list_routes(
                    external_id=arguments.get("external_id")
                )

                if not routes:
                    return [TextContent(type="text", text="No routes found.")]

                result = f"Found {len(routes)} routes:\n\n"
                for route in routes:
                    result += f"- ID: {route.id}\n"
                    result += f"  Name: {route.name}\n"
                    if route.description:
                        result += f"  Description: {route.description}\n"
                    if route.distance:
                        result += f"  Distance: {route.distance:.1f}\n"
                    if route.start_lat and route.start_lng:
                        result += (
                            f"  Start: {route.start_lat:.6f}, {route.start_lng:.6f}\n"
                        )
                    if route.external_id:
                        result += f"  External ID: {route.external_id}\n"
                    result += "\n"

                return [TextContent(type="text", text=result)]

            elif name == "get_route":
                route_id = arguments["route_id"]
                route = await client.get_route(route_id)

                result = f"Route Details (ID: {route.id}):\n"
                result += f"- Name: {route.name}\n"
                if route.description:
                    result += f"- Description: {route.description}\n"
                result += f"- User ID: {route.user_id}\n"
                result += f"- Workout Type Family ID: {route.workout_type_family_id}\n"
                if route.external_id:
                    result += f"- External ID: {route.external_id}\n"
                if route.start_lat and route.start_lng:
                    result += f"- Start Position: {route.start_lat:.6f}, {route.start_lng:.6f}\n"
                if route.distance:
                    result += f"- Distance: {route.distance:.1f}\n"
                if route.ascent:
                    result += f"- Ascent: {route.ascent:.1f}\n"
                if route.descent:
                    result += f"- Descent: {route.descent:.1f}\n"
                result += f"- File URL: {route.file.url}\n"

                result += f"\nFull JSON:\n{json.dumps(route.model_dump(), indent=2)}"

                return [TextContent(type="text", text=result)]

            elif name == "list_plans":
                plans = await client.list_plans(
                    external_id=arguments.get("external_id")
                )

                if not plans:
                    return [TextContent(type="text", text="No plans found.")]

                result = f"Found {len(plans)} plans:\n\n"
                for plan in plans:
                    result += f"- ID: {plan.id}\n"
                    result += f"  Name: {plan.name}\n"
                    if plan.description:
                        result += f"  Description: {plan.description}\n"
                    if plan.external_id:
                        result += f"  External ID: {plan.external_id}\n"
                    result += f"  Deleted: {plan.deleted}\n"
                    result += "\n"

                return [TextContent(type="text", text=result)]

            elif name == "get_plan":
                plan_id = arguments["plan_id"]
                plan = await client.get_plan(plan_id)

                result = f"Plan Details (ID: {plan.id}):\n"
                result += f"- Name: {plan.name}\n"
                if plan.description:
                    result += f"- Description: {plan.description}\n"
                result += f"- User ID: {plan.user_id}\n"
                result += f"- Workout Type Family ID: {plan.workout_type_family_id}\n"
                if plan.external_id:
                    result += f"- External ID: {plan.external_id}\n"
                if plan.provider_updated_at:
                    result += f"- Provider Updated: {plan.provider_updated_at}\n"
                result += f"- Deleted: {plan.deleted}\n"
                result += f"- File URL: {plan.file.url}\n"

                result += f"\nFull JSON:\n{json.dumps(plan.model_dump(), indent=2)}"

                return [TextContent(type="text", text=result)]

            elif name == "list_power_zones":
                power_zones = await client.list_power_zones()

                if not power_zones:
                    return [TextContent(type="text", text="No power zones found.")]

                result = f"Found {len(power_zones)} power zones:\n\n"
                for pz in power_zones:
                    workout_type = pz.get_workout_type()
                    result += f"- ID: {pz.id}\n"
                    result += f"  FTP: {pz.ftp}W\n"
                    result += f"  Type: {workout_type.description}\n"
                    result += f"  Zones: {pz.zone_1}W, {pz.zone_2}W, {pz.zone_3}W, {pz.zone_4}W, {pz.zone_5}W, {pz.zone_6}W, {pz.zone_7}W\n"
                    if pz.critical_power:
                        result += f"  Critical Power: {pz.critical_power}W\n"
                    result += "\n"

                return [TextContent(type="text", text=result)]

            elif name == "get_power_zone":
                power_zone_id = arguments["power_zone_id"]
                pz = await client.get_power_zone(power_zone_id)

                workout_type = pz.get_workout_type()
                result = f"Power Zone Details (ID: {pz.id}):\n"
                result += f"- User ID: {pz.user_id}\n"
                result += f"- FTP: {pz.ftp}W\n"
                result += f"- Zone Count: {pz.zone_count}\n"
                result += f"- Workout Type: {workout_type.description}\n"
                result += f"- Zone 1: {pz.zone_1}W\n"
                result += f"- Zone 2: {pz.zone_2}W\n"
                result += f"- Zone 3: {pz.zone_3}W\n"
                result += f"- Zone 4: {pz.zone_4}W\n"
                result += f"- Zone 5: {pz.zone_5}W\n"
                result += f"- Zone 6: {pz.zone_6}W\n"
                result += f"- Zone 7: {pz.zone_7}W\n"
                if pz.critical_power:
                    result += f"- Critical Power: {pz.critical_power}W\n"
                result += f"- Created: {pz.created_at}\n"
                result += f"- Updated: {pz.updated_at}\n"

                result += f"\nFull JSON:\n{json.dumps(pz.model_dump(), indent=2)}"

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
