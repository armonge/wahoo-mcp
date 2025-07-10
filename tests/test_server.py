import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models import (
    CreatePlanRequest,
    Workout,
    WorkoutInterval,
    WorkoutPlan,
    WorkoutTarget,
)
from src.server import WahooAPIClient, WahooConfig, call_tool, list_tools
from src.token_store import TokenData, TokenStore


@pytest.fixture
def wahoo_config():
    return WahooConfig()


@pytest.fixture
def temp_token_file(tmp_path):
    """Create a temporary token file with test data"""
    token_file = tmp_path / "test_token.json"
    token_data = {
        "access_token": "test_token",
        "refresh_token": "test_refresh_token",
        "code_verifier": "test_verifier",
        "expires_at": time.time() + 7200,
        "token_type": "Bearer",
    }
    token_file.write_text(json.dumps(token_data))
    return str(token_file)


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
                "workout_token": "token_1",
                "plan_id": None,
                "route_id": None,
                "workout_summary": None,
                "created_at": "2024-01-15T08:00:00.000Z",
                "updated_at": "2024-01-15T08:00:00.000Z",
            },
            {
                "id": 2,
                "name": "Evening Ride",
                "starts": "2024-01-15T18:00:00.000Z",
                "minutes": 60,
                "workout_type_id": 2,
                "workout_token": "token_2",
                "plan_id": 123,
                "route_id": 456,
                "workout_summary": None,
                "created_at": "2024-01-15T19:00:00.000Z",
                "updated_at": "2024-01-15T19:00:00.000Z",
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
        "workout_token": "token_1",
        "plan_id": None,
        "route_id": None,
        "workout_summary": None,
        "created_at": "2024-01-15T08:00:00.000Z",
        "updated_at": "2024-01-15T08:00:00.000Z",
    }


@pytest.fixture
def mock_routes_response():
    return {
        "routes": [
            {
                "id": 1,
                "user_id": 123,
                "name": "Mountain Loop",
                "description": "A challenging mountain route",
                "file": {"url": "https://example.com/route1.fit"},
                "workout_type_family_id": 0,
                "external_id": "route_001",
                "start_lat": 37.7749,
                "start_lng": -122.4194,
                "distance": 25.5,
                "ascent": 500.0,
                "descent": 450.0,
            }
        ]
    }


@pytest.fixture
def mock_route_detail():
    return {
        "id": 1,
        "user_id": 123,
        "name": "Mountain Loop",
        "description": "A challenging mountain route",
        "file": {"url": "https://example.com/route1.fit"},
        "workout_type_family_id": 0,
        "external_id": "route_001",
        "start_lat": 37.7749,
        "start_lng": -122.4194,
        "distance": 25.5,
        "ascent": 500.0,
        "descent": 450.0,
    }


@pytest.fixture
def mock_plans_response():
    return {
        "plans": [
            {
                "id": 1,
                "user_id": 123,
                "name": "Training Plan A",
                "description": "Basic training plan",
                "file": {"url": "https://example.com/plan1.json"},
                "workout_type_family_id": 0,
                "external_id": "plan_001",
                "provider_updated_at": "2024-01-15T10:00:00.000Z",
                "deleted": False,
            }
        ]
    }


@pytest.fixture
def mock_plan_detail():
    return {
        "id": 1,
        "user_id": 123,
        "name": "Training Plan A",
        "description": "Basic training plan",
        "file": {"url": "https://example.com/plan1.json"},
        "workout_type_family_id": 0,
        "external_id": "plan_001",
        "provider_updated_at": "2024-01-15T10:00:00.000Z",
        "deleted": False,
    }


@pytest.fixture
def mock_power_zones_response():
    return {
        "power_zones": [
            {
                "id": 1,
                "user_id": 123,
                "zone_1": 100,
                "zone_2": 150,
                "zone_3": 200,
                "zone_4": 250,
                "zone_5": 300,
                "zone_6": 350,
                "zone_7": 400,
                "ftp": 250,
                "zone_count": 7,
                "workout_type_id": 0,
                "workout_type_family_id": 0,
                "workout_type_location_id": 0,
                "critical_power": 275,
                "created_at": "2024-01-15T12:00:00.000Z",
                "updated_at": "2024-01-15T12:00:00.000Z",
            }
        ]
    }


