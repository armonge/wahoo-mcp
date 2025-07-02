import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from src.server import WahooAPIClient, WahooConfig


@pytest.fixture
def wahoo_config():
    return WahooConfig(access_token="test_token")


@pytest.fixture
def mock_workouts_response():
    return {
        "workouts": [
            {
                "id": 1,
                "name": "Morning Run",
                "starts": "2024-01-15T07:00:00.000Z",
                "minutes": 45,
                "workout_type_id": 1,
            },
            {
                "id": 2,
                "name": "Evening Ride",
                "starts": "2024-01-15T18:00:00.000Z",
                "minutes": 60,
                "workout_type_id": 2,
            },
        ]
    }


@pytest.fixture
def mock_workout_detail():
    return {
        "id": 1,
        "name": "Morning Run",
        "starts": "2024-01-15T07:00:00.000Z",
        "minutes": 45,
        "workout_type_id": 1,
        "created_at": "2024-01-15T08:00:00.000Z",
        "updated_at": "2024-01-15T08:00:00.000Z",
    }


class TestWahooAPIClient:
    @pytest.mark.asyncio
    async def test_list_workouts(self, wahoo_config, mock_workouts_response):
        async with WahooAPIClient(wahoo_config) as client:
            with patch.object(client.client, "get") as mock_get:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = mock_workouts_response
                mock_response.raise_for_status.return_value = None
                mock_get.return_value = mock_response

                workouts = await client.list_workouts()

                assert len(workouts) == 2
                assert workouts[0]["name"] == "Morning Run"
                mock_get.assert_called_once_with(
                    "/v1/workouts", params={"page": 1, "per_page": 30}
                )

    @pytest.mark.asyncio
    async def test_list_workouts_with_filters(
        self, wahoo_config, mock_workouts_response
    ):
        async with WahooAPIClient(wahoo_config) as client:
            with patch.object(client.client, "get") as mock_get:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = mock_workouts_response
                mock_response.raise_for_status.return_value = None
                mock_get.return_value = mock_response

                await client.list_workouts(
                    page=2, per_page=50, start_date="2024-01-01", end_date="2024-01-31"
                )

                mock_get.assert_called_once_with(
                    "/v1/workouts",
                    params={
                        "page": 2,
                        "per_page": 50,
                        "created_after": "2024-01-01",
                        "created_before": "2024-01-31",
                    },
                )

    @pytest.mark.asyncio
    async def test_get_workout(self, wahoo_config, mock_workout_detail):
        async with WahooAPIClient(wahoo_config) as client:
            with patch.object(client.client, "get") as mock_get:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = mock_workout_detail
                mock_response.raise_for_status.return_value = None
                mock_get.return_value = mock_response

                workout = await client.get_workout(1)

                assert workout["id"] == 1
                assert workout["name"] == "Morning Run"
                mock_get.assert_called_once_with("/v1/workouts/1")


class TestMCPTools:
    @pytest.mark.asyncio
    async def test_list_tools(self):
        # The list_tools decorator creates a handler, we need to call it directly
        from src.server import list_tools

        tools = await list_tools()
        assert len(tools) == 2
        assert tools[0].name == "list_workouts"
        assert tools[1].name == "get_workout"

    @pytest.mark.asyncio
    async def test_call_tool_list_workouts(self, mock_workouts_response):
        with patch.dict("os.environ", {"WAHOO_ACCESS_TOKEN": "test_token"}):
            with patch(
                "src.server.WahooAPIClient.list_workouts", new_callable=AsyncMock
            ) as mock_list:
                mock_list.return_value = mock_workouts_response["workouts"]

                from src.server import call_tool

                result = await call_tool("list_workouts", {})

                assert len(result) == 1
                assert "Found 2 workouts" in result[0].text
                assert "Morning Run" in result[0].text
                assert "Evening Ride" in result[0].text

    @pytest.mark.asyncio
    async def test_call_tool_get_workout(self, mock_workout_detail):
        with patch.dict("os.environ", {"WAHOO_ACCESS_TOKEN": "test_token"}):
            with patch(
                "src.server.WahooAPIClient.get_workout", new_callable=AsyncMock
            ) as mock_get:
                mock_get.return_value = mock_workout_detail

                from src.server import call_tool

                result = await call_tool("get_workout", {"workout_id": 1})

                assert len(result) == 1
                assert "Workout Details (ID: 1)" in result[0].text
                assert "Morning Run" in result[0].text
                assert "45 minutes" in result[0].text

    @pytest.mark.asyncio
    async def test_call_tool_no_token(self):
        with patch.dict("os.environ", {}, clear=True):
            from src.server import call_tool

            result = await call_tool("list_workouts", {})

            assert len(result) == 1
            assert "WAHOO_ACCESS_TOKEN environment variable not set" in result[0].text

    @pytest.mark.asyncio
    async def test_call_tool_unknown_tool(self):
        with patch.dict("os.environ", {"WAHOO_ACCESS_TOKEN": "test_token"}):
            from src.server import call_tool

            result = await call_tool("unknown_tool", {})

            assert len(result) == 1
            assert "Unknown tool: unknown_tool" in result[0].text
