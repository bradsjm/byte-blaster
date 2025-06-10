"""Main ByteBlaster client implementation.

This module provides the ByteBlasterClient class, which is the primary interface
for connecting to ByteBlaster servers and receiving EMWIN data using the Quick
Block Transfer protocol.
"""

import asyncio
import contextlib
import logging
import types
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Any

from byteblaster.protocol.auth import AuthenticationHandler, AuthProtocol
from byteblaster.protocol.decoder import DecoderState, ProtocolDecoder
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


class SegmentStream:
    """Async iterator for streaming segments with backpressure support.

    This class provides an async iterator interface for receiving QBT segments,
    offering structured concurrency and natural backpressure handling. It can be
    used with 'async with' and 'async for' patterns for reactive programming.

    The stream automatically subscribes to segment events when entering the context
    and unsubscribes when exiting, ensuring proper resource cleanup. If the internal
    queue becomes full, new segments are dropped with logging to prevent memory issues.
    """

    def __init__(self, client: "ByteBlasterClient", max_queue_size: int = 1000) -> None:
        """Initialize segment stream with client and queue configuration.

        Args:
            client: ByteBlasterClient instance to stream segments from
            max_queue_size: Maximum number of segments to buffer (default: 1000)

        """
        self._client = client
        self._queue: asyncio.Queue[QBTSegment | None] = asyncio.Queue(maxsize=max_queue_size)
        self._closed = False

    async def __aenter__(self) -> "SegmentStream":
        """Start streaming when entering context."""
        self._client.subscribe(self._enqueue_segment)
        logger.debug("Started segment stream")
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None:
        """Clean up when exiting context."""
        self._closed = True
        self._client.unsubscribe(self._enqueue_segment)

        # Signal end of stream
        with contextlib.suppress(asyncio.QueueFull):
            self._queue.put_nowait(None)

        logger.debug("Stopped segment stream")

    def __aiter__(self) -> AsyncIterator[QBTSegment]:
        """Return self as async iterator."""
        return self

    async def __anext__(self) -> QBTSegment:
        """Get next segment from stream."""
        while True:
            if self._closed:
                raise StopAsyncIteration
            item = await self._queue.get()
            if item is None:
                raise StopAsyncIteration
            return item

    async def _enqueue_segment(self, segment: QBTSegment) -> None:
        """Queue segment for async iteration with backpressure."""
        if self._closed:
            return

        try:
            # Use put_nowait to avoid blocking the event loop
            # If queue is full, we drop the segment and log a warning
            self._queue.put_nowait(segment)
        except asyncio.QueueFull:
            logger.warning(
                "Segment stream queue full, dropping segment: %s (block %d/%d)",
                segment.filename,
                segment.block_number,
                segment.total_blocks,
            )