@pytest.fixture
def mock_power_zone_detail():
    return {
        "id": 1,
        "user_id": 123,
        "zone_1": 100,
        "zone_2": 150,
        "zone_3": 200,
        "zone_4": 250,
        "zone_5": 300,
        "zone_6": 350,
        "zone_7": 400,
        "ftp": 250,
        "zone_count": 7,
        "workout_type_id": 0,
        "workout_type_family_id": 0,
        "workout_type_location_id": 0,
        "critical_power": 275,
        "created_at": "2024-01-15T12:00:00.000Z",
        "updated_at": "2024-01-15T12:00:00.000Z",
    }


class TestWahooAPIClient:
    @pytest.mark.asyncio
    async def test_list_workouts(
        self,
        wahoo_config,
        mock_workouts_response,
        temp_token_file,
        monkeypatch,
        httpx_mock,
    ):
        monkeypatch.setenv("WAHOO_TOKEN_FILE", temp_token_file)

        # Mock the API response
        httpx_mock.add_response(
            method="GET",
            url="https://api.wahooligan.com/v1/workouts?page=1&per_page=30",
            json=mock_workouts_response,
            status_code=200,
        )

        async with WahooAPIClient(wahoo_config) as client:
            workouts = await client.list_workouts()

            assert len(workouts) == 2
            assert workouts[0].name == "Morning Run"
            assert workouts[0].id == 1
            assert workouts[0].workout_token == "token_1"
            assert workouts[1].name == "Evening Ride"
            assert workouts[1].plan_id == 123

    @pytest.mark.asyncio
    async def test_list_workouts_with_filters(
        self,
        wahoo_config,
        mock_workouts_response,
        temp_token_file,
        monkeypatch,
        httpx_mock,
    ):
        monkeypatch.setenv("WAHOO_TOKEN_FILE", temp_token_file)

        # Mock the API response with query parameters
        httpx_mock.add_response(
            method="GET",
            url="https://api.wahooligan.com/v1/workouts?page=2&per_page=50&created_after=2024-01-01&created_before=2024-01-31",
            json=mock_workouts_response,
            status_code=200,
        )

        async with WahooAPIClient(wahoo_config) as client:
            await client.list_workouts(
                page=2, per_page=50, start_date="2024-01-01", end_date="2024-01-31"
            )

    @pytest.mark.asyncio
    async def test_get_workout(
        self,
        wahoo_config,
        mock_workout_detail,
        temp_token_file,
        monkeypatch,
        httpx_mock,
    ):
        monkeypatch.setenv("WAHOO_TOKEN_FILE", temp_token_file)

        # Mock the API response
        httpx_mock.add_response(
            method="GET",
            url="https://api.wahooligan.com/v1/workouts/1",
            json=mock_workout_detail,
            status_code=200,
        )

        async with WahooAPIClient(wahoo_config) as client:
            workout = await client.get_workout(1)

            assert workout.id == 1
            assert workout.name == "Morning Run"
            assert workout.workout_token == "token_1"
            assert workout.minutes == 45

    @pytest.mark.asyncio
    async def test_list_routes(
        self,
        wahoo_config,
        mock_routes_response,
        temp_token_file,
        monkeypatch,
        httpx_mock,
    ):
        monkeypatch.setenv("WAHOO_TOKEN_FILE", temp_token_file)

        # Mock the API response
        httpx_mock.add_response(
            method="GET",
            url="https://api.wahooligan.com/v1/routes",
            json=mock_routes_response,
            status_code=200,
        )

        async with WahooAPIClient(wahoo_config) as client:
            routes = await client.list_routes()

            assert len(routes) == 1
            assert routes[0].name == "Mountain Loop"
            assert routes[0].id == 1
            assert routes[0].distance == 25.5

    @pytest.mark.asyncio
    async def test_get_route(
        self, wahoo_config, mock_route_detail, temp_token_file, monkeypatch, httpx_mock
    ):
        monkeypatch.setenv("WAHOO_TOKEN_FILE", temp_token_file)

        # Mock the API response
        httpx_mock.add_response(
            method="GET",
            url="https://api.wahooligan.com/v1/routes/1",
            json=mock_route_detail,
            status_code=200,
        )

        async with WahooAPIClient(wahoo_config) as client:
            route = await client.get_route(1)

            assert route.id == 1
            assert route.name == "Mountain Loop"
            assert route.file.url == "https://example.com/route1.fit"

    @pytest.mark.asyncio
    async def test_list_plans(
        self,
        wahoo_config,
        mock_plans_response,
        temp_token_file,
        monkeypatch,
        httpx_mock,
    ):
        monkeypatch.setenv("WAHOO_TOKEN_FILE", temp_token_file)

        # Mock the API response
        httpx_mock.add_response(
            method="GET",
            url="https://api.wahooligan.com/v1/plans",
            json=mock_plans_response,
            status_code=200,
        )

        async with WahooAPIClient(wahoo_config) as client:
            plans = await client.list_plans()

            assert len(plans) == 1
            assert plans[0].name == "Training Plan A"
            assert plans[0].id == 1
            assert not plans[0].deleted

    @pytest.mark.asyncio
    async def test_get_plan(
        self, wahoo_config, mock_plan_detail, temp_token_file, monkeypatch, httpx_mock
    ):
        monkeypatch.setenv("WAHOO_TOKEN_FILE", temp_token_file)

        # Mock the API response
        httpx_mock.add_response(
            method="GET",
            url="https://api.wahooligan.com/v1/plans/1",
            json=mock_plan_detail,
            status_code=200,
        )

        async with WahooAPIClient(wahoo_config) as client:
            plan = await client.get_plan(1)

            assert plan.id == 1
            assert plan.name == "Training Plan A"
            assert plan.file.url == "https://example.com/plan1.json"

    @pytest.mark.asyncio
    async def test_create_plan(
        self, wahoo_config, temp_token_file, monkeypatch, httpx_mock
    ):
        monkeypatch.setenv("WAHOO_TOKEN_FILE", temp_token_file)

        # Mock response for plan creation
        mock_create_response = {
            "id": 100,
            "user_id": 1,
            "name": "New Training Plan",
            "description": "A new training plan",
            "file": {"url": "https://example.com/new_plan.json"},
            "external_id": "EXT123",
            "provider_updated_at": "2024-01-01T12:00:00Z",
            "created_at": "2024-01-01T12:00:00Z",
            "updated_at": "2024-01-01T12:00:00Z",
        }

        # Mock the POST request to /v1/plans
        httpx_mock.add_response(
            method="POST",
            url="https://api.wahooligan.com/v1/plans",
            json=mock_create_response,
            status_code=201,
        )

        # Create test workout targets
        power_target = WorkoutTarget(
            target_type="power", target_min=200, target_max=250, unit="watts"
        )

        # Create test workout interval with generic interval type
        test_interval = WorkoutInterval(
            duration=600,  # 10 minutes
            targets=[power_target],
            name="Test Interval",
            interval_type="work",  # This should map to "active"
        )

        # Create test workout plan
        test_plan = WorkoutPlan(
            name="New Training Plan",
            description="A test training plan",
            intervals=[test_interval],
            workout_type="bike",
            author="Test Author",
        )

        plan_request = CreatePlanRequest(
            plan=test_plan,
            filename="test_plan.json",
            external_id="EXT123",
            provider_updated_at="2024-01-01T12:00:00Z",
        )

        async with WahooAPIClient(wahoo_config) as client:
            created_plan = await client.create_plan(plan_request)

            assert created_plan.id == 100
            assert created_plan.name == "New Training Plan"
            assert created_plan.external_id == "EXT123"
            assert created_plan.file.url == "https://example.com/new_plan.json"

            # Verify the request was made to the correct endpoint
            assert len(httpx_mock.get_requests()) == 1
            request = httpx_mock.get_requests()[0]
            assert request.method == "POST"
            assert "/v1/plans" in str(request.url)

    @pytest.mark.asyncio
    async def test_list_power_zones(
        self,
        wahoo_config,
        mock_power_zones_response,
        temp_token_file,
        monkeypatch,
        httpx_mock,
    ):
        monkeypatch.setenv("WAHOO_TOKEN_FILE", temp_token_file)

        # Mock the API response
        httpx_mock.add_response(
            method="GET",
            url="https://api.wahooligan.com/v1/power_zones",
            json=mock_power_zones_response,
            status_code=200,
        )

        async with WahooAPIClient(wahoo_config) as client:
            power_zones = await client.list_power_zones()

            assert len(power_zones) == 1
            assert power_zones[0].ftp == 250
            assert power_zones[0].id == 1
            assert power_zones[0].zone_7 == 400

    @pytest.mark.asyncio
    async def test_get_power_zone(
        self,
        wahoo_config,
        mock_power_zone_detail,
        temp_token_file,
        monkeypatch,
        httpx_mock,
    ):
        monkeypatch.setenv("WAHOO_TOKEN_FILE", temp_token_file)

        # Mock the API response
        httpx_mock.add_response(
            method="GET",
            url="https://api.wahooligan.com/v1/power_zones/1",
            json=mock_power_zone_detail,
            status_code=200,
        )

        async with WahooAPIClient(wahoo_config) as client:
            power_zone = await client.get_power_zone(1)

            assert power_zone.id == 1
            assert power_zone.ftp == 250
            assert power_zone.critical_power == 275


