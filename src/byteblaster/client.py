"""Main ByteBlaster client implementation.

This module provides the ByteBlasterClient class, which is the primary interface
for connecting to ByteBlaster servers and receiving EMWIN data using the Quick
Block Transfer protocol.
"""

import asyncio
import contextlib
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from byteblaster.protocol.auth import AuthenticationHandler, AuthProtocol
from byteblaster.protocol.decoder import ProtocolDecoder, DecoderState
from byteblaster.protocol.models import (
    DataBlockFrame,
    ProtocolFrame,
    QBTSegment,
    ServerListFrame,
)
from byteblaster.utils import ServerListManager

logger = logging.getLogger(__name__)

type SegmentHandler = Callable[[QBTSegment], None]
type AsyncSegmentHandler = Callable[[QBTSegment], Any]


class ConnectionProtocol(asyncio.Protocol, AuthProtocol):
    """Network protocol handler for ByteBlaster connections."""

    def __init__(self, client: "ByteBlasterClient") -> None:
        """Initialize connection protocol.

        Args:
            client: Parent ByteBlaster client

        """
        self._client = client
        self._transport: asyncio.Transport | None = None
        self._connected = False

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        """Establish connection and initialize client state."""
        if not isinstance(transport, asyncio.Transport):
            msg = "Expected asyncio.Transport"
            raise TypeError(msg)

        self._transport = transport
        self._connected = True

        peer_info = transport.get_extra_info("peername")
        address = "unknown"
        if peer_info:
            address = f"{peer_info[0]}:{peer_info[1]}"
            self._client.set_remote_address(address)

        logger.info("Connected to %s", address)
        self._connection_task = asyncio.create_task(self._client.on_connection_made())

    def connection_lost(self, exc: Exception | None) -> None:
        """Handle connection loss and notify client."""
        self._connected = False
        self._transport = None

        if exc:
            logger.warning("Connection lost with error: %s", exc)
        else:
            logger.info("Connection closed")

        self._disconnect_task = asyncio.create_task(self._client.on_connection_lost(exc))

    def data_received(self, data: bytes) -> None:
        """Process received data through protocol decoder."""
        try:
            self._client.decoder.feed(data)
        except Exception as e:
            logger.exception("Error processing received data")
            self._client.on_protocol_error(e)

    async def send_data(self, data: bytes) -> None:
        """Send data to remote server."""
        if not self._transport or not self._connected:
            msg = "Not connected to server"
            raise RuntimeError(msg)

        self._transport.write(data)

    def error_received(self, exc: Exception) -> None:
        """Handle protocol errors and notify client."""
        logger.error("Protocol error: %s", exc)
        self._client.on_protocol_error(exc)

    @property
    def is_connected(self) -> bool:
        """Check if connection is active."""
        return self._connected and self._transport is not None


class Watchdog:
    """Connection watchdog for monitoring health."""

    def __init__(
        self,
        timeout: float = 20.0,
        max_exceptions: int = 10,
    ) -> None:
        """Initialize watchdog.

        Args:
            timeout: Timeout in seconds for data reception
            max_exceptions: Maximum exceptions before closing connection

        """
        self._timeout = timeout
        self._max_exceptions = max_exceptions
        self._exception_count = 0
        self._last_data_time = 0.0
        self._task: asyncio.Task[None] | None = None
        self._active = False

    async def start(self, close_callback: Callable[[], Any]) -> None:
        """Start watchdog monitoring.

        Args:
            close_callback: Callback to call when connection should be closed

        """
        self._active = True
        self._last_data_time = asyncio.get_event_loop().time()
        self._exception_count = 0

        self._task = asyncio.create_task(self._monitor_loop(close_callback))
        logger.debug("Watchdog started")

    async def stop(self) -> None:
        """Stop watchdog monitoring."""
        self._active = False

        if self._task and not self._task.done():
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task

        self._task = None
        logger.debug("Watchdog stopped")

    def on_data_received(self) -> None:
        """Reset timeout when data is received."""
        self._last_data_time = asyncio.get_event_loop().time()

    def on_exception(self) -> None:
        """Increment exception count when an exception occurs."""
        self._exception_count += 1
        logger.debug("Watchdog exception count: %d", self._exception_count)

    async def _monitor_loop(self, close_callback: Callable[[], Any]) -> None:
        """Monitor connection health and close if needed."""
        try:
            while self._active:
                await asyncio.sleep(self._timeout)

                if not self._active:
                    break

                current_time = asyncio.get_event_loop().time()
                time_since_data = current_time - self._last_data_time

                if time_since_data > self._timeout:
                    logger.warning("No data received in %.1f seconds", time_since_data)
                    await close_callback()
                    break

                if self._exception_count > self._max_exceptions:
                    logger.warning("Exception threshold exceeded: %d", self._exception_count)
                    await close_callback()
                    break

        except asyncio.CancelledError:
            logger.debug("Watchdog monitor loop cancelled")
            raise
        except Exception:
            logger.exception("Watchdog monitor error")


