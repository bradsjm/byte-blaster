# pyright: reportPrivateUsage=false
"""Comprehensive tests for ByteBlaster client classes.

This module provides extensive test coverage for all client classes including
SegmentStream, ConnectionProtocol, Watchdog, ByteBlasterClientOptions, and
ByteBlasterClient. Tests cover both normal operation and edge cases with
proper mocking and async test patterns.
"""

import asyncio
import logging
import time
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from byteblaster.client import (
    ByteBlasterClient,
    ByteBlasterClientOptions,
    ConnectionProtocol,
    SegmentStream,
    Watchdog,
)
from byteblaster.protocol.models import QBTSegment


class TestSegmentStream:
    """Tests for SegmentStream async iterator functionality."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mock ByteBlasterClient for testing."""
        client = MagicMock()
        client.subscribe = MagicMock()
        client.unsubscribe = MagicMock()
        return client

    @pytest.fixture
    def segment_stream(self, mock_client: MagicMock) -> SegmentStream:
        """Create a SegmentStream instance for testing."""
        return SegmentStream(mock_client, max_queue_size=10)

    def test_segment_stream_when_initialized_then_has_correct_attributes(
        self, segment_stream: SegmentStream, mock_client: MagicMock
    ) -> None:
        """Test SegmentStream initialization sets correct attributes."""
        assert segment_stream._client is mock_client
        assert segment_stream._queue.maxsize == 10
        assert not segment_stream._closed

    @pytest.mark.asyncio
    async def test_segment_stream_when_entering_context_then_subscribes_handler(
        self, segment_stream: SegmentStream, mock_client: MagicMock
    ) -> None:
        """Test SegmentStream context entry subscribes to client."""
        async with segment_stream as stream:
            assert stream is segment_stream
            mock_client.subscribe.assert_called_once_with(segment_stream._enqueue_segment)

    @pytest.mark.asyncio
    async def test_segment_stream_when_exiting_context_then_unsubscribes_and_closes(
        self, segment_stream: SegmentStream, mock_client: MagicMock
    ) -> None:
        """Test SegmentStream context exit unsubscribes and closes stream."""
        async with segment_stream:
            pass

        assert segment_stream._closed
        mock_client.unsubscribe.assert_called_once_with(segment_stream._enqueue_segment)

    @pytest.mark.asyncio
    async def test_segment_stream_when_iterating_then_yields_segments(
        self, segment_stream: SegmentStream
    ) -> None:
        """Test SegmentStream async iteration yields queued segments."""
        test_segment = QBTSegment(filename="test.txt", block_number=1, total_blocks=1)

        # Queue a segment
        await segment_stream._enqueue_segment(test_segment)

        # Test iteration
        async with segment_stream as stream:
            segment = await stream.__anext__()
            assert segment is test_segment

    @pytest.mark.asyncio
    async def test_segment_stream_when_closed_then_raises_stop_iteration(
        self, segment_stream: SegmentStream
    ) -> None:
        """Test SegmentStream raises StopAsyncIteration when closed."""
        async with segment_stream as stream:
            segment_stream._closed = True
            with pytest.raises(StopAsyncIteration):
                await stream.__anext__()

    @pytest.mark.asyncio
    async def test_segment_stream_when_queue_full_then_drops_segment_with_warning(
        self, segment_stream: SegmentStream, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test SegmentStream drops segments when queue is full."""
        # Fill the queue to capacity
        for i in range(10):
            await segment_stream._enqueue_segment(
                QBTSegment(filename=f"test{i}.txt", block_number=1, total_blocks=1)
            )

        # Try to add one more segment
        with caplog.at_level(logging.WARNING):
            await segment_stream._enqueue_segment(
                QBTSegment(filename="overflow.txt", block_number=1, total_blocks=1)
            )

        assert "Segment stream queue full" in caplog.text

    @pytest.mark.asyncio
    async def test_segment_stream_when_closed_then_ignores_new_segments(
        self, segment_stream: SegmentStream
    ) -> None:
        """Test SegmentStream ignores segments when closed."""
        segment_stream._closed = True
        test_segment = QBTSegment(filename="test.txt", block_number=1, total_blocks=1)

        # Should not raise exception or queue segment
        await segment_stream._enqueue_segment(test_segment)
        assert segment_stream._queue.empty()


class TestConnectionProtocol:
    """Tests for ConnectionProtocol network handling functionality."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mock ByteBlasterClient for testing."""
        client = MagicMock()
        client.decoder = MagicMock()
        client.set_remote_address = MagicMock()
        client.on_connection_made = AsyncMock()
        client.on_connection_lost = AsyncMock()
        client.on_protocol_error = MagicMock()
        return client

    @pytest.fixture
    def protocol(self, mock_client: MagicMock) -> ConnectionProtocol:
        """Create a ConnectionProtocol instance for testing."""
        return ConnectionProtocol(mock_client)

    def test_connection_protocol_when_initialized_then_has_correct_state(
        self, protocol: ConnectionProtocol, mock_client: MagicMock
    ) -> None:
        """Test ConnectionProtocol initialization sets correct initial state."""
        assert protocol._client is mock_client
        assert protocol._transport is None
        assert not protocol._connected

    @patch("asyncio.create_task")
    def test_connection_made_when_valid_transport_then_sets_connected_state(
        self, mock_create_task: MagicMock, protocol: ConnectionProtocol, mock_client: MagicMock
    ) -> None:
        """Test connection_made sets up transport and connection state."""
        mock_transport = MagicMock(spec=asyncio.Transport)
        mock_transport.get_extra_info.return_value = ("192.168.1.1", 8080)

        protocol.connection_made(mock_transport)

        assert protocol._transport is mock_transport
        assert protocol._connected
        mock_client.set_remote_address.assert_called_once_with("192.168.1.1:8080")
        mock_client.on_connection_made.assert_called_once()
        mock_create_task.assert_called_once()

    def test_connection_made_when_invalid_transport_then_raises_type_error(
        self, protocol: ConnectionProtocol
    ) -> None:
        """Test connection_made raises TypeError for invalid transport."""
        with pytest.raises(TypeError, match="Expected asyncio.Transport"):
            protocol.connection_made("not a transport")  # type: ignore[arg-type]

    @patch("asyncio.create_task")
    def test_connection_lost_when_called_then_resets_state_and_notifies_client(
        self, mock_create_task: MagicMock, protocol: ConnectionProtocol, mock_client: MagicMock
    ) -> None:
        """Test connection_lost resets state and notifies client."""
        # Set up connected state
        mock_transport = MagicMock(spec=asyncio.Transport)
        protocol.connection_made(mock_transport)

        # Test connection lost
        test_exception = ConnectionError("Network error")
        protocol.connection_lost(test_exception)

        assert not protocol._connected
        assert protocol._transport is None
        mock_client.on_connection_lost.assert_called_once_with(test_exception)
        assert (
            mock_create_task.call_count == 2
        )  # Once for connection_made, once for connection_lost

    @patch("asyncio.create_task")
    def test_connection_lost_when_no_exception_then_logs_clean_closure(
        self, mock_create_task: MagicMock, protocol: ConnectionProtocol, mock_client: MagicMock
    ) -> None:
        """Test connection_lost handles clean closure without exception."""
        protocol.connection_lost(None)

        assert not protocol._connected
        mock_client.on_connection_lost.assert_called_once_with(None)
        mock_create_task.assert_called_once()

    def test_data_received_when_valid_data_then_feeds_to_decoder(
        self, protocol: ConnectionProtocol, mock_client: MagicMock
    ) -> None:
        """Test data_received forwards data to client decoder."""
        test_data = b"test data"

        protocol.data_received(test_data)

        mock_client.decoder.feed.assert_called_once_with(test_data)

    def test_data_received_when_decoder_raises_exception_then_handles_error(
        self, protocol: ConnectionProtocol, mock_client: MagicMock
    ) -> None:
        """Test data_received handles decoder exceptions gracefully."""
        test_exception = ValueError("Decoder error")
        mock_client.decoder.feed.side_effect = test_exception

        protocol.data_received(b"bad data")

        mock_client.on_protocol_error.assert_called_once_with(test_exception)

    @pytest.mark.asyncio
    async def test_send_data_when_connected_then_writes_to_transport(
        self, protocol: ConnectionProtocol
    ) -> None:
        """Test send_data writes data to transport when connected."""
        mock_transport = MagicMock(spec=asyncio.Transport)
        protocol.connection_made(mock_transport)

        test_data = b"test message"
        await protocol.send_data(test_data)

        mock_transport.write.assert_called_once_with(test_data)

    @pytest.mark.asyncio
    async def test_send_data_when_not_connected_then_raises_runtime_error(
        self, protocol: ConnectionProtocol
    ) -> None:
        """Test send_data raises RuntimeError when not connected."""
        with pytest.raises(RuntimeError, match="Not connected to server"):
            await protocol.send_data(b"test data")

    def test_error_received_when_called_then_logs_and_notifies_client(
        self, protocol: ConnectionProtocol, mock_client: MagicMock
    ) -> None:
        """Test error_received logs error and notifies client."""
        test_exception = OSError("Protocol error")

        protocol.error_received(test_exception)

        mock_client.on_protocol_error.assert_called_once_with(test_exception)

    @patch("asyncio.create_task")
    def test_is_connected_when_connected_then_returns_true(
        self, protocol: ConnectionProtocol
    ) -> None:
        """Test is_connected property returns True when connected."""
        mock_transport = MagicMock(spec=asyncio.Transport)
        protocol.connection_made(mock_transport)

        assert protocol.is_connected

    def test_is_connected_when_not_connected_then_returns_false(
        self, protocol: ConnectionProtocol
    ) -> None:
        """Test is_connected property returns False when not connected."""
        assert not protocol.is_connected


class TestWatchdog:
    """Tests for Watchdog connection monitoring functionality."""

    @pytest.fixture
    def watchdog(self) -> Watchdog:
        """Create a Watchdog instance for testing."""
        return Watchdog(timeout=1.0, max_exceptions=3)

    def test_watchdog_when_initialized_then_has_correct_defaults(self, watchdog: Watchdog) -> None:
        """Test Watchdog initialization sets correct default values."""
        assert watchdog._timeout == 1.0
        assert watchdog._max_exceptions == 3
        assert watchdog._exception_count == 0
        assert watchdog._task is None
        assert not watchdog._active

    @pytest.mark.asyncio
    async def test_watchdog_when_started_then_begins_monitoring(self, watchdog: Watchdog) -> None:
        """Test Watchdog start begins monitoring task."""
        close_callback = AsyncMock()

        await watchdog.start(close_callback)

        assert watchdog._active
        assert watchdog._task is not None
        assert not watchdog._task.done()

        await watchdog.stop()

    @pytest.mark.asyncio
    async def test_watchdog_when_stopped_then_cancels_monitoring(self, watchdog: Watchdog) -> None:
        """Test Watchdog stop cancels monitoring task."""
        close_callback = AsyncMock()
        await watchdog.start(close_callback)

        await watchdog.stop()

        assert not watchdog._active
        assert watchdog._task is None

    def test_watchdog_when_data_received_then_updates_timestamp(self, watchdog: Watchdog) -> None:
        """Test on_data_received updates last data timestamp."""
        initial_time = watchdog._last_data_time

        watchdog.on_data_received()

        assert watchdog._last_data_time > initial_time

    def test_watchdog_when_exception_occurs_then_increments_counter(
        self, watchdog: Watchdog
    ) -> None:
        """Test on_exception increments exception counter."""
        initial_count = watchdog._exception_count

        watchdog.on_exception()

        assert watchdog._exception_count == initial_count + 1

    @pytest.mark.asyncio
    async def test_watchdog_when_timeout_exceeded_then_calls_close_callback(
        self, watchdog: Watchdog
    ) -> None:
        """Test Watchdog calls close callback when timeout is exceeded."""
        close_callback = AsyncMock()

        # Set last data time to past timeout threshold
        await watchdog.start(close_callback)
        watchdog._last_data_time = time.monotonic() - 2.0

        # Wait for monitoring loop to detect timeout
        await asyncio.sleep(1.1)

        close_callback.assert_called_once()
        await watchdog.stop()

    @pytest.mark.asyncio
    async def test_watchdog_when_exception_threshold_exceeded_then_calls_close_callback(
        self, watchdog: Watchdog
    ) -> None:
        """Test Watchdog calls close callback when exception threshold is exceeded."""
        close_callback = AsyncMock()

        await watchdog.start(close_callback)

        # Exceed exception threshold
        for _ in range(4):
            watchdog.on_exception()

        # Wait for monitoring loop to detect threshold
        await asyncio.sleep(1.1)

        close_callback.assert_called_once()
        await watchdog.stop()

    @pytest.mark.asyncio
    async def test_watchdog_when_monitoring_loop_cancelled_then_handles_gracefully(
        self, watchdog: Watchdog
    ) -> None:
        """Test Watchdog handles monitoring loop cancellation gracefully."""
        close_callback = AsyncMock()

        await watchdog.start(close_callback)
        task = watchdog._task

        # Cancel the task directly
        if task:
            task.cancel()

        await watchdog.stop()

        assert not watchdog._active


class TestByteBlasterClientOptions:
    """Tests for ByteBlasterClientOptions configuration."""

    def test_byte_blaster_client_options_when_minimal_config_then_has_defaults(self) -> None:
        """Test ByteBlasterClientOptions uses correct defaults."""
        options = ByteBlasterClientOptions(email="test@example.com")

        assert options.email == "test@example.com"
        assert options.server_list_path == "servers.json"
        assert options.watchdog_timeout == 20.0
        assert options.max_exceptions == 10
        assert options.reconnect_delay == 5.0
        assert options.connection_timeout == 10.0

    def test_byte_blaster_client_options_when_custom_config_then_overrides_defaults(self) -> None:
        """Test ByteBlasterClientOptions accepts custom configuration."""
        options = ByteBlasterClientOptions(
            email="custom@example.com",
            server_list_path="/custom/path.json",
            watchdog_timeout=30.0,
            max_exceptions=5,
            reconnect_delay=2.0,
            connection_timeout=15.0,
        )

        assert options.email == "custom@example.com"
        assert options.server_list_path == "/custom/path.json"
        assert options.watchdog_timeout == 30.0
        assert options.max_exceptions == 5
        assert options.reconnect_delay == 2.0
        assert options.connection_timeout == 15.0


class TestByteBlasterClient:
    """Tests for ByteBlasterClient main functionality."""

    @pytest.fixture
    def client_options(self) -> ByteBlasterClientOptions:
        """Create test client options."""
        return ByteBlasterClientOptions(
            email="test@example.com",
            watchdog_timeout=1.0,
            max_exceptions=3,
            reconnect_delay=0.1,
            connection_timeout=1.0,
        )

    @pytest.fixture
    def mock_server_manager(self) -> MagicMock:
        """Create a mock ServerListManager."""
        manager = MagicMock()
        manager.__len__ = MagicMock(return_value=2)
        manager.get_next_server = MagicMock(return_value=("localhost", 8080))

        # Mock the get_current_server_list method
        mock_server_list = MagicMock()
        mock_server_list.servers = [("server1", 8080), ("server2", 8080)]
        manager.get_current_server_list = MagicMock(return_value=mock_server_list)

        manager.save_server_list = MagicMock()
        return manager

    @pytest.fixture
    def mock_auth_handler(self) -> MagicMock:
        """Create a mock AuthenticationHandler."""
        handler = MagicMock()
        handler.start_authentication = AsyncMock()
        handler.stop_authentication = AsyncMock()
        return handler

    @pytest.fixture
    def mock_decoder(self) -> MagicMock:
        """Create a mock ProtocolDecoder."""
        decoder = MagicMock()
        # Configure state as a readable property
        decoder.state = "RESYNC"
        decoder.set_remote_address = MagicMock()
        return decoder

    @pytest.fixture
    def mock_watchdog(self) -> MagicMock:
        """Create a mock Watchdog."""
        watchdog = MagicMock()
        watchdog.start = AsyncMock()
        watchdog.stop = AsyncMock()
        watchdog.on_exception = MagicMock()
        watchdog.on_data_received = MagicMock()
        return watchdog

    @pytest.fixture
    def client(
        self,
        client_options: ByteBlasterClientOptions,
        mock_server_manager: MagicMock,
        mock_auth_handler: MagicMock,
        mock_decoder: MagicMock,
        mock_watchdog: MagicMock,
    ) -> ByteBlasterClient:
        """Create a ByteBlasterClient with mocked dependencies."""
        with (
            patch("byteblaster.client.ServerListManager", return_value=mock_server_manager),
            patch("byteblaster.client.AuthenticationHandler", return_value=mock_auth_handler),
            patch("byteblaster.client.ProtocolDecoder", return_value=mock_decoder),
            patch("byteblaster.client.Watchdog", return_value=mock_watchdog),
        ):
            client = ByteBlasterClient(client_options)
            # Type cast to help type checker understand these are mocked
            client._server_manager = cast("MagicMock", client._server_manager)
            client._auth_handler = cast("MagicMock", client._auth_handler)
            client._decoder = cast("MagicMock", client._decoder)
            client._watchdog = cast("MagicMock", client._watchdog)
            return client

    def test_byte_blaster_client_when_initialized_then_has_correct_configuration(
        self, client: ByteBlasterClient, client_options: ByteBlasterClientOptions
    ) -> None:
        """Test ByteBlasterClient initialization sets correct configuration."""
        assert client._email == client_options.email
        assert client._reconnect_delay == client_options.reconnect_delay
        assert client._connection_timeout == client_options.connection_timeout
        assert not client._running
        assert not client._connected
        assert client._protocol is None

    def test_byte_blaster_client_when_subscribe_called_then_adds_handler(
        self, client: ByteBlasterClient
    ) -> None:
        """Test subscribe adds handler to the list."""
        handler = MagicMock()

        client.subscribe(handler)

        assert handler in client._segment_handlers

    def test_byte_blaster_client_when_subscribe_duplicate_then_ignores_duplicate(
        self, client: ByteBlasterClient
    ) -> None:
        """Test subscribe ignores duplicate handlers."""
        handler = MagicMock()

        client.subscribe(handler)
        client.subscribe(handler)

        assert client._segment_handlers.count(handler) == 1

    def test_byte_blaster_client_when_unsubscribe_called_then_removes_handler(
        self, client: ByteBlasterClient
    ) -> None:
        """Test unsubscribe removes handler from the list."""
        handler = MagicMock()
        client.subscribe(handler)

        client.unsubscribe(handler)

        assert handler not in client._segment_handlers

    def test_byte_blaster_client_when_unsubscribe_nonexistent_then_no_error(
        self, client: ByteBlasterClient
    ) -> None:
        """Test unsubscribe handles non-existent handlers gracefully."""
        handler = MagicMock()

        # Should not raise exception
        client.unsubscribe(handler)

    def test_byte_blaster_client_when_stream_segments_called_then_returns_segment_stream(
        self, client: ByteBlasterClient
    ) -> None:
        """Test stream_segments returns SegmentStream instance."""
        stream = client.stream_segments(max_queue_size=100)

        assert isinstance(stream, SegmentStream)
        assert stream._client is client

    @pytest.mark.asyncio
    async def test_byte_blaster_client_when_start_called_then_begins_operation(
        self, client: ByteBlasterClient
    ) -> None:
        """Test start method begins client operation."""
        with patch.object(client, "_connection_loop", new_callable=AsyncMock) as mock_loop:
            await client.start()

            assert client._running
            mock_loop.assert_called_once()

        await client.stop()

    @pytest.mark.asyncio
    async def test_byte_blaster_client_when_start_called_twice_then_warns_and_ignores(
        self, client: ByteBlasterClient, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test start method warns when called on already running client."""
        with patch.object(client, "_connection_loop", new_callable=AsyncMock):
            await client.start()

            with caplog.at_level(logging.WARNING):
                await client.start()

            assert "Client already running" in caplog.text

        await client.stop()

    @pytest.mark.asyncio
    async def test_byte_blaster_client_when_stop_called_then_stops_operation(
        self, client: ByteBlasterClient
    ) -> None:
        """Test stop method stops client operation."""
        with (
            patch.object(client, "_connection_loop", new_callable=AsyncMock),
            patch.object(client, "_close_connection", new_callable=AsyncMock) as mock_close,
        ):
            await client.start()
            await client.stop()

            assert not client._running
            mock_close.assert_called_once()

    def test_byte_blaster_client_properties_when_disconnected_then_return_correct_values(
        self, client: ByteBlasterClient
    ) -> None:
        """Test client properties return correct values when disconnected."""
        assert not client.is_connected
        assert not client.is_running
        assert client.server_count == 2  # From mock_server_manager
        assert client.email == "test@example.com"

    def test_byte_blaster_client_when_get_server_list_called_then_returns_server_data(
        self, client: ByteBlasterClient
    ) -> None:
        """Test get_server_list returns server manager data."""
        result = client.get_server_list()

        client._server_manager.get_current_server_list.assert_called_once()  # type: ignore[attr-defined]
        assert result is client._server_manager.get_current_server_list.return_value  # type: ignore[attr-defined]

    def test_byte_blaster_client_when_set_remote_address_called_then_updates_decoder(
        self, client: ByteBlasterClient
    ) -> None:
        """Test set_remote_address updates decoder with address."""
        test_address = "192.168.1.1:8080"

        client.set_remote_address(test_address)

        client._decoder.set_remote_address.assert_called_once_with(test_address)  # type: ignore[attr-defined]

    def test_byte_blaster_client_when_decoder_property_accessed_then_returns_decoder(
        self, client: ByteBlasterClient
    ) -> None:
        """Test decoder property returns the protocol decoder."""
        assert client.decoder is client._decoder

    def test_byte_blaster_client_when_decoder_state_property_accessed_then_returns_state(
        self, client: ByteBlasterClient
    ) -> None:
        """Test decoder_state property returns decoder state."""
        # Configure the mock state to return the desired state
        client._decoder.configure_mock(state="CONNECTED")  # type: ignore[attr-defined]

        assert client.decoder_state == "CONNECTED"

    def test_byte_blaster_client_when_on_frame_received_with_data_segment_then_handles_async(
        self, client: ByteBlasterClient
    ) -> None:
        """Test on_frame_received creates task for data segment handling."""
        from byteblaster.protocol.models import DataBlockFrame

        frame = DataBlockFrame(
            content=b"test data",
            segment=QBTSegment(filename="test.txt", block_number=1, total_blocks=1),
        )

        with patch("asyncio.create_task") as mock_create_task:
            client.on_frame_received(frame)

            mock_create_task.assert_called_once()

    def test_byte_blaster_client_when_on_frame_received_with_server_list_then_updates_list(
        self, client: ByteBlasterClient
    ) -> None:
        """Test on_frame_received updates server list for server list frames."""
        from byteblaster.protocol.models import ByteBlasterServerList, ServerListFrame

        server_list = ByteBlasterServerList(servers=[("server1", 8080), ("server2", 8080)])
        frame = ServerListFrame(content=b"server list data", server_list=server_list)

        client.on_frame_received(frame)

        client._server_manager.save_server_list.assert_called_once_with(server_list)  # type: ignore[attr-defined]

    def test_byte_blaster_client_when_on_protocol_error_called_then_notifies_watchdog(
        self, client: ByteBlasterClient
    ) -> None:
        """Test on_protocol_error notifies watchdog of exception."""
        test_error = ValueError("Protocol error")

        client.on_protocol_error(test_error)

        client._watchdog.on_exception.assert_called_once()  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_byte_blaster_client_when_handle_data_segment_called_then_notifies_handlers(
        self, client: ByteBlasterClient
    ) -> None:
        """Test _handle_data_segment notifies all registered handlers."""
        sync_handler = MagicMock()
        async_handler = AsyncMock()

        client.subscribe(sync_handler)
        client.subscribe(async_handler)

        test_segment = QBTSegment(filename="test.txt", block_number=1, total_blocks=1)

        await client._handle_data_segment(test_segment)

        sync_handler.assert_called_once_with(test_segment)
        async_handler.assert_called_once_with(test_segment)

    @pytest.mark.asyncio
    async def test_byte_blaster_client_when_handler_raises_exception_then_continues(
        self, client: ByteBlasterClient, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test client continues processing when handler raises exception."""
        failing_handler = MagicMock(side_effect=ValueError("Handler error"))
        working_handler = MagicMock()

        client.subscribe(failing_handler)
        client.subscribe(working_handler)

        test_segment = QBTSegment(filename="test.txt", block_number=1, total_blocks=1)

        with caplog.at_level(logging.ERROR):
            await client._handle_data_segment(test_segment)

        # Both handlers should be called despite the first one failing
        failing_handler.assert_called_once_with(test_segment)
        working_handler.assert_called_once_with(test_segment)
        assert "Sync segment handler error" in caplog.text

    def test_byte_blaster_client_when_repr_called_then_returns_formatted_string(
        self, client: ByteBlasterClient
    ) -> None:
        """Test __repr__ returns properly formatted string representation."""
        result = repr(client)

        expected = (
            "ByteBlasterClient(email='test@example.com', running=False, connected=False, servers=2)"
        )
        assert result == expected

    @pytest.mark.asyncio
    @patch("asyncio.create_task")
    async def test_byte_blaster_client_when_connection_made_then_starts_auth_and_watchdog(
        self,
        mock_create_task: MagicMock,  # noqa: ARG002
        client: ByteBlasterClient,
    ) -> None:
        """Test on_connection_made starts authentication and watchdog."""
        # Set up mock protocol to avoid early return
        mock_protocol = MagicMock()
        client._protocol = mock_protocol

        await client.on_connection_made()

        client._auth_handler.start_authentication.assert_called_once_with(mock_protocol)  # type: ignore[attr-defined]
        client._watchdog.start.assert_called_once()  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_byte_blaster_client_when_connection_lost_then_updates_state(
        self, client: ByteBlasterClient
    ) -> None:
        """Test on_connection_lost updates connection state."""
        client._connected = True

        await client.on_connection_lost(None)

        assert not client._connected
        client._connection_lost_event.is_set()

    @pytest.mark.asyncio
    async def test_byte_blaster_client_when_close_connection_then_cleans_up_resources(
        self, client: ByteBlasterClient
    ) -> None:
        """Test _close_connection performs proper cleanup."""
        mock_protocol = MagicMock()
        mock_transport = MagicMock()
        mock_protocol._transport = mock_transport
        client._protocol = mock_protocol

        await client._close_connection()

        mock_transport.close.assert_called_once()
        client._watchdog.stop.assert_called_once()  # type: ignore[attr-defined]
        client._auth_handler.stop_authentication.assert_called_once()  # type: ignore[attr-defined]
        assert client._protocol is None