class TestMCPTools:
    @pytest.mark.asyncio
    async def test_list_tools(self):
        # The list_tools decorator creates a handler, we need to call it directly
        tools = await list_tools()
        assert len(tools) == 9

        tool_names = [tool.name for tool in tools]
        expected_tools = [
            "list_workouts",
            "get_workout",
            "list_routes",
            "get_route",
            "list_plans",
            "get_plan",
            "create_plan",
            "list_power_zones",
            "get_power_zone",
        ]

        for expected_tool in expected_tools:
            assert expected_tool in tool_names

    @pytest.mark.asyncio
    async def test_call_tool_list_workouts(
        self, mock_workouts_response, temp_token_file, monkeypatch
    ):
        monkeypatch.setenv("WAHOO_TOKEN_FILE", temp_token_file)
        with patch(
            "src.server.WahooAPIClient.list_workouts", new_callable=AsyncMock
        ) as mock_list:
            # Convert mock data to Workout objects
            workout_objects = [Workout(**w) for w in mock_workouts_response["workouts"]]
            mock_list.return_value = workout_objects

            result = await call_tool("list_workouts", {})

            assert len(result) == 1
            assert "Found 2 workouts" in result[0].text
            assert "Morning Run" in result[0].text
            assert "Evening Ride" in result[0].text

    @pytest.mark.asyncio
    async def test_call_tool_get_workout(
        self, mock_workout_detail, temp_token_file, monkeypatch
    ):
        monkeypatch.setenv("WAHOO_TOKEN_FILE", temp_token_file)
        with patch(
            "src.server.WahooAPIClient.get_workout", new_callable=AsyncMock
        ) as mock_get:
            # Convert mock data to Workout object
            workout_object = Workout(**mock_workout_detail)
            mock_get.return_value = workout_object

            result = await call_tool("get_workout", {"workout_id": 1})

            assert len(result) == 1
            assert "Workout Details (ID: 1)" in result[0].text
            assert "Morning Run" in result[0].text
            assert "45 minutes" in result[0].text

    @pytest.mark.asyncio
    async def test_call_tool_no_token(self, monkeypatch):
        monkeypatch.delenv("WAHOO_TOKEN_FILE", raising=False)
        result = await call_tool("list_workouts", {})

        assert len(result) == 1
        assert "WAHOO_TOKEN_FILE environment variable is required" in result[0].text

    @pytest.mark.asyncio
    async def test_call_tool_unknown_tool(self, temp_token_file, monkeypatch):
        monkeypatch.setenv("WAHOO_TOKEN_FILE", temp_token_file)
        result = await call_tool("unknown_tool", {})

        assert len(result) == 1
        assert "Unknown tool: unknown_tool" in result[0].text