@dataclass
class ByteBlasterClientOptions:
    """Configuration options for ByteBlasterClient."""

    email: str
    """Email address for server authentication."""
    server_list_path: str = "servers.json"
    """Path to server list persistence file."""
    watchdog_timeout: float = 20.0
    """Watchdog timeout in seconds for data reception."""
    max_exceptions: int = 10
    """Maximum exceptions before closing connection."""
    reconnect_delay: float = 5.0
    """Delay in seconds between reconnection attempts."""
    connection_timeout: float = 10.0
    """Timeout in seconds for connection attempts."""


class ByteBlasterClient:
    """Main ByteBlaster client for connecting to EMWIN servers.

    This class provides a high-level interface for connecting to ByteBlaster
    servers, handling authentication, protocol decoding, and data distribution.
    """

    def __init__(
        self,
        options: ByteBlasterClientOptions,
    ) -> None:
        """Initialize ByteBlaster client.

        Args:
            options: Configuration options for the client

        """
        self._email = options.email
        self._reconnect_delay = options.reconnect_delay
        self._connection_timeout = options.connection_timeout

        # Core components
        self._server_manager = ServerListManager(options.server_list_path)
        self._auth_handler = AuthenticationHandler(options.email)
        self._decoder = ProtocolDecoder(self.on_frame_received)
        self._watchdog = Watchdog(options.watchdog_timeout, options.max_exceptions)

        # Connection state
        self._protocol: ConnectionProtocol | None = None
        self._running = False
        self._connected = False
        self._reconnect_task: asyncio.Task[None] | None = None
        self._connection_lost_event = asyncio.Event()

        # Event handlers
        self._segment_handlers: list[SegmentHandler | AsyncSegmentHandler] = []

    def subscribe(self, handler: SegmentHandler | AsyncSegmentHandler) -> None:
        """Subscribe to data segment events.

        Args:
            handler: Function to call when segments are received

        """
        if handler not in self._segment_handlers:
            self._segment_handlers.append(handler)
            logger.debug("Added segment handler: %s", handler)

    def unsubscribe(self, handler: SegmentHandler | AsyncSegmentHandler) -> None:
        """Unsubscribe from data segment events.

        Args:
            handler: Handler function to remove

        """
        if handler in self._segment_handlers:
            self._segment_handlers.remove(handler)
            logger.debug("Removed segment handler: %s", handler)

    async def start(self) -> None:
        """Start the ByteBlaster client."""
        if self._running:
            logger.warning("Client already running")
            return

        self._running = True
        logger.info("Starting ByteBlaster client")

        # Start connection loop
        self._reconnect_task = asyncio.create_task(self._connection_loop())

    async def stop(self, timeout: float | None = None) -> None:
        """Stop the ByteBlaster client.

        Args:
            timeout: Timeout for graceful shutdown

        """
        if not self._running:
            return

        logger.info("Stopping ByteBlaster client")
        self._running = False

        # Cancel reconnection task
        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()
            with contextlib.suppress(TimeoutError, asyncio.CancelledError):
                await asyncio.wait_for(self._reconnect_task, timeout=timeout)

        # Close current connection
        await self._close_connection()
        logger.info("ByteBlaster client stopped")

    @property
    def is_connected(self) -> bool:
        """Check if client is connected to a server."""
        return self._connected and self._protocol is not None

    @property
    def is_running(self) -> bool:
        """Check if client is running."""
        return self._running

    @property
    def server_count(self) -> int:
        """Get number of available servers."""
        return len(self._server_manager)

    @property
    def email(self) -> str:
        """Get email address used for authentication."""
        return self._email

    def get_server_list(self) -> Any:
        """Get current server list."""
        return self._server_manager.get_current_server_list()

    async def _connection_loop(self) -> None:
        """Run main connection loop with automatic reconnection."""
        consecutive_failures = 0
        max_consecutive_failures = self.server_count * 2  # Try all servers twice before backing off

        try:
            while self._running:
                server = self._server_manager.get_next_server()
                if not server:
                    logger.error("No servers available")
                    await asyncio.sleep(self._reconnect_delay)
                    continue

                host, port = server
                logger.info(
                    "Attempting connection to %s:%d (attempt %d)",
                    host,
                    port,
                    consecutive_failures + 1,
                )

                try:
                    await self._connect_to_server(host, port)
                    consecutive_failures = 0  # Reset failure count on successful connection

                    logger.info("Successfully connected to %s:%d", host, port)

                    # Wait for connection to be lost
                    self._connection_lost_event.clear()
                    await self._connection_lost_event.wait()

                except (TimeoutError, ConnectionRefusedError, OSError) as e:
                    consecutive_failures += 1
                    logger.warning("Connection to %s:%d failed: %s", host, port, e)

                    # If we've failed to connect to all servers multiple times, back off
                    if consecutive_failures >= max_consecutive_failures:
                        backoff_delay = min(self._reconnect_delay * 4, 60.0)  # Cap at 60 seconds
                        logger.warning(
                            "All servers failed %d times, backing off for %.1f seconds",
                            consecutive_failures,
                            backoff_delay,
                        )
                        await asyncio.sleep(backoff_delay)
                        consecutive_failures = 0  # Reset after backoff
                        self._server_manager.reset_index()  # Start from first server again
                        continue

                except Exception:
                    consecutive_failures += 1
                    logger.exception("Unexpected error connecting to %s:%d", host, port)

                # Wait before trying next server (shorter delay for quick failover)
                if self._running and consecutive_failures > 0:
                    await asyncio.sleep(min(self._reconnect_delay, 2.0))

        except asyncio.CancelledError:
            logger.debug("Connection loop cancelled")
            raise
        except Exception:
            logger.exception("Connection loop error")

    async def _connect_to_server(self, host: str, port: int) -> None:
        """Connect to a specific server.

        Args:
            host: Server hostname
            port: Server port

        """
        try:
            loop = asyncio.get_event_loop()
            _, protocol = await asyncio.wait_for(
                loop.create_connection(
                    lambda: ConnectionProtocol(self),
                    host,
                    port,
                ),
                timeout=self._connection_timeout,
            )

            self._protocol = protocol
            self._connected = True

        except TimeoutError:
            logger.warning(
                "Connection to %s:%d timed out after %.1f seconds",
                host,
                port,
                self._connection_timeout,
            )
            raise
        except Exception:
            logger.exception("Failed to connect to %s:%d", host, port)
            raise

    async def _close_connection(self) -> None:
        """Close current connection."""
        self._connected = False

        # Stop watchdog
        await self._watchdog.stop()

        # Stop authentication
        await self._auth_handler.stop_authentication()

        # Close transport
        if self._protocol and self._protocol.is_connected:
            transport = getattr(self._protocol, "_transport", None)
            if transport:
                transport.close()

        self._protocol = None
        logger.debug("Connection closed")

    async def on_connection_made(self) -> None:
        """Initialize connection state when connection is established."""
        if not self._protocol:
            return

        # Start authentication
        await self._auth_handler.start_authentication(self._protocol)

        # Start watchdog
        await self._watchdog.start(self._close_connection)

        logger.info("Connection established and authenticated")

    async def on_connection_lost(self, _exc: Exception | None) -> None:
        """Clean up when connection is lost."""
        self._connected = False
        await self._close_connection()
        self._connection_lost_event.set()

    def on_protocol_error(self, _exc: Exception) -> None:
        """Handle protocol errors by resetting state."""
        self._watchdog.on_exception()
        self._decoder.reset()

    def set_remote_address(self, address: str) -> None:
        """Set remote address for decoder."""
        self._decoder.set_remote_address(address)

    @property
    def decoder(self) -> ProtocolDecoder:
        """Get protocol decoder instance."""
        return self._decoder

    @property
    def decoder_state(self) -> DecoderState:
        """Get current state of the protocol decoder."""
        return self._decoder.state

    def on_frame_received(self, frame: ProtocolFrame) -> None:
        """Handle received protocol frames.

        Args:
            frame: Received protocol frame

        """
        self._watchdog.on_data_received()

        if isinstance(frame, DataBlockFrame) and frame.segment:
            self._data_task = asyncio.create_task(self._handle_data_segment(frame.segment))

        elif isinstance(frame, ServerListFrame) and frame.server_list:
            self._handle_server_list_update(frame.server_list)

    async def _handle_data_segment(self, segment: QBTSegment) -> None:
        """Handle received data segments.

        Args:
            segment: Received data segment

        """
        logger.debug("Received segment: %s", segment)

        # Notify handlers
        for handler in self._segment_handlers.copy():
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(segment)
                else:
                    handler(segment)
            except Exception:
                logger.exception("Segment handler error")

    def _handle_server_list_update(self, server_list: Any) -> None:
        """Handle server list updates.

        Args:
            server_list: Updated server list

        """
        logger.info("Received server list update")
        self._server_manager.save_server_list(server_list)

    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"ByteBlasterClient("
            f"email='{self._email}', "
            f"running={self._running}, "
            f"connected={self._connected}, "
            f"servers={len(self._server_manager)})"
        )
