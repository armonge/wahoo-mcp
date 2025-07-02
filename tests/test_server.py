import pytest
import time
from unittest.mock import patch, AsyncMock, MagicMock
from src.server import WahooAPIClient, WahooConfig
from src.token_store import TokenStore, TokenData


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
            assert "No authentication tokens found" in result[0].text

    @pytest.mark.asyncio
    async def test_call_tool_unknown_tool(self):
        with patch.dict("os.environ", {"WAHOO_ACCESS_TOKEN": "test_token"}):
            from src.server import call_tool

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
    async def test_refresh_token_on_expired(self, wahoo_config, mock_token_store):
        # Set token as expired
        mock_token_store.get_current.return_value.expires_at = time.time() - 100

        async with WahooAPIClient(wahoo_config, mock_token_store) as client:
            with patch.object(
                client, "_refresh_access_token", new_callable=AsyncMock
            ) as mock_refresh:
                mock_refresh.return_value = True

                # Ensure token refresh is called
                await client._ensure_valid_token()

                mock_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_refresh_token_on_401_response(self, wahoo_config, mock_token_store):
        async with WahooAPIClient(wahoo_config, mock_token_store) as client:
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
        self, wahoo_config, mock_token_store
    ):
        async with WahooAPIClient(wahoo_config, mock_token_store) as client:
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
    async def test_refresh_access_token_success(self, wahoo_config, mock_token_store):
        with patch.dict("os.environ", {"WAHOO_CLIENT_ID": "test_client_id"}):
            async with WahooAPIClient(wahoo_config, mock_token_store) as client:
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
                    mock_token_store.update_from_response.assert_called_once()

    @pytest.mark.asyncio
    async def test_refresh_access_token_no_refresh_token(self, wahoo_config):
        store = MagicMock(spec=TokenStore)
        store.get_current.return_value = TokenData(
            access_token="test"
        )  # No refresh token

        async with WahooAPIClient(wahoo_config, store) as client:
            result = await client._refresh_access_token()
            assert result is False

    @pytest.mark.asyncio
    async def test_call_tool_with_token_store(self, mock_workouts_response):
        with patch.dict("os.environ", {"WAHOO_TOKEN_FILE": "/tmp/tokens.json"}):
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
                    mock_list.return_value = mock_workouts_response["workouts"]

                    from src.server import call_tool

                    result = await call_tool("list_workouts", {})

                    assert len(result) == 1
                    assert "Found 2 workouts" in result[0].text
