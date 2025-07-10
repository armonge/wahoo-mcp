#!/usr/bin/env python3
"""
Pydantic models for Wahoo API data structures
"""

import json
from datetime import datetime
from enum import Enum
from typing import Any, TypedDict

from pydantic import BaseModel, Field


class WahooTarget(TypedDict):
    """TypedDict for Wahoo plan target format."""

    type: str
    low: float
    high: float


class WahooIntervalRequired(TypedDict):
    """Required fields for Wahoo plan interval format."""

    targets: list[WahooTarget]
    exit_trigger_type: str
    exit_trigger_value: int
    intensity_type: str


class WahooInterval(WahooIntervalRequired, total=False):
    """TypedDict for Wahoo plan interval format with optional fields."""

    name: str  # Optional field


class WahooHeaderRequired(TypedDict):
    """Required fields for Wahoo plan header format."""

    name: str
    description: str
    version: str
    workout_type_family: int
    workout_type_location: int
    ftp: int


class WahooHeader(WahooHeaderRequired, total=False):
    """TypedDict for Wahoo plan header format with optional fields."""

    author: str  # Optional field
    estimated_tss: float  # Optional field


class WahooPlan(TypedDict):
    """TypedDict for complete Wahoo plan format."""

    header: WahooHeader
    intervals: list[WahooInterval]


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


class RouteFile(BaseModel):
    """Route file information"""

    url: str = Field(description="URL to the route file")


class Route(BaseModel):
    """Wahoo route model matching the Cloud API schema"""

    id: int = Field(description="Unique route identifier")
    user_id: int = Field(description="User ID who owns the route")
    name: str = Field(description="Route name")
    description: str | None = Field(None, description="Route description")
    file: RouteFile = Field(description="Route file information")
    workout_type_family_id: int = Field(description="Workout type family ID")
    external_id: str | None = Field(None, description="External route ID")
    start_lat: float | None = Field(None, description="Starting latitude")
    start_lng: float | None = Field(None, description="Starting longitude")
    distance: float | None = Field(None, description="Route distance")
    ascent: float | None = Field(None, description="Route ascent")
    descent: float | None = Field(None, description="Route descent")

    def format_summary(self) -> str:
        """Format route for list display"""
        lines = [f"- ID: {self.id}", f"  Name: {self.name}"]

        if self.description:
            lines.append(f"  Description: {self.description}")
        if self.distance:
            lines.append(f"  Distance: {self.distance:.1f}")
        if self.start_lat and self.start_lng:
            lines.append(f"  Start: {self.start_lat:.6f}, {self.start_lng:.6f}")
        if self.external_id:
            lines.append(f"  External ID: {self.external_id}")

        return "\n".join(lines)

    def format_details(self) -> str:
        """Format route for detailed display"""
        details = f"""Route Details (ID: {self.id}):
- Name: {self.name}"""

        if self.description:
            details += f"\n- Description: {self.description}"

        details += f"""
- User ID: {self.user_id}
- Workout Type Family ID: {self.workout_type_family_id}"""

        if self.external_id:
            details += f"\n- External ID: {self.external_id}"
        if self.start_lat and self.start_lng:
            details += f"\n- Start Position: {self.start_lat:.6f}, {self.start_lng:.6f}"
        if self.distance:
            details += f"\n- Distance: {self.distance:.1f}"
        if self.ascent:
            details += f"\n- Ascent: {self.ascent:.1f}"
        if self.descent:
            details += f"\n- Descent: {self.descent:.1f}"

        details += f"\n- File URL: {self.file.url}"
        details += f"\n\nFull JSON:\n{json.dumps(self.model_dump(), indent=2)}"

        return details


class PlanFile(BaseModel):
    """Plan file information"""

    url: str = Field(description="URL to the plan file")


