#!/usr/bin/env python3
"""
Token storage and management for Wahoo API
"""

import os
import json
import time
from typing import Optional, Dict, Any
from pathlib import Path
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class TokenData:
    """Container for OAuth token data"""

    access_token: str
    refresh_token: Optional[str] = None
    code_verifier: Optional[str] = None
    expires_at: Optional[float] = None
    token_type: str = "Bearer"

    def is_expired(self, buffer_seconds: int = 300) -> bool:
        """Check if token is expired or will expire soon"""
        if not self.expires_at:
            return False
        return time.time() >= (self.expires_at - buffer_seconds)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {k: v for k, v in asdict(self).items() if v is not None}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TokenData":
        """Create from dictionary"""
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})


class TokenStore:
    """Manages OAuth tokens with file persistence"""

    def __init__(self, token_file: str):
        if not token_file:
            raise ValueError("token_file is required")
        self.token_file = Path(token_file)
        self._token_data: Optional[TokenData] = None

    def load(self) -> Optional[TokenData]:
        """Load tokens from file"""
        if self.token_file.exists():
            try:
                with open(self.token_file, "r") as f:
                    data = json.load(f)
                    self._token_data = TokenData.from_dict(data)
                    logger.info(f"Loaded tokens from file: {self.token_file}")
                    return self._token_data
            except Exception as e:
                logger.error(f"Failed to load token file: {e}")
        else:
            logger.warning(f"Token file not found: {self.token_file}")

        return None

    def save(self, token_data: TokenData) -> None:
        """Save tokens to file"""
        self._token_data = token_data

        try:
            # Ensure directory exists
            self.token_file.parent.mkdir(parents=True, exist_ok=True)

            # Write tokens to file
            with open(self.token_file, "w") as f:
                json.dump(token_data.to_dict(), f, indent=2)

            # Set restrictive permissions (owner read/write only)
            os.chmod(self.token_file, 0o600)

            logger.info(f"Saved tokens to file: {self.token_file}")
        except Exception as e:
            logger.error(f"Failed to save token file: {e}")

    def update_from_response(self, response_data: Dict[str, Any]) -> TokenData:
        """Update tokens from OAuth response"""
        # Calculate expiry time
        expires_at = None
        if "expires_in" in response_data:
            expires_at = time.time() + response_data["expires_in"]

        # Create new token data
        token_data = TokenData(
            access_token=response_data["access_token"],
            refresh_token=response_data.get(
                "refresh_token",
                self._token_data.refresh_token if self._token_data else None,
            ),
            code_verifier=self._token_data.code_verifier if self._token_data else None,
            expires_at=expires_at,
            token_type=response_data.get("token_type", "Bearer"),
        )

        # Save the updated tokens
        self.save(token_data)
        return token_data

    def get_current(self) -> Optional[TokenData]:
        """Get current token data"""
        if not self._token_data:
            self._token_data = self.load()
        return self._token_data

    def clear(self) -> None:
        """Clear stored tokens"""
        self._token_data = None
        if self.token_file and self.token_file.exists():
            try:
                self.token_file.unlink()
                logger.info(f"Deleted token file: {self.token_file}")
            except Exception as e:
                logger.error(f"Failed to delete token file: {e}")