class TestRefreshToken:
    @pytest.fixture
    def mock_token_store(self):
        store = MagicMock(spec=TokenStore)
        store.get_current.return_value = TokenData(
            access_token="test_access",
            refresh_token="test_refresh",
            code_verifier="test_verifier",
            expires_at=time.time() + 3600,
        )
        return store

    @pytest.mark.asyncio
    async def test_refresh_token_on_expired(
        self, wahoo_config, temp_token_file, monkeypatch
    ):
        monkeypatch.setenv("WAHOO_TOKEN_FILE", temp_token_file)

        # Modify the token file to have an expired token
        with open(temp_token_file) as f:
            token_data = json.load(f)
        token_data["expires_at"] = time.time() - 100
        with open(temp_token_file, "w") as f:
            json.dump(token_data, f)

        async with WahooAPIClient(wahoo_config) as client:
            with patch.object(
                client, "_refresh_access_token", new_callable=AsyncMock
            ) as mock_refresh:
                mock_refresh.return_value = True

                # Ensure token refresh is called
                await client._ensure_valid_token()

                mock_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_refresh_token_on_401_response(
        self, wahoo_config, temp_token_file, monkeypatch
    ):
        monkeypatch.setenv("WAHOO_TOKEN_FILE", temp_token_file)
        async with WahooAPIClient(wahoo_config) as client:
            with patch.object(client.client, "get") as mock_get:
                # First call returns 401, second call succeeds
                mock_response_401 = MagicMock()
                mock_response_401.status_code = 401

                mock_response_200 = MagicMock()
                mock_response_200.status_code = 200
                mock_response_200.json.return_value = {"workouts": []}
                mock_response_200.raise_for_status.return_value = None

                mock_get.side_effect = [mock_response_401, mock_response_200]

                with patch.object(
                    client, "_refresh_access_token", new_callable=AsyncMock
                ) as mock_refresh:
                    mock_refresh.return_value = True

                    workouts = await client.list_workouts()

                    assert workouts == []
                    mock_refresh.assert_called_once()
                    assert mock_get.call_count == 2

    @pytest.mark.asyncio
    async def test_refresh_token_failure_raises_error(
        self, wahoo_config, temp_token_file, monkeypatch
    ):
        monkeypatch.setenv("WAHOO_TOKEN_FILE", temp_token_file)
        async with WahooAPIClient(wahoo_config) as client:
            with patch.object(client.client, "get") as mock_get:
                mock_response_401 = MagicMock()
                mock_response_401.status_code = 401
                mock_response_401.request = MagicMock()
                mock_get.return_value = mock_response_401

                with patch.object(
                    client, "_refresh_access_token", new_callable=AsyncMock
                ) as mock_refresh:
                    mock_refresh.return_value = False

                    with pytest.raises(Exception) as exc_info:
                        await client.list_workouts()

                    assert "Authentication failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_refresh_access_token_success(
        self, wahoo_config, temp_token_file, monkeypatch
    ):
        monkeypatch.setenv("WAHOO_TOKEN_FILE", temp_token_file)
        monkeypatch.setenv("WAHOO_CLIENT_ID", "test_client_id")
        async with WahooAPIClient(wahoo_config) as client:
            with patch("httpx.AsyncClient") as mock_client_class:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {
                    "access_token": "new_access_token",
                    "refresh_token": "new_refresh_token",
                    "expires_in": 7200,
                }

                mock_client = AsyncMock()
                mock_client.post.return_value = mock_response
                mock_client.__aenter__.return_value = mock_client
                mock_client_class.return_value = mock_client

                result = await client._refresh_access_token()

                assert result is True
                # Check that token was updated in the store
                assert (
                    client.token_store.get_current().access_token == "new_access_token"
                )

    @pytest.mark.asyncio
    async def test_refresh_access_token_no_refresh_token(
        self, wahoo_config, monkeypatch, tmp_path
    ):
        # Create a token file without refresh token
        token_file = tmp_path / "no_refresh_token.json"
        token_data = {
            "access_token": "test_token",
            "expires_at": time.time() + 7200,
            "token_type": "Bearer",
        }
        token_file.write_text(json.dumps(token_data))

        monkeypatch.setenv("WAHOO_TOKEN_FILE", str(token_file))
        async with WahooAPIClient(wahoo_config) as client:
            result = await client._refresh_access_token()
            assert result is False

    @pytest.mark.asyncio
    async def test_call_tool_with_token_store(
        self, mock_workouts_response, monkeypatch
    ):
        monkeypatch.setenv("WAHOO_TOKEN_FILE", "/tmp/tokens.json")
        mock_token_data = TokenData(
            access_token="stored_token",
            refresh_token="stored_refresh",
            expires_at=time.time() + 3600,
        )

        with patch("src.server.TokenStore") as mock_store_class:
            mock_store = MagicMock()
            mock_store.load.return_value = mock_token_data
            mock_store_class.return_value = mock_store

            with patch(
                "src.server.WahooAPIClient.list_workouts", new_callable=AsyncMock
            ) as mock_list:
                # Convert mock data to Workout objects
                workout_objects = [
                    Workout(**w) for w in mock_workouts_response["workouts"]
                ]
                mock_list.return_value = workout_objects

                result = await call_tool("list_workouts", {})

                assert len(result) == 1
                assert "Found 2 workouts" in result[0].text


