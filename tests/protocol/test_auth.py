# pyright: reportPrivateUsage=false
"""Tests for authentication handling in ByteBlaster protocol."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from byteblaster.protocol.auth import AuthenticationHandler
from byteblaster.utils.crypto import xor_encode_string


class MockAuthProtocol:
    """Mock implementation of AuthProtocol for testing."""

    def __init__(self) -> None:
        """Initialize mock protocol with AsyncMock send_data."""
        self.send_data = AsyncMock()


class TestAuthenticationHandler:
    """Test cases for AuthenticationHandler class."""

    def test_authentication_handler_when_valid_email_then_initializes_correctly(self) -> None:
        """Test AuthenticationHandler initializes with valid email."""
        # Arrange & Act
        handler = AuthenticationHandler("test@example.com")

        # Assert
        assert handler.email == "test@example.com"
        assert not handler.is_active
        assert "test@example.com" in repr(handler)
        assert "active=False" in repr(handler)

    def test_authentication_handler_when_email_with_whitespace_then_strips_whitespace(self) -> None:
        """Test AuthenticationHandler strips whitespace from email."""
        # Arrange & Act
        handler = AuthenticationHandler("  test@example.com  ")

        # Assert
        assert handler.email == "test@example.com"

    @pytest.mark.parametrize(
        "invalid_email",
        [
            "",
            "   ",
            "\t\n",
        ],
    )
    def test_authentication_handler_when_invalid_email_then_raises_value_error(
        self, invalid_email: str
    ) -> None:
        """Test AuthenticationHandler raises ValueError for invalid email."""
        # Arrange & Act & Assert
        with pytest.raises(ValueError, match="Email address cannot be empty"):
            AuthenticationHandler(invalid_email)

    def test_create_logon_message_when_email_provided_then_creates_correct_format(self) -> None:
        """Test logon message creation follows correct format."""
        # Arrange
        email = "user@domain.com"
        handler = AuthenticationHandler(email)
        expected_text = f"ByteBlast Client|NM-{email}|V2"
        expected_encoded = xor_encode_string(expected_text, encoding="ascii")

        # Act
        logon_message = handler._create_logon_message()

        # Assert
        assert logon_message == expected_encoded

    @pytest.mark.asyncio
    async def test_start_authentication_when_called_then_sends_logon_and_starts_reauth(
        self,
    ) -> None:
        """Test start_authentication sends initial logon and starts periodic reauth."""
        # Arrange
        handler = AuthenticationHandler("test@example.com")
        mock_protocol = MockAuthProtocol()

        # Act
        await handler.start_authentication(mock_protocol)

        # Assert
        assert handler.is_active
        mock_protocol.send_data.assert_called_once()
        assert handler._reauth_task is not None
        assert not handler._reauth_task.done()

        # Cleanup
        await handler.stop_authentication()

    @pytest.mark.asyncio
    async def test_start_authentication_when_called_then_sends_correct_logon_message(
        self,
    ) -> None:
        """Test start_authentication sends the correct XOR-encoded logon message."""
        # Arrange
        email = "test@example.com"
        handler = AuthenticationHandler(email)
        mock_protocol = MockAuthProtocol()
        expected_message = xor_encode_string(f"ByteBlast Client|NM-{email}|V2", encoding="ascii")

        # Act
        await handler.start_authentication(mock_protocol)

        # Assert
        mock_protocol.send_data.assert_called_once_with(expected_message)

        # Cleanup
        await handler.stop_authentication()

    @pytest.mark.asyncio
    async def test_stop_authentication_when_called_then_cancels_reauth_task(self) -> None:
        """Test stop_authentication properly cancels re-authentication task."""
        # Arrange
        handler = AuthenticationHandler("test@example.com")
        mock_protocol = MockAuthProtocol()
        await handler.start_authentication(mock_protocol)
        reauth_task = handler._reauth_task

        # Act
        await handler.stop_authentication()

        # Assert
        assert not handler.is_active
        assert handler._reauth_task is None
        assert reauth_task is not None
        assert reauth_task.cancelled()

    @pytest.mark.asyncio
    async def test_stop_authentication_when_no_active_task_then_handles_gracefully(self) -> None:
        """Test stop_authentication handles case where no task is running."""
        # Arrange
        handler = AuthenticationHandler("test@example.com")

        # Act & Assert - Should not raise any exceptions
        await handler.stop_authentication()
        assert not handler.is_active

    @pytest.mark.asyncio
    async def test_send_logon_when_no_protocol_then_raises_runtime_error(self) -> None:
        """Test _send_logon raises RuntimeError when no protocol is set."""
        # Arrange
        handler = AuthenticationHandler("test@example.com")

        # Act & Assert
        with pytest.raises(RuntimeError, match="No authentication protocol available"):
            await handler._send_logon()

    @pytest.mark.asyncio
    async def test_reauth_loop_when_active_then_sends_periodic_logon_messages(self) -> None:
        """Test re-authentication loop sends periodic logon messages."""
        # Arrange
        handler = AuthenticationHandler("test@example.com")
        mock_protocol = MockAuthProtocol()

        # Patch the reauth interval to be very short for testing
        original_interval = AuthenticationHandler.REAUTH_INTERVAL
        AuthenticationHandler.REAUTH_INTERVAL = 0.01

        try:
            # Start authentication
            await handler.start_authentication(mock_protocol)

            # Wait for multiple reauth cycles
            await asyncio.sleep(0.05)

            # Assert multiple logon messages were sent (initial + at least one reauth)
            assert mock_protocol.send_data.call_count >= 2

        finally:
            # Restore original interval
            AuthenticationHandler.REAUTH_INTERVAL = original_interval
            # Cleanup
            await handler.stop_authentication()

    @pytest.mark.asyncio
    async def test_reauth_loop_when_cancelled_then_raises_cancelled_error(self) -> None:
        """Test re-authentication loop properly handles cancellation."""
        # Arrange
        handler = AuthenticationHandler("test@example.com")
        mock_protocol = MockAuthProtocol()
        await handler.start_authentication(mock_protocol)
        reauth_task = handler._reauth_task

        # Act
        assert reauth_task is not None
        reauth_task.cancel()

        # Assert
        with pytest.raises(asyncio.CancelledError):
            await reauth_task

        # Cleanup
        await handler.stop_authentication()

    @pytest.mark.asyncio
    async def test_reauth_loop_when_exception_occurs_then_propagates_exception(self) -> None:
        """Test re-authentication loop propagates exceptions from send_data."""
        # Arrange
        handler = AuthenticationHandler("test@example.com")
        mock_protocol = MockAuthProtocol()

        # Make send_data raise an exception after first call
        call_count = 0

        async def failing_send_data(_data: bytes) -> None:
            nonlocal call_count
            call_count += 1
            if call_count > 1:
                msg = "Network failure"
                raise ConnectionError(msg)
            # Don't call original, just pass

        mock_protocol.send_data.side_effect = failing_send_data

        # Mock sleep to trigger quick re-auth
        original_sleep = asyncio.sleep

        async def quick_sleep(_delay: float) -> None:
            await original_sleep(0.001)  # Very short delay

        asyncio.sleep = quick_sleep  # type: ignore[assignment]

        try:
            await handler.start_authentication(mock_protocol)
            reauth_task = handler._reauth_task

            # Wait for the task to fail
            assert reauth_task is not None
            with pytest.raises(ConnectionError, match="Network failure"):
                await reauth_task

        finally:
            # Restore original sleep
            asyncio.sleep = original_sleep  # type: ignore[assignment]
            # Cleanup
            await handler.stop_authentication()

    def test_email_property_when_accessed_then_returns_email(self) -> None:
        """Test email property returns the configured email."""
        # Arrange
        email = "user@example.com"
        handler = AuthenticationHandler(email)

        # Act & Assert
        assert handler.email == email

    def test_is_active_property_when_not_started_then_returns_false(self) -> None:
        """Test is_active property returns False when not started."""
        # Arrange
        handler = AuthenticationHandler("test@example.com")

        # Act & Assert
        assert not handler.is_active

    @pytest.mark.asyncio
    async def test_is_active_property_when_started_then_returns_true(self) -> None:
        """Test is_active property returns True when authentication is active."""
        # Arrange
        handler = AuthenticationHandler("test@example.com")
        mock_protocol = MockAuthProtocol()

        # Act
        await handler.start_authentication(mock_protocol)

        # Assert
        assert handler.is_active

        # Cleanup
        await handler.stop_authentication()

    @pytest.mark.asyncio
    async def test_is_active_property_when_stopped_then_returns_false(self) -> None:
        """Test is_active property returns False after stopping."""
        # Arrange
        handler = AuthenticationHandler("test@example.com")
        mock_protocol = MockAuthProtocol()
        await handler.start_authentication(mock_protocol)

        # Act
        await handler.stop_authentication()

        # Assert
        assert not handler.is_active

    def test_repr_when_not_active_then_shows_inactive_status(self) -> None:
        """Test __repr__ shows inactive status correctly."""
        # Arrange
        handler = AuthenticationHandler("test@example.com")

        # Act
        repr_str = repr(handler)

        # Assert
        assert "AuthenticationHandler" in repr_str
        assert "test@example.com" in repr_str
        assert "active=False" in repr_str

    @pytest.mark.asyncio
    async def test_repr_when_active_then_shows_active_status(self) -> None:
        """Test __repr__ shows active status correctly."""
        # Arrange
        handler = AuthenticationHandler("test@example.com")
        mock_protocol = MockAuthProtocol()

        # Act
        await handler.start_authentication(mock_protocol)
        repr_str = repr(handler)

        # Assert
        assert "AuthenticationHandler" in repr_str
        assert "test@example.com" in repr_str
        assert "active=True" in repr_str

        # Cleanup
        await handler.stop_authentication()

    def test_reauth_interval_constant_when_accessed_then_has_expected_value(self) -> None:
        """Test REAUTH_INTERVAL constant has the expected value."""
        # Act & Assert
        assert AuthenticationHandler.REAUTH_INTERVAL == 115.0

    def test_logon_format_constant_when_accessed_then_has_expected_format(self) -> None:
        """Test LOGON_FORMAT constant has the expected format string."""
        # Act & Assert
        assert AuthenticationHandler.LOGON_FORMAT == "ByteBlast Client|NM-{email}|V2"

    @pytest.mark.asyncio
    async def test_concurrent_start_stop_when_multiple_operations_then_handles_gracefully(
        self,
    ) -> None:
        """Test handler gracefully handles concurrent start/stop operations."""
        # Arrange
        handler = AuthenticationHandler("test@example.com")
        mock_protocol = MockAuthProtocol()

        # Act - Start and immediately stop multiple times
        tasks: list[asyncio.Task[None]] = []
        for _ in range(3):
            tasks.append(asyncio.create_task(handler.start_authentication(mock_protocol)))
            tasks.append(asyncio.create_task(handler.stop_authentication()))

        # Wait for all operations to complete
        await asyncio.gather(*tasks, return_exceptions=True)

        # Assert - Should be in a clean state
        assert not handler.is_active
        assert handler._reauth_task is None

    @pytest.mark.asyncio
    async def test_authentication_integration_when_full_cycle_then_works_correctly(self) -> None:
        """Test complete authentication cycle integration."""
        # Arrange
        email = "integration@test.com"
        handler = AuthenticationHandler(email)
        mock_protocol = MockAuthProtocol()
        expected_logon = xor_encode_string(f"ByteBlast Client|NM-{email}|V2", encoding="ascii")

        # Act - Full cycle: start, verify active, stop, verify inactive
        assert not handler.is_active

        await handler.start_authentication(mock_protocol)
        assert handler.is_active
        assert handler.email == email
        mock_protocol.send_data.assert_called_with(expected_logon)

        await handler.stop_authentication()
        assert not handler.is_active

        # Assert final state
        repr_str = repr(handler)
        assert email in repr_str
        assert "active=False" in repr_str