class ConnectionProtocol(asyncio.Protocol, AuthProtocol):
    """Network protocol handler for ByteBlaster server connections.

    This class implements the asyncio.Protocol interface to handle low-level network
    communication with ByteBlaster servers. It manages the TCP transport layer,
    connection lifecycle events, and data flow between the network and the parent
    ByteBlaster client. The protocol integrates with the authentication system and
    provides error handling for network-related issues.

    The protocol maintains connection state and automatically forwards received data
    to the client's protocol decoder while handling connection establishment,
    termination, and error conditions gracefully.
    """

    def __init__(self, client: "ByteBlasterClient") -> None:
        """Initialize the connection protocol with a reference to the parent client.

        Sets up the protocol instance with initial state variables and establishes
        the bidirectional communication channel with the ByteBlaster client. The
        protocol starts in a disconnected state and will transition to connected
        when the transport layer establishes a connection.

        Args:
            client: The parent ByteBlaster client instance that owns this protocol.
                   Used for forwarding data, connection events, and error notifications.

        """
        self._client = client
        self._transport: asyncio.Transport | None = None
        self._connected = False

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        """Handle successful connection establishment and initialize transport layer.

        Called by asyncio when a TCP connection is successfully established with
        a ByteBlaster server. This method stores the transport reference, extracts
        peer connection information for logging, and notifies the parent client
        that the connection is ready for authentication and data exchange.

        The method performs transport validation, updates connection state, logs
        connection details, and schedules the client's connection initialization
        routine as an async task.

        Args:
            transport: The asyncio transport object for the established connection.
                      Must be an asyncio.Transport instance for TCP communication.

        Raises:
            TypeError: If the provided transport is not an asyncio.Transport instance.

        """
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
        """Handle connection termination and perform cleanup operations.

        Called by asyncio when the TCP connection is lost, either due to network
        issues, server-side disconnection, or intentional closure. This method
        updates the connection state, clears the transport reference, logs the
        disconnection event, and schedules the client's connection cleanup routine.

        The method distinguishes between clean disconnections and error-based
        disconnections, providing appropriate logging for each scenario. It ensures
        the client is notified asynchronously to handle reconnection logic.

        Args:
            exc: Exception that caused the disconnection, or None for clean closure.
                If present, indicates the specific error that terminated the connection.

        """
        self._connected = False
        self._transport = None

        if exc:
            logger.warning("Connection lost with error: %s", exc)
        else:
            logger.info("Connection closed")

        self._disconnect_task = asyncio.create_task(self._client.on_connection_lost(exc))

    def data_received(self, data: bytes) -> None:
        """Process incoming data from the ByteBlaster server through the protocol decoder.

        Called by asyncio whenever data is received on the TCP connection. This method
        immediately forwards the raw bytes to the client's protocol decoder for parsing
        into structured ByteBlaster protocol frames. Error handling ensures that
        malformed data or decoder issues don't crash the connection.

        The method maintains the data flow pipeline from network transport to protocol
        processing, with comprehensive error handling and logging for debugging
        protocol-related issues.

        Args:
            data: Raw bytes received from the ByteBlaster server containing protocol
                 frames, segments, or partial messages that need to be decoded.

        """
        try:
            self._client.decoder.feed(data)
        except Exception as e:
            logger.exception("Error processing received data")
            self._client.on_protocol_error(e)

    async def send_data(self, data: bytes) -> None:
        """Send data to the connected ByteBlaster server.

        Transmits raw bytes to the remote server using the established TCP transport.
        This method is primarily used by the authentication system to send login
        credentials and acknowledgments. The method validates connection state
        before attempting transmission to prevent errors.

        Args:
            data: Raw bytes to transmit to the server, typically containing
                 authentication messages or protocol control frames.

        Raises:
            RuntimeError: If no active connection exists or transport is unavailable.

        """
        if not self._transport or not self._connected:
            msg = "Not connected to server"
            raise RuntimeError(msg)

        self._transport.write(data)

    def error_received(self, exc: Exception) -> None:
        """Handle protocol-level errors and forward them to the client.

        Called by asyncio when protocol-specific errors occur during data processing
        or transport operations. This method logs the error for debugging purposes
        and notifies the parent client so it can update its error tracking and
        potentially trigger connection recovery procedures.

        Args:
            exc: The protocol error that occurred during communication or data processing.

        """
        logger.error("Protocol error: %s", exc)
        self._client.on_protocol_error(exc)

    @property
    def is_connected(self) -> bool:
        """Check if the protocol has an active connection to a ByteBlaster server.

        Returns:
            True if both the connection state flag is set and a valid transport
            object exists, indicating the protocol can send and receive data.

        """
        return self._connected and self._transport is not None