class Plan(BaseModel):
    """Wahoo plan model matching the Cloud API schema"""

    id: int = Field(description="Unique plan identifier")
    user_id: int = Field(description="User ID who owns the plan")
    name: str = Field(description="Plan name")
    description: str | None = Field(None, description="Plan description")
    file: PlanFile = Field(description="Plan file information")
    workout_type_family_id: int = Field(description="Workout type family ID")
    external_id: str | None = Field(None, description="External plan ID")
    provider_updated_at: str | None = Field(
        None, description="Provider update timestamp"
    )
    deleted: bool = Field(default=False, description="Whether the plan is deleted")

    def format_summary(self) -> str:
        """Format plan for list display"""
        lines = [f"- ID: {self.id}", f"  Name: {self.name}"]

        if self.description:
            lines.append(f"  Description: {self.description}")
        if self.external_id:
            lines.append(f"  External ID: {self.external_id}")

        lines.append(f"  Deleted: {self.deleted}")
        return "\n".join(lines)

    def format_details(self) -> str:
        """Format plan for detailed display"""
        details = f"""Plan Details (ID: {self.id}):
- Name: {self.name}"""

        if self.description:
            details += f"\n- Description: {self.description}"

        details += f"""
- User ID: {self.user_id}
- Workout Type Family ID: {self.workout_type_family_id}"""

        if self.external_id:
            details += f"\n- External ID: {self.external_id}"
        if self.provider_updated_at:
            details += f"\n- Provider Updated: {self.provider_updated_at}"

        details += f"""
- Deleted: {self.deleted}
- File URL: {self.file.url}

Full JSON:
{json.dumps(self.model_dump(), indent=2)}"""

        return details


class WorkoutTarget(BaseModel):
    """Workout target specification"""

    target_type: str = Field(
        description=(
            "Type of target: power, heart_rate, speed, pace, rpe, cadence, "
            "ftp, watts, hr, rpm (mapped to Wahoo API types)"
        )
    )
    target_value: float | None = Field(None, description="Target value")
    target_min: float | None = Field(
        None, description="Minimum target value for ranges"
    )
    target_max: float | None = Field(
        None, description="Maximum target value for ranges"
    )
    unit: str | None = Field(None, description="Unit of measurement")


class WorkoutInterval(BaseModel):
    """Individual workout interval"""

    duration: int = Field(description="Duration in seconds")
    targets: list[WorkoutTarget] = Field(
        description="List of targets for this interval"
    )
    name: str | None = Field(None, description="Name/description of the interval")
    interval_type: str = Field(
        default="work",
        description=(
            "Type of interval: work, rest, warmup, cooldown, tempo, threshold, "
            "recovery, active, or Wahoo intensity types (wu, cd, lt, map, ac, nm, ftp, "
            "recover)"
        ),
    )


