import pytest
import json
import os
import time
from unittest.mock import patch
from src.token_store import TokenStore, TokenData


class TestTokenData:
    def test_token_data_creation(self):
        token = TokenData(
            access_token="test_access",
            refresh_token="test_refresh",
            code_verifier="test_verifier",
            expires_at=time.time() + 3600,
        )
        assert token.access_token == "test_access"
        assert token.refresh_token == "test_refresh"
        assert token.code_verifier == "test_verifier"
        assert token.token_type == "Bearer"

    def test_is_expired_with_future_expiry(self):
        token = TokenData(
            access_token="test",
            expires_at=time.time() + 3600,  # 1 hour from now
        )
        assert not token.is_expired()
        assert not token.is_expired(buffer_seconds=300)

    def test_is_expired_with_past_expiry(self):
        token = TokenData(
            access_token="test",
            expires_at=time.time() - 100,  # 100 seconds ago
        )
        assert token.is_expired()
        assert token.is_expired(buffer_seconds=0)

    def test_is_expired_with_buffer(self):
        token = TokenData(
            access_token="test",
            expires_at=time.time() + 200,  # 200 seconds from now
        )
        assert not token.is_expired(buffer_seconds=100)
        assert token.is_expired(buffer_seconds=300)  # With 5-minute buffer

    def test_is_expired_without_expiry(self):
        token = TokenData(access_token="test")
        assert not token.is_expired()
        assert not token.is_expired(buffer_seconds=300)

    def test_to_dict(self):
        token = TokenData(
            access_token="test_access",
            refresh_token="test_refresh",
            code_verifier="test_verifier",
            expires_at=1234567890.0,
        )
        data = token.to_dict()
        assert data == {
            "access_token": "test_access",
            "refresh_token": "test_refresh",
            "code_verifier": "test_verifier",
            "expires_at": 1234567890.0,
            "token_type": "Bearer",
        }

    def test_to_dict_excludes_none(self):
        token = TokenData(access_token="test_access")
        data = token.to_dict()
        assert data == {
            "access_token": "test_access",
            "token_type": "Bearer",
        }
        assert "refresh_token" not in data
        assert "code_verifier" not in data
        assert "expires_at" not in data

    def test_from_dict(self):
        data = {
            "access_token": "test_access",
            "refresh_token": "test_refresh",
            "code_verifier": "test_verifier",
            "expires_at": 1234567890.0,
            "token_type": "Bearer",
        }
        token = TokenData.from_dict(data)
        assert token.access_token == "test_access"
        assert token.refresh_token == "test_refresh"
        assert token.code_verifier == "test_verifier"
        assert token.expires_at == 1234567890.0
        assert token.token_type == "Bearer"

    def test_from_dict_ignores_extra_fields(self):
        data = {
            "access_token": "test_access",
            "extra_field": "should_be_ignored",
            "another_field": 123,
        }
        token = TokenData.from_dict(data)
        assert token.access_token == "test_access"
        assert not hasattr(token, "extra_field")
        assert not hasattr(token, "another_field")