class Watchdog:
    """Connection health monitor that tracks data flow and error conditions.

    The Watchdog class provides connection health monitoring by tracking data
    reception timeouts and cumulative error counts. It runs an independent
    monitoring loop that can trigger connection closure when health thresholds
    are exceeded, ensuring the client doesn't remain connected to unresponsive
    or problematic servers.

    The watchdog uses configurable timeout and exception thresholds to balance
    connection stability with responsiveness to network issues. It integrates
    with the client's connection management system to provide automated recovery
    from degraded connection conditions.
    """

    def __init__(
        self,
        timeout: float = 20.0,
        max_exceptions: int = 10,
    ) -> None:
        """Initialize the connection watchdog with health monitoring parameters.

        Sets up the watchdog with configurable thresholds for data reception
        timeouts and error accumulation. The watchdog starts in an inactive state
        and must be explicitly started when a connection is established.

        Args:
            timeout: Maximum time in seconds to wait for data reception before
                    considering the connection unhealthy and triggering closure.
            max_exceptions: Maximum number of protocol or processing exceptions
                          to tolerate before forcing connection closure.

        """
        self._timeout = timeout
        self._max_exceptions = max_exceptions
        self._exception_count = 0
        self._last_data_time = 0.0
        self._task: asyncio.Task[None] | None = None
        self._active = False

    async def start(self, close_callback: Callable[[], Any]) -> None:
        """Start the watchdog monitoring loop for connection health tracking.

        Activates the watchdog and begins continuous monitoring of connection health
        metrics including data reception timing and error accumulation. The monitoring
        runs in a separate async task to avoid blocking the main connection loop.

        The watchdog resets its internal counters and timestamps when started, ensuring
        fresh monitoring state for each new connection. The monitoring loop will
        automatically invoke the provided callback if health thresholds are exceeded.

        Args:
            close_callback: Async or sync callable to invoke when the connection
                          should be closed due to health threshold violations.
                          Typically the client's connection closure method.

        """
        self._active = True
        self._last_data_time = asyncio.get_event_loop().time()
        self._exception_count = 0

        self._task = asyncio.create_task(self._monitor_loop(close_callback))
        logger.debug("Watchdog started")

    async def stop(self) -> None:
        """Stop the watchdog monitoring loop and perform cleanup.

        Deactivates the watchdog monitoring system and cancels the monitoring task
        if it's still running. This method ensures graceful shutdown of the watchdog
        without leaving background tasks running after connection closure.

        The method handles task cancellation gracefully, suppressing cancellation
        exceptions that are expected during normal shutdown procedures.
        """
        self._active = False

        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                logger.debug("Watchdog task cancelled during shutdown")

        self._task = None
        logger.debug("Watchdog stopped")

    def on_data_received(self) -> None:
        """Update the data reception timestamp to reset the timeout period.

        Called by the client whenever data is successfully received and processed
        from the ByteBlaster server. This method updates the internal timestamp
        used by the monitoring loop to track data reception intervals and prevent
        false timeout triggers during normal operation.
        """
        self._last_data_time = asyncio.get_event_loop().time()

    def on_exception(self) -> None:
        """Increment the exception counter when protocol or processing errors occur.

        Called by the client whenever an exception is encountered during data
        processing, protocol decoding, or other connection-related operations.
        The watchdog tracks cumulative exceptions to identify connections that
        are consistently problematic and may need to be closed.
        """
        self._exception_count += 1
        logger.debug("Watchdog exception count: %d", self._exception_count)

    async def _monitor_loop(self, close_callback: Callable[[], Any]) -> None:
        """Execute the main monitoring loop that checks connection health metrics.

        Runs continuously while the watchdog is active, periodically checking
        data reception timing and exception counts against configured thresholds.
        When health violations are detected, the loop invokes the close callback
        to trigger connection termination and recovery procedures.

        The monitoring loop uses the configured timeout as both the check interval
        and the maximum allowed time without data reception. This approach provides
        responsive detection of connection issues while avoiding excessive polling.

        Args:
            close_callback: Callable to invoke when connection closure is required
                          due to health threshold violations.

        Raises:
            asyncio.CancelledError: When the monitoring task is cancelled during
                                   normal shutdown procedures.

        """
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
    """Comprehensive configuration options for ByteBlaster client initialization.

    This dataclass encapsulates all configurable parameters for the ByteBlaster
    client, including authentication credentials, connection behavior, monitoring
    thresholds, and file system paths. The options provide fine-grained control
    over client behavior while maintaining sensible defaults for typical usage
    scenarios.

    The configuration supports both operational parameters (timeouts, delays) and
    functional parameters (authentication, persistence) to enable deployment in
    various network environments and operational contexts.
    """

    email: str
    """Email address for server authentication and user identification."""
    server_list_path: str = "servers.json"
    """File system path for server list persistence and automatic updates."""
    watchdog_timeout: float = 20.0
    """Watchdog timeout in seconds for detecting inactive connections."""
    max_exceptions: int = 10
    """Maximum protocol exceptions before forcing connection closure."""
    reconnect_delay: float = 5.0
    """Base delay in seconds between reconnection attempts."""
    connection_timeout: float = 10.0
    """Timeout in seconds for TCP connection establishment."""


