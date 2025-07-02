#!/usr/bin/env python3
import os
import json
from typing import Any, Dict, List, Optional
import httpx
from pydantic import BaseModel, Field
from mcp.server import Server
from mcp.types import Tool, TextContent
from mcp.server.stdio import stdio_server
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


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
    def __init__(self, config: WahooConfig):
        self.config = config
        self.client = httpx.AsyncClient(
            base_url=config.base_url,
            headers={
                "Authorization": f"Bearer {config.access_token}",
                "Content-Type": "application/json",
            }
            if config.access_token
            else {},
        )

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
        params = {"page": page, "per_page": per_page}
        if start_date:
            params["created_after"] = start_date
        if end_date:
            params["created_before"] = end_date

        response = await self.client.get("/v1/workouts", params=params)
        response.raise_for_status()
        data = response.json()
        return data.get("workouts", [])

    async def get_workout(self, workout_id: int) -> Dict[str, Any]:
        response = await self.client.get(f"/v1/workouts/{workout_id}")
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
    access_token = os.getenv("WAHOO_ACCESS_TOKEN")
    if not access_token:
        return [
            TextContent(
                type="text",
                text="Error: WAHOO_ACCESS_TOKEN environment variable not set. Please set it with your Wahoo API access token.",
            )
        ]

    config = WahooConfig(access_token=access_token)

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