class WorkoutPlan(BaseModel):
    """Complete workout plan structure"""

    name: str = Field(description="Name of the workout plan")
    description: str | None = Field(None, description="Description of the workout")
    intervals: list[WorkoutInterval] = Field(description="List of workout intervals")
    workout_type: str = Field(
        default="bike", description="Type of workout: bike, run, swim"
    )
    estimated_duration: int | None = Field(
        None, description="Estimated total duration in seconds"
    )
    estimated_tss: float | None = Field(
        None, description="Estimated Training Stress Score"
    )
    author: str | None = Field(None, description="Author of the plan")

    def _map_intensity_type(self, interval_type: str) -> str:
        """Map generic interval types to Wahoo-specific intensity types."""
        # Wahoo API expects:
        # ["active","wu","tempo","lt","map","ac","nm","ftp","cd","recover","rest"]
        intensity_mapping = {
            "warmup": "wu",
            "warm-up": "wu",
            "wu": "wu",
            "work": "active",
            "active": "active",
            "interval": "active",
            "tempo": "tempo",
            "threshold": "lt",
            "lt": "lt",
            "map": "map",
            "ac": "ac",
            "neuromuscular": "nm",
            "nm": "nm",
            "ftp": "ftp",
            "cooldown": "cd",
            "cool-down": "cd",
            "cd": "cd",
            "recovery": "recover",
            "recover": "recover",
            "rest": "rest",
        }

        # Convert to lowercase for case-insensitive matching
        interval_type_lower = interval_type.lower()
        return intensity_mapping.get(
            interval_type_lower, "active"
        )  # Default to "active"

    def _map_target_type(self, target_type: str) -> str:
        """Map generic target types to Wahoo-specific target types."""
        # Wahoo API expects:
        # ["rpm","rpe","watts","hr","speed","ftp","map","ac",
        # "nm","threshold_hr","threshold_speed","max_hr"]
        target_mapping = {
            "power": "watts",
            "watts": "watts",
            "heart_rate": "hr",
            "hr": "hr",
            "heartrate": "hr",
            "cadence": "rpm",
            "rpm": "rpm",
            "rpe": "rpe",
            "perceived_exertion": "rpe",
            "speed": "speed",
            "pace": "speed",
            "ftp": "ftp",
            "map": "map",
            "ac": "ac",
            "nm": "nm",
            "neuromuscular": "nm",
            "threshold_hr": "threshold_hr",
            "threshold_speed": "threshold_speed",
            "max_hr": "max_hr",
        }

        # Convert to lowercase for case-insensitive matching
        target_type_lower = target_type.lower()
        return target_mapping.get(target_type_lower, "watts")  # Default to "watts"

    def to_wahoo_format(self) -> WahooPlan:
        """Convert to Wahoo plan JSON format"""

        # Calculate total duration if not provided
        total_duration = self.estimated_duration
        if total_duration is None:
            total_duration = sum(interval.duration for interval in self.intervals)

        # Convert intervals to Wahoo format
        wahoo_intervals: list[WahooInterval] = []
        for interval in self.intervals:
            wahoo_interval: WahooInterval = {
                "targets": [],
                "exit_trigger_type": "time",
                "exit_trigger_value": interval.duration,
                "intensity_type": self._map_intensity_type(interval.interval_type),
            }

            # Add interval name/description if provided
            if interval.name:
                wahoo_interval["name"] = interval.name

            # Convert targets to Wahoo format
            for target in interval.targets:
                # Map target types to Wahoo-specific types
                wahoo_target_type = self._map_target_type(target.target_type)

                # Add target values based on whether it's a range or single value
                if target.target_min is not None and target.target_max is not None:
                    wahoo_target: WahooTarget = {
                        "type": wahoo_target_type,
                        "low": target.target_min,
                        "high": target.target_max,
                    }
                elif target.target_value is not None:
                    # Use value as both low and high for single values
                    wahoo_target: WahooTarget = {
                        "type": wahoo_target_type,
                        "low": target.target_value,
                        "high": target.target_value,
                    }
                else:
                    # Skip targets without valid values
                    continue

                wahoo_interval["targets"].append(wahoo_target)

            wahoo_intervals.append(wahoo_interval)

        # Build the complete Wahoo plan JSON structure
        header: WahooHeader = {
            "name": self.name,
            "description": self.description or "",
            "version": "1.0.0",
            "workout_type_family": 0,  # 0 = cycling, 1 = running
            "workout_type_location": 0,  # 0 = indoor, 1 = outdoor
            "ftp": 250,  # Default FTP value for target calculations
        }

        # Skip optional fields that cause Wahoo API validation errors:
        # - author: causes "field 'author' is not an allowed field" error
        # - estimated_tss: causes "field 'estimated_tss' is not an allowed field" error

        wahoo_plan: WahooPlan = {
            "header": header,
            "intervals": wahoo_intervals,
        }

        return wahoo_plan


class CreatePlanRequest(BaseModel):
    """Request model for creating a new plan"""

    plan: WorkoutPlan = Field(description="Complete workout plan structure")
    filename: str | None = Field(None, description="Name of the plan file")
    external_id: str = Field(description="Unique external ID for the plan")
    provider_updated_at: str = Field(
        description="External date/time the file was updated"
    )