class ByteBlasterClient:
    """High-level ByteBlaster client for EMWIN data reception and distribution.

    The ByteBlasterClient provides a comprehensive interface for connecting to
    ByteBlaster servers, managing authentication, decoding the Quick Block Transfer
    protocol, and distributing received data segments to registered handlers. The
    client implements automatic reconnection, server failover, connection health
    monitoring, and graceful error recovery.

    The client manages the complete lifecycle of ByteBlaster connections including:
    - Automatic server discovery and rotation from a managed server list
    - Authentication using the ByteBlaster authentication protocol
    - Real-time protocol decoding of incoming EMWIN data streams
    - Health monitoring with configurable timeouts and error thresholds
    - Event-driven data distribution to subscribed handlers
    - Persistent server list management with automatic updates
    - Graceful shutdown and cleanup of all resources

    The client operates asynchronously and can handle multiple concurrent operations
    while maintaining a single active connection to the most responsive available
    server. It provides both synchronous and asynchronous interfaces for maximum
    integration flexibility.
    """

    def __init__(
        self,
        options: ByteBlasterClientOptions,
    ) -> None:
        """Initialize the ByteBlaster client with comprehensive configuration.

        Creates and configures all necessary components for ByteBlaster connectivity
        including server management, authentication handling, protocol decoding,
        connection monitoring, and event distribution. The client starts in an
        inactive state and must be explicitly started to begin operations.

        The initialization process sets up internal state management, configures
        all subsystems with the provided options, and prepares event handling
        infrastructure for data distribution.

        Args:
            options: Complete configuration object containing all operational
                    parameters including authentication credentials, timeouts,
                    file paths, and behavioral settings.

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
        """Register a handler function to receive EMWIN data segments.

        Adds a handler function to the client's notification system that will be
        called whenever complete data segments are received and decoded from the
        ByteBlaster stream. Handlers can be either synchronous or asynchronous
        functions and will be invoked in the order they were registered.

        The client maintains a list of active handlers and ensures each handler
        is called exactly once per received segment. Handler errors are isolated
        and logged but do not affect other handlers or the connection stability.

        Args:
            handler: Callable function that accepts a QBTSegment parameter.
                    Can be either a synchronous function or an async coroutine.
                    Duplicate handlers are automatically prevented.

        """
        if handler not in self._segment_handlers:
            self._segment_handlers.append(handler)
            logger.debug("Added segment handler: %s", handler)

    def unsubscribe(self, handler: SegmentHandler | AsyncSegmentHandler) -> None:
        """Remove a previously registered handler from the notification system.

        Removes the specified handler function from the client's event notification
        system, ensuring it will no longer receive data segment notifications. The
        method safely handles attempts to remove non-existent handlers without
        raising errors.

        Args:
            handler: The exact handler function reference that was previously
                    registered using the subscribe method. Must match the original
                    function object reference for successful removal.

        """
        if handler in self._segment_handlers:
            self._segment_handlers.remove(handler)
            logger.debug("Removed segment handler: %s", handler)

    def stream_segments(self, max_queue_size: int = 1000) -> SegmentStream:
        """Create an async iterator for streaming segments.

        This method returns a SegmentStream that implements the async iterator protocol,
        allowing you to use 'async with' and 'async for' patterns for reactive segment
        processing. The stream provides natural backpressure handling and structured
        concurrency support.

        Example usage:
            async with client.stream_segments() as segments:
                async for segment in segments:
                    await process_segment(segment)

        Args:
            max_queue_size: Maximum number of segments to buffer before dropping
                          new segments (default: 1000)

        Returns:
            SegmentStream that can be used as an async context manager and iterator

        """
        return SegmentStream(self, max_queue_size)

    async def start(self) -> None:
        """Start the ByteBlaster client and begin connection operations.

        Initiates the client's main operation cycle including connection establishment,
        server management, and data reception. The client transitions from inactive
        to active state and begins attempting connections to available ByteBlaster
        servers with automatic failover and reconnection logic.

        The start process creates the main connection loop as an async task that
        will continue running until the client is explicitly stopped. The method
        is idempotent and will log a warning if called on an already running client.
        """
        if self._running:
            logger.warning("Client already running")
            return

        self._running = True
        logger.info("Starting ByteBlaster client")

        # Start connection loop
        self._reconnect_task = asyncio.create_task(self._connection_loop())

    async def stop(self, shutdown_timeout: float | None = None) -> None:
        """Stop the ByteBlaster client and perform graceful shutdown.

        Terminates all client operations including the connection loop, active
        connections, monitoring systems, and background tasks. The shutdown process
        ensures all resources are properly cleaned up and no background tasks
        remain running after completion.

        The method handles cancellation of the reconnection task, closure of active
        connections, and cleanup of all subsystems with configurable timeout
        constraints to prevent indefinite blocking during shutdown.

        Args:
            shutdown_timeout: Maximum time in seconds to wait for graceful shutdown of
                    background tasks. If None, waits indefinitely for clean
                    termination of all operations.

        """
        if not self._running:
            return

        logger.info("Stopping ByteBlaster client")
        self._running = False

        # Cancel reconnection task with structured cancellation
        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()
            try:
                if shutdown_timeout:
                    await asyncio.wait_for(self._reconnect_task, timeout=shutdown_timeout)
                else:
                    await self._reconnect_task
            except (TimeoutError, asyncio.CancelledError):
                logger.debug("Reconnection task cancelled during shutdown")

        # Close current connection
        await self._close_connection()
        logger.info("ByteBlaster client stopped")

    @property
    def is_connected(self) -> bool:
        """Check if the client has an active connection to a ByteBlaster server.

        Returns:
            True if the client is currently connected to a server and ready to
            receive data, False if disconnected or in a connecting state.

        """
        return self._connected and self._protocol is not None

    @property
    def is_running(self) -> bool:
        """Check if the client's main operation loop is active.

        Returns:
            True if the client has been started and is actively managing
            connections, False if stopped or not yet started.

        """
        return self._running

    @property
    def server_count(self) -> int:
        """Get the total number of available ByteBlaster servers.

        Returns:
            The count of servers currently known to the server manager,
            including both active and inactive servers from the server list.

        """
        return len(self._server_manager)

    @property
    def email(self) -> str:
        """Get the email address used for ByteBlaster server authentication.

        Returns:
            The email address string configured during client initialization
            and used for server authentication and user identification.

        """
        return self._email

    def get_server_list(self) -> Any:
        """Retrieve the current list of known ByteBlaster servers.

        Returns:
            The complete server list as maintained by the server manager,
            including server hostnames, ports, and metadata. The format
            matches the server list structure used for persistence.

        """
        return self._server_manager.get_current_server_list()

    async def _connection_loop(self) -> None:
        """Execute the main connection management loop with automatic failover.

        Manages the complete connection lifecycle including server selection,
        connection attempts, failure handling, and reconnection logic. The loop
        implements intelligent failover strategies with exponential backoff for
        repeated failures and automatic server rotation to find responsive hosts.

        The connection loop maintains connection stability by tracking consecutive
        failures, implementing progressive delays, and resetting server selection
        after extended failure periods. It ensures the client remains operational
        even when individual servers become unavailable.

        Raises:
            asyncio.CancelledError: When the connection loop is cancelled during
                                   normal shutdown procedures.

        """
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
        """Establish a TCP connection to a specific ByteBlaster server.

        Creates a new asyncio connection to the specified server using the
        configured connection timeout. The method initializes the protocol
        handler, establishes the transport layer, and updates the client's
        connection state upon successful connection.

        The connection process includes transport validation and comprehensive
        error handling for common connection failure scenarios including
        timeouts, connection refusal, and network errors.

        Args:
            host: Hostname or IP address of the ByteBlaster server to connect to.
            port: TCP port number for the ByteBlaster service on the target server.

        Raises:
            TimeoutError: If the connection attempt exceeds the configured timeout.
            ConnectionRefusedError: If the server refuses the connection.
            OSError: For other network-related connection failures.

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
        """Close the current connection and clean up all associated resources.

        Performs comprehensive cleanup of the active connection including stopping
        the watchdog monitor, terminating authentication processes, and closing
        the network transport. The method ensures all subsystems are properly
        shut down and no resources remain allocated after disconnection using
        structured concurrency.

        The cleanup process handles each subsystem concurrently but safely to
        ensure all resources are freed even if individual cleanup operations fail.
        """
        self._connected = False

        # Stop subsystems concurrently using TaskGroup with individual error handling
        async def safe_stop_watchdog() -> None:
            try:
                await self._watchdog.stop()
            except Exception:
                logger.exception("Error stopping watchdog during connection cleanup")

        async def safe_stop_auth() -> None:
            try:
                await self._auth_handler.stop_authentication()
            except Exception:
                logger.exception("Error stopping authentication during connection cleanup")

        # Stop both subsystems concurrently
        async with asyncio.TaskGroup() as tg:
            tg.create_task(safe_stop_watchdog())
            tg.create_task(safe_stop_auth())

        # Close transport (synchronous operation)
        if self._protocol and self._protocol.is_connected:
            transport = getattr(self._protocol, "_transport", None)
            if transport:
                transport.close()

        self._protocol = None
        logger.debug("Connection closed")

    async def on_connection_made(self) -> None:
        """Initialize all connection-dependent subsystems after successful connection.

        Called by the protocol handler when a TCP connection is successfully
        established with a ByteBlaster server. This method coordinates the
        startup of authentication, monitoring, and other connection-dependent
        services required for normal operation using asyncio.TaskGroup for
        structured concurrency.

        The initialization process includes starting the authentication handshake
        with the server and activating the connection health monitoring system.
        All subsystems are started concurrently for faster connection setup.
        """
        if not self._protocol:
            return

        # Start authentication and watchdog concurrently using TaskGroup
        async with asyncio.TaskGroup() as tg:
            tg.create_task(self._auth_handler.start_authentication(self._protocol))
            tg.create_task(self._watchdog.start(self._close_connection))

        logger.info("Connection established and authenticated")

    async def on_connection_lost(self, _exc: Exception | None) -> None:
        """Handle connection termination and trigger reconnection procedures.

        Called by the protocol handler when the connection to a ByteBlaster server
        is lost due to network issues, server shutdown, or other connectivity
        problems. This method updates connection state, performs cleanup, and
        signals the connection loop to attempt reconnection.

        Args:
            _exc: Optional exception that caused the connection loss. Currently
                 not used but maintained for protocol compatibility.

        """
        self._connected = False
        await self._close_connection()
        self._connection_lost_event.set()

    def on_protocol_error(self, _exc: Exception) -> None:
        """Handle protocol processing errors and update health monitoring.

        Called when exceptions occur during protocol decoding, data processing,
        or other protocol-related operations. This method updates the watchdog
        error counter and resets the protocol decoder to prevent cascading
        failures from malformed data.

        Args:
            _exc: The exception that occurred during protocol processing.
                 Currently used for logging purposes and health tracking.

        """
        self._watchdog.on_exception()
        self._decoder.reset()

    def set_remote_address(self, address: str) -> None:
        """Update the protocol decoder with the current server connection address.

        Provides the decoder with connection context including the remote server
        address for logging, debugging, and protocol state management purposes.

        Args:
            address: String representation of the remote server address in
                    'host:port' format for identification and logging.

        """
        self._decoder.set_remote_address(address)

    @property
    def decoder(self) -> ProtocolDecoder:
        """Access the protocol decoder instance for direct interaction.

        Returns:
            The ProtocolDecoder instance used for parsing ByteBlaster protocol
            frames and managing decoder state.

        """
        return self._decoder

    @property
    def decoder_state(self) -> DecoderState:
        """Access the current state of the protocol decoder.

        Returns:
            The current DecoderState indicating the decoder's position in
            the protocol parsing state machine and buffer status.

        """
        return self._decoder.state

    def on_frame_received(self, frame: ProtocolFrame) -> None:
        """Process successfully decoded protocol frames from the ByteBlaster stream.

        Called by the protocol decoder when complete frames are successfully
        parsed from the incoming data stream. This method dispatches different
        frame types to appropriate handlers including data segments for content
        distribution and server list updates for connection management.

        The method updates watchdog timing, creates async tasks for data processing,
        and ensures all frame types are handled according to their specific
        processing requirements.

        Args:
            frame: Successfully decoded protocol frame containing either data
                  segments, server list updates, or other protocol messages.

        """
        self._watchdog.on_data_received()

        if isinstance(frame, DataBlockFrame) and frame.segment:
            # Create task for data segment handling to avoid blocking protocol processing
            self._data_task = asyncio.create_task(self._handle_data_segment(frame.segment))

        elif isinstance(frame, ServerListFrame) and frame.server_list:
            self._handle_server_list_update(frame.server_list)

    async def _handle_data_segment(self, segment: QBTSegment) -> None:
        """Process and distribute received EMWIN data segments to registered handlers.

        Manages the distribution of successfully received and decoded data segments
        to all registered handler functions. The method handles both synchronous
        and asynchronous handlers concurrently using asyncio.TaskGroup for better
        performance and structured concurrency.

        Handler errors are caught and logged but do not affect the processing of
        other handlers or the stability of the connection. This ensures that
        problematic handlers cannot disrupt the overall data flow.

        Args:
            segment: Complete QBTSegment containing EMWIN data that has been
                    successfully received and decoded from the ByteBlaster stream.

        """
        logger.debug("Received segment: %s", segment)

        if not self._segment_handlers:
            return

        # Process async and sync handlers separately for optimal performance
        handlers_copy = self._segment_handlers.copy()
        async_handlers = [h for h in handlers_copy if asyncio.iscoroutinefunction(h)]
        sync_handlers = [h for h in handlers_copy if not asyncio.iscoroutinefunction(h)]

        # Execute async handlers concurrently using TaskGroup
        if async_handlers:
            async with asyncio.TaskGroup() as tg:
                for handler in async_handlers:
                    tg.create_task(self._safe_async_handler_call(handler, segment))

        # Execute sync handlers sequentially to avoid blocking the event loop
        for handler in sync_handlers:
            try:
                handler(segment)
            except Exception:
                logger.exception("Sync segment handler error")

    async def _safe_async_handler_call(
        self,
        handler: AsyncSegmentHandler,
        segment: QBTSegment,
    ) -> None:
        """Safely call an async segment handler with error isolation."""
        try:
            await handler(segment)
        except Exception:
            logger.exception("Async segment handler error")

    def _handle_server_list_update(self, server_list: Any) -> None:
        """Process server list updates received from ByteBlaster servers.

        Handles server list update frames that contain current information about
        available ByteBlaster servers. The method updates the client's server
        manager with the new server information and persists the updated list
        for future connection attempts.

        Server list updates allow the client to automatically discover new servers
        and update connection priorities based on current server availability
        and performance characteristics.

        Args:
            server_list: Updated server list data structure containing hostnames,
                        ports, and server metadata in the ByteBlaster format.

        """
        logger.info("Received server list update")
        self._server_manager.save_server_list(server_list)

    def __repr__(self) -> str:
        """Return a detailed string representation of the client's current state.

        Provides a comprehensive view of the client's operational status including
        authentication information, runtime state, connection status, and server
        availability for debugging and monitoring purposes.

        Returns:
            Formatted string containing key client state information including
            email, running status, connection status, and server count.

        """
        return (
            f"ByteBlasterClient("
            f"email='{self._email}', "
            f"running={self._running}, "
            f"connected={self._connected}, "
            f"servers={len(self._server_manager)})"
        )