class TestTokenStore:
    @pytest.fixture
    def temp_token_file(self, tmp_path):
        return tmp_path / "tokens.json"

    def test_init_without_file(self):
        with pytest.raises(TypeError):
            TokenStore()

    def test_init_with_empty_file(self):
        with pytest.raises(ValueError) as exc_info:
            TokenStore("")
        assert "token_file is required" in str(exc_info.value)

    def test_init_with_file(self, temp_token_file):
        store = TokenStore(str(temp_token_file))
        assert store.token_file == temp_token_file
        assert store._token_data is None

    def test_load_from_missing_file(self, temp_token_file):
        # Use a non-existent file path
        store = TokenStore(str(temp_token_file) + ".missing")
        token_data = store.load()

        assert token_data is None

    @patch.dict(os.environ, {}, clear=True)
    def test_load_from_file(self, temp_token_file):
        # Create a token file
        token_data = {
            "access_token": "file_access_token",
            "refresh_token": "file_refresh_token",
            "expires_at": time.time() + 3600,
        }
        with open(temp_token_file, "w") as f:
            json.dump(token_data, f)

        store = TokenStore(str(temp_token_file))
        loaded_data = store.load()

        assert loaded_data is not None
        assert loaded_data.access_token == "file_access_token"
        assert loaded_data.refresh_token == "file_refresh_token"
        assert loaded_data.expires_at == token_data["expires_at"]

    def test_load_from_invalid_json_file(self, temp_token_file):
        # Create an invalid JSON file
        with open(temp_token_file, "w") as f:
            f.write("invalid json")

        store = TokenStore(str(temp_token_file))
        token_data = store.load()

        # Should return None on error
        assert token_data is None

    def test_load_returns_none_when_file_missing(self, temp_token_file):
        # Use a non-existent file path
        store = TokenStore(str(temp_token_file) + ".notfound")
        assert store.load() is None

    def test_save_to_file(self, temp_token_file):
        store = TokenStore(str(temp_token_file))
        token_data = TokenData(
            access_token="saved_access_token",
            refresh_token="saved_refresh_token",
            expires_at=1234567890.0,
        )

        store.save(token_data)

        # Verify file was created with correct content
        assert temp_token_file.exists()
        with open(temp_token_file) as f:
            saved_data = json.load(f)

        assert saved_data["access_token"] == "saved_access_token"
        assert saved_data["refresh_token"] == "saved_refresh_token"
        assert saved_data["expires_at"] == 1234567890.0

        # Verify file permissions (Unix only)
        if os.name != "nt":
            stat_info = os.stat(temp_token_file)
            assert stat_info.st_mode & 0o777 == 0o600

    def test_save_creates_parent_directory(self, tmp_path):
        # Use a path with non-existent parent directory
        nested_path = tmp_path / "nested" / "dir" / "tokens.json"
        store = TokenStore(str(nested_path))
        token_data = TokenData(access_token="test")

        store.save(token_data)

        assert nested_path.exists()
        assert store._token_data == token_data

    def test_update_from_response(self, temp_token_file):
        store = TokenStore(str(temp_token_file))
        response_data = {
            "access_token": "new_access_token",
            "refresh_token": "new_refresh_token",
            "expires_in": 7200,
            "token_type": "Bearer",
        }

        before_time = time.time()
        token_data = store.update_from_response(response_data)
        after_time = time.time()

        assert token_data.access_token == "new_access_token"
        assert token_data.refresh_token == "new_refresh_token"
        assert token_data.token_type == "Bearer"
        assert before_time + 7200 <= token_data.expires_at <= after_time + 7200

    def test_update_from_response_preserves_code_verifier(self, temp_token_file):
        store = TokenStore(str(temp_token_file))
        # Set initial token data with code_verifier
        initial_token = TokenData(
            access_token="old_access",
            refresh_token="old_refresh",
            code_verifier="preserved_verifier",
        )
        store._token_data = initial_token

        response_data = {
            "access_token": "new_access_token",
            "expires_in": 7200,
        }

        token_data = store.update_from_response(response_data)

        assert token_data.access_token == "new_access_token"
        assert token_data.refresh_token == "old_refresh"  # Preserved
        assert token_data.code_verifier == "preserved_verifier"  # Preserved

    def test_get_current_loads_if_needed(self, temp_token_file):
        store = TokenStore(str(temp_token_file))
        with patch.object(store, "load") as mock_load:
            mock_load.return_value = TokenData(access_token="loaded_token")

            token_data = store.get_current()

            assert token_data.access_token == "loaded_token"
            mock_load.assert_called_once()

    def test_get_current_returns_cached(self, temp_token_file):
        store = TokenStore(str(temp_token_file))
        cached_token = TokenData(access_token="cached_token")
        store._token_data = cached_token

        with patch.object(store, "load") as mock_load:
            token_data = store.get_current()

            assert token_data == cached_token
            mock_load.assert_not_called()

    def test_clear(self, temp_token_file):
        # Create a token file
        with open(temp_token_file, "w") as f:
            json.dump({"access_token": "test"}, f)

        store = TokenStore(str(temp_token_file))
        store._token_data = TokenData(access_token="test")

        store.clear()

        assert store._token_data is None
        assert not temp_token_file.exists()

    def test_clear_with_missing_file(self, temp_token_file):
        # Use a non-existent file path
        store = TokenStore(str(temp_token_file) + ".missing")
        store._token_data = TokenData(access_token="test")

        # Should not raise exception even if file doesn't exist
        store.clear()
        assert store._token_data is None