class CreatePlanResponse(BaseModel):
    """Response model for plan creation"""

    id: int = Field(description="Unique plan identifier")
    user_id: int = Field(description="User ID who owns the plan")
    name: str = Field(description="Plan name")
    description: str | None = Field(None, description="Plan description")
    file: PlanFile = Field(description="Plan file information")
    external_id: str = Field(description="External plan ID")
    provider_updated_at: str = Field(description="Provider update timestamp")
    created_at: str = Field(description="Creation timestamp")
    updated_at: str = Field(description="Last update timestamp")


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
    critical_power: int | None = Field(None, description="Critical power")
    created_at: str = Field(description="Creation timestamp in ISO 8601 format")
    updated_at: str = Field(description="Last update timestamp in ISO 8601 format")

    def get_workout_type(self) -> WorkoutType:
        """Get the WorkoutType enum for this power zone"""
        return WorkoutType.from_id(self.workout_type_id)

    def format_summary(self) -> str:
        """Format power zone for list display"""
        workout_type = self.get_workout_type()
        lines = [
            f"- ID: {self.id}",
            f"  FTP: {self.ftp}W",
            f"  Type: {workout_type.description}",
            (
                f"  Zones: {self.zone_1}W, {self.zone_2}W, {self.zone_3}W, "
                f"{self.zone_4}W, {self.zone_5}W, {self.zone_6}W, {self.zone_7}W"
            ),
        ]

        if self.critical_power:
            lines.append(f"  Critical Power: {self.critical_power}W")

        return "\n".join(lines)

    def format_details(self) -> str:
        """Format power zone for detailed display"""
        workout_type = self.get_workout_type()
        details = f"""Power Zone Details (ID: {self.id}):
- User ID: {self.user_id}
- FTP: {self.ftp}W
- Zone Count: {self.zone_count}
- Workout Type: {workout_type.description}
- Zone 1: {self.zone_1}W
- Zone 2: {self.zone_2}W
- Zone 3: {self.zone_3}W
- Zone 4: {self.zone_4}W
- Zone 5: {self.zone_5}W
- Zone 6: {self.zone_6}W
- Zone 7: {self.zone_7}W"""

        if self.critical_power:
            details += f"\n- Critical Power: {self.critical_power}W"

        details += f"""
- Created: {self.created_at}
- Updated: {self.updated_at}

Full JSON:
{json.dumps(self.model_dump(), indent=2)}"""

        return details


class Workout(BaseModel):
    """Wahoo workout model matching the Cloud API schema"""

    id: int = Field(description="Unique workout identifier")
    starts: str = Field(description="Workout start time in ISO 8601 format")
    minutes: int = Field(description="Workout duration in minutes")
    name: str = Field(description="Workout name")
    plan_id: int | None = Field(None, description="Associated plan ID")
    route_id: int | None = Field(None, description="Associated route ID")
    workout_token: str = Field(description="Application-specific identifier")
    workout_type_id: int = Field(description="Type of workout")
    workout_summary: dict[str, Any] | None = Field(
        None, description="Workout results/summary data"
    )
    created_at: str = Field(description="Creation timestamp in ISO 8601 format")
    updated_at: str = Field(description="Last update timestamp in ISO 8601 format")

    def duration_str(self) -> str:
        """Format duration as a readable string"""
        if self.minutes < 60:  # noqa: PLR2004
            return f"{self.minutes} minutes"
        hours = self.minutes // 60  # noqa: PLR2004
        remaining_minutes = self.minutes % 60  # noqa: PLR2004
        if remaining_minutes == 0:
            return f"{hours} hour{'s' if hours != 1 else ''}"
        return f"{hours}h {remaining_minutes}m"

    def formatted_start_time(self) -> str:
        """Format start time for display"""
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

    def format_summary(self) -> str:
        """Format workout for list display"""
        workout_type = self.get_workout_type()
        lines = [
            f"- ID: {self.id}",
            f"  Name: {self.name}",
            f"  Date: {self.formatted_start_time()}",
            f"  Duration: {self.duration_str()}",
            (
                f"  Type: {workout_type.description} "
                f"({workout_type.location.value}, {workout_type.family.value})"
            ),
        ]

        if self.plan_id:
            lines.append(f"  Plan ID: {self.plan_id}")
        if self.route_id:
            lines.append(f"  Route ID: {self.route_id}")

        return "\n".join(lines)

    def format_details(self) -> str:
        """Format workout for detailed display"""
        workout_type = self.get_workout_type()
        details = f"""Workout Details (ID: {self.id}):
- Name: {self.name}
- Start Time: {self.formatted_start_time()}
- Duration: {self.duration_str()}
- Type: {workout_type.description}
- Location: {workout_type.location.value}
- Family: {workout_type.family.value}
- Workout Token: {self.workout_token}"""

        if self.plan_id:
            details += f"\n- Plan ID: {self.plan_id}"
        if self.route_id:
            details += f"\n- Route ID: {self.route_id}"

        details += f"""
- Created: {self.created_at}
- Updated: {self.updated_at}
- Has Summary: {"Yes" if self.workout_summary else "No"}

Full JSON:
{json.dumps(self.model_dump(), indent=2)}"""

        return details