class TestIntensityTypeMapping:
    """Test intensity type mapping for Wahoo API compatibility."""

    def test_intensity_type_mapping(self):
        """Test that interval types are correctly mapped to Wahoo intensity types."""
        # Create test workout plan
        plan = WorkoutPlan(
            name="Test Plan",
            intervals=[
                WorkoutInterval(
                    duration=300,
                    targets=[WorkoutTarget(target_type="power", target_value=200)],
                    interval_type="work",  # Should map to "active"
                ),
                WorkoutInterval(
                    duration=300,
                    targets=[WorkoutTarget(target_type="power", target_value=100)],
                    interval_type="warmup",  # Should map to "wu"
                ),
                WorkoutInterval(
                    duration=300,
                    targets=[WorkoutTarget(target_type="power", target_value=150)],
                    interval_type="cooldown",  # Should map to "cd"
                ),
                WorkoutInterval(
                    duration=300,
                    targets=[WorkoutTarget(target_type="power", target_value=120)],
                    interval_type="rest",  # Should stay "rest"
                ),
            ],
        )

        # Convert to Wahoo format
        wahoo_plan = plan.to_wahoo_format()

        # Verify intensity types are correctly mapped
        intervals = wahoo_plan["intervals"]
        assert len(intervals) == 4

        assert intervals[0]["intensity_type"] == "active"  # work -> active
        assert intervals[1]["intensity_type"] == "wu"  # warmup -> wu
        assert intervals[2]["intensity_type"] == "cd"  # cooldown -> cd
        assert intervals[3]["intensity_type"] == "rest"  # rest -> rest

    def test_intensity_type_case_insensitive(self):
        """Test that intensity type mapping is case insensitive."""
        plan = WorkoutPlan(
            name="Test Plan",
            intervals=[
                WorkoutInterval(
                    duration=300,
                    targets=[WorkoutTarget(target_type="power", target_value=200)],
                    interval_type="WORK",  # Should map to "active"
                ),
                WorkoutInterval(
                    duration=300,
                    targets=[WorkoutTarget(target_type="power", target_value=100)],
                    interval_type="WarmUp",  # Should map to "wu"
                ),
            ],
        )

        wahoo_plan = plan.to_wahoo_format()
        intervals = wahoo_plan["intervals"]

        assert intervals[0]["intensity_type"] == "active"
        assert intervals[1]["intensity_type"] == "wu"

    def test_unknown_intensity_type_defaults_to_active(self):
        """Test that unknown intensity types default to 'active'."""
        plan = WorkoutPlan(
            name="Test Plan",
            intervals=[
                WorkoutInterval(
                    duration=300,
                    targets=[WorkoutTarget(target_type="power", target_value=200)],
                    interval_type="unknown_type",  # Should default to "active"
                ),
            ],
        )

        wahoo_plan = plan.to_wahoo_format()
        intervals = wahoo_plan["intervals"]

        assert intervals[0]["intensity_type"] == "active"

    def test_target_type_mapping(self):
        """Test that target types are correctly mapped to Wahoo target types."""
        plan = WorkoutPlan(
            name="Test Plan",
            intervals=[
                WorkoutInterval(
                    duration=300,
                    targets=[
                        WorkoutTarget(
                            target_type="power", target_value=200
                        ),  # Should map to "watts"
                        WorkoutTarget(
                            target_type="heart_rate", target_value=150
                        ),  # Should map to "hr"
                        WorkoutTarget(
                            target_type="cadence", target_value=90
                        ),  # Should map to "rpm"
                    ],
                    interval_type="work",
                ),
            ],
        )

        wahoo_plan = plan.to_wahoo_format()
        targets = wahoo_plan["intervals"][0]["targets"]

        assert len(targets) == 3
        assert targets[0]["type"] == "watts"  # power -> watts
        assert targets[1]["type"] == "hr"  # heart_rate -> hr
        assert targets[2]["type"] == "rpm"  # cadence -> rpm

    def test_target_type_case_insensitive(self):
        """Test that target type mapping is case insensitive."""
        plan = WorkoutPlan(
            name="Test Plan",
            intervals=[
                WorkoutInterval(
                    duration=300,
                    targets=[WorkoutTarget(target_type="POWER", target_value=200)],
                    interval_type="work",
                ),
            ],
        )

        wahoo_plan = plan.to_wahoo_format()
        targets = wahoo_plan["intervals"][0]["targets"]

        assert targets[0]["type"] == "watts"

    def test_unknown_target_type_defaults_to_watts(self):
        """Test that unknown target types default to 'watts'."""
        plan = WorkoutPlan(
            name="Test Plan",
            intervals=[
                WorkoutInterval(
                    duration=300,
                    targets=[
                        WorkoutTarget(target_type="unknown_type", target_value=200)
                    ],
                    interval_type="work",
                ),
            ],
        )

        wahoo_plan = plan.to_wahoo_format()
        targets = wahoo_plan["intervals"][0]["targets"]

        assert targets[0]["type"] == "watts"
