"""Authentication handling for ByteBlaster protocol.

This module provides authentication functionality for the ByteBlaster protocol,
including logon message creation and periodic re-authentication.
"""

import asyncio
import logging
from typing import Protocol

from byteblaster.utils.crypto import xor_encode_string

logger = logging.getLogger(__name__)


class AuthProtocol(Protocol):
    """Protocol for authentication callbacks."""

    async def send_data(self, data: bytes) -> None:
        """Send data to remote server."""
        ...


class AuthenticationHandler:
    """Handles ByteBlaster authentication and keep-alive.

    This class manages the initial logon sequence and periodic re-authentication
    required by ByteBlaster servers.
    """

    # Logon message format
    LOGON_FORMAT = "ByteBlast Client|NM-{email}|V2"

    # Re-authentication interval (2 minutes)
    REAUTH_INTERVAL = 115.0

    def __init__(self, email: str) -> None:
        """Initialize authentication handler.

        Args:
            email: Email address for authentication

        Raises:
            ValueError: If email is empty or invalid

        """
        if not email or not email.strip():
            msg = "Email address cannot be empty"
            raise ValueError(msg)

        self._email = email.strip()
        self._logon_message = self._create_logon_message()
        self._auth_protocol: AuthProtocol | None = None
        self._reauth_task: asyncio.Task[None] | None = None
        self._is_active = False

    def _create_logon_message(self) -> bytes:
        """Create XOR-encoded logon message.

        Returns:
            XOR-encoded logon message bytes

        """
        logon_text = self.LOGON_FORMAT.format(email=self._email)
        return xor_encode_string(logon_text, encoding="ascii")

    async def start_authentication(self, auth_protocol: AuthProtocol) -> None:
        """Start authentication process.

        Args:
            auth_protocol: Protocol for sending authentication data

        """
        self._auth_protocol = auth_protocol
        self._is_active = True

        # Send initial logon
        await self._send_logon()

        # Start periodic re-authentication
        self._reauth_task = asyncio.create_task(self._reauth_loop())
        logger.info("Authentication started")

    async def stop_authentication(self) -> None:
        """Stop authentication and cancel re-authentication task."""
        self._is_active = False

        if self._reauth_task and not self._reauth_task.done():
            self._reauth_task.cancel()
            try:
                await self._reauth_task
            except asyncio.CancelledError:
                logger.debug("Re-authentication task cancelled during shutdown")

        self._reauth_task = None
        self._auth_protocol = None
        logger.info("Authentication stopped")

    async def _send_logon(self) -> None:
        """Send logon message to server."""
        if not self._auth_protocol:
            msg = "No authentication protocol available"
            raise RuntimeError(msg)

        await self._auth_protocol.send_data(self._logon_message)
        logger.debug("Sent logon message")

    async def _reauth_loop(self) -> None:
        """Periodic re-authentication loop."""
        try:
            while self._is_active:
                await asyncio.sleep(self.REAUTH_INTERVAL)

                if self._is_active and self._auth_protocol:
                    await self._send_logon()
                    logger.debug("Sent periodic re-authentication")

        except asyncio.CancelledError:
            logger.debug("Re-authentication loop cancelled")
            raise
        except Exception:
            logger.exception("Re-authentication loop error")
            raise

    @property
    def email(self) -> str:
        """Get email address used for authentication."""
        return self._email

    @property
    def is_active(self) -> bool:
        """Check if authentication is active."""
        return self._is_active

    def __repr__(self) -> str:
        """Return string representation."""
        return f"AuthenticationHandler(email='{self._email}', active={self._is_active})"
