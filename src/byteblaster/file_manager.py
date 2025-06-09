"""High-level file manager for ByteBlaster client.

This module provides abstractions for managing file reconstruction from ByteBlaster
protocol segments. It handles the complex process of receiving, assembling, and
delivering complete files from fragmented data streams, with built-in duplicate
detection and error handling capabilities.
"""

import asyncio
import contextlib
import logging
import types
from collections import deque
from collections.abc import AsyncIterator, Callable, Coroutine
from typing import Any, NamedTuple

from byteblaster.client import ByteBlasterClient, ByteBlasterClientOptions
from byteblaster.protocol import QBTSegment

logger = logging.getLogger(__name__)


class CompletedFile(NamedTuple):
    """Represents a fully reconstructed file from assembled segments.

    This immutable data structure contains the complete file data that has been
    successfully reconstructed from all received segments. It serves as the final
    output of the file assembly process and is passed to registered handlers for
    processing or storage.

    Attributes:
        filename: The original filename as transmitted in the protocol segments.
        data: The complete binary file content assembled from all segments.

    """

    filename: str
    data: bytes


FileCompletionCallback = Callable[[CompletedFile], Coroutine[Any, Any, None]]


class FileStream:
    """Async iterator for streaming completed files with backpressure support.

    This class provides an async iterator interface for receiving completed files,
    offering structured concurrency and natural backpressure handling. It can be
    used with 'async with' and 'async for' patterns for reactive file processing.

    The stream automatically subscribes to file completion events when entering the
    context and unsubscribes when exiting, ensuring proper resource cleanup. If the
    internal queue becomes full, new files are dropped with logging to prevent
    memory issues.
    """

    def __init__(self, file_manager: "ByteBlasterFileManager", max_queue_size: int = 100) -> None:
        """Initialize file stream with manager and queue configuration.

        Args:
            file_manager: ByteBlasterFileManager instance to stream files from
            max_queue_size: Maximum number of files to buffer (default: 100)

        """
        self._file_manager = file_manager
        self._queue: asyncio.Queue[CompletedFile | None] = asyncio.Queue(maxsize=max_queue_size)
        self._closed = False

    async def __aenter__(self) -> "FileStream":
        """Start streaming when entering context."""
        self._file_manager.subscribe(self._enqueue_file)
        logger.debug("Started file stream")
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None:
        """Clean up when exiting context."""
        self._closed = True
        self._file_manager.unsubscribe(self._enqueue_file)

        # Signal end of stream
        with contextlib.suppress(asyncio.QueueFull):
            self._queue.put_nowait(None)

        logger.debug("Stopped file stream")

    def __aiter__(self) -> AsyncIterator[CompletedFile]:
        """Return self as async iterator."""
        return self

    async def __anext__(self) -> CompletedFile:
        """Get next completed file from stream."""
        while True:
            item = await self._queue.get()
            if item is None or self._closed:
                raise StopAsyncIteration
            return item

    async def _enqueue_file(self, file: CompletedFile) -> None:
        """Queue file for async iteration with backpressure."""
        if self._closed:
            return

        try:
            # Use put_nowait to avoid blocking the event loop
            # If queue is full, we drop the file and log a warning
            self._queue.put_nowait(file)
        except asyncio.QueueFull:
            logger.warning(
                "File stream queue full, dropping file: %s (%d bytes)",
                file.filename,
                len(file.data),
            )


class FileAssembler:
    """Assembles file segments into complete files with duplicate detection and error handling.

    This class manages the complex process of receiving individual QBT protocol segments
    and reconstructing them into complete files. It handles segment ordering, duplicate
    detection, and maintains a cache of recently completed files to prevent processing
    redundant transmissions. The assembler automatically triggers completion callbacks
    when all segments for a file have been received and successfully reconstructed.

    The assembler filters out filler data (FILLFILE.TXT) and provides robust error
    handling to ensure system stability even when individual file reconstruction fails.
    """

    def __init__(
        self, on_file_completed: FileCompletionCallback, duplicate_cache_size: int = 100
    ) -> None:
        """Initialize the FileAssembler with completion callback and duplicate detection.

        Sets up the internal data structures for segment management and configures
        the duplicate detection cache. The assembler maintains a bounded cache of
        recently completed file keys to efficiently detect and skip duplicate
        transmissions that may occur due to server-side retransmissions or network
        reliability mechanisms.

        The completion callback is invoked asynchronously when files are fully
        reconstructed, allowing for non-blocking file processing workflows.

        Args:
            on_file_completed: Async callback function that receives CompletedFile
                objects when reconstruction is successful. This callback should
                handle file processing, storage, or forwarding operations.
            duplicate_cache_size: Maximum number of completed file keys to retain
                in the duplicate detection cache. Larger values provide better
                duplicate detection at the cost of memory usage. Default is 100.

        """
        self.on_file_completed = on_file_completed
        self.file_segments: dict[str, list[QBTSegment]] = {}
        self._recently_completed: deque[str] = deque(maxlen=duplicate_cache_size)

    async def handle_segment(self, segment: QBTSegment) -> None:
        """Process an incoming data segment and attempt file reconstruction.

        This method serves as the primary entry point for segment processing and is
        designed to be subscribed to ByteBlasterClient segment events. It performs
        comprehensive filtering, duplicate detection, and segment aggregation before
        attempting file reconstruction.

        The processing workflow includes:
        1. Duplicate file detection using the completion cache
        2. Filtering of filler data (FILLFILE.TXT segments)
        3. Duplicate segment detection within the same file
        4. Segment aggregation and completeness checking
        5. Automatic file reconstruction when all segments are received

        Error handling is implemented at multiple levels to ensure system stability,
        with detailed logging for debugging and monitoring purposes.

        Args:
            segment: The QBTSegment containing file data, metadata, and block
                information received from the ByteBlaster protocol stream.

        """
        file_key = segment.key

        # Check if this is a duplicate of a recently completed file
        if file_key in self._recently_completed:
            logger.info("Skipping segment for duplicate file: %s", file_key)
            return

        # Skip FILLFILE.TXT - it's filler data when no real data is being transmitted
        if segment.filename == "FILLFILE.TXT":
            return

        # Group segments by file key
        if file_key not in self.file_segments:
            self.file_segments[file_key] = []

        # Check for duplicate segments before appending
        if any(s.block_number == segment.block_number for s in self.file_segments[file_key]):
            logger.debug("Skipping duplicate segment: %s, block %s", file_key, segment.block_number)
            return

        self.file_segments[file_key].append(segment)

        # Check if we have all segments for this file
        segments = self.file_segments[file_key]
        if len(segments) == segment.total_blocks:
            await self._reconstruct_and_notify(file_key, segments)

    async def _reconstruct_and_notify(self, file_key: str, segments: list[QBTSegment]) -> None:
        """Reconstruct a file from its segments and notify the consumer."""
        try:
            # Sort segments by block number
            segments.sort(key=lambda s: s.block_number)

            # Combine content
            complete_data = b"".join(segment.content for segment in segments)

            # Get filename from first segment
            filename = segments[0].filename

            # Create completed file object
            completed_file = CompletedFile(filename=filename, data=complete_data)

            # Notify consumer
            await self.on_file_completed(completed_file)

            # Add to cache to prevent processing duplicates
            self._recently_completed.append(file_key)
            logger.debug("Added file key to duplicate cache: %s", file_key)
        except Exception:
            logger.exception("Error reconstructing file %s", file_key)
        finally:
            # Clean up segments from memory
            if file_key in self.file_segments:
                del self.file_segments[file_key]


class ByteBlasterFileManager:
    """High-level manager that provides a simplified interface for ByteBlaster file operations.

    This class serves as the primary integration point for applications that need to
    receive complete files from ByteBlaster protocol streams without managing the
    complexity of segment handling, block assembly, or protocol details. It orchestrates
    the interaction between the low-level ByteBlasterClient and the FileAssembler to
    provide a clean, event-driven file completion interface.

    The manager supports multiple file completion handlers, allowing different parts
    of an application to process completed files independently. It handles the complete
    lifecycle from client initialization through graceful shutdown, with comprehensive
    error handling and logging throughout the process.

    Key capabilities include:
    - Automatic segment assembly and file reconstruction
    - Multiple subscriber support for file completion events
    - Graceful startup and shutdown with configurable timeouts
    - Built-in duplicate detection and error recovery
    - Direct access to underlying client and assembler components when needed
    """

    def __init__(
        self,
        options: ByteBlasterClientOptions,
    ) -> None:
        """Initialize the ByteBlasterFileManager with client configuration.

        Sets up the complete file management pipeline by instantiating and configuring
        the underlying ByteBlasterClient and FileAssembler components. The initialization
        process establishes the event subscription chain from client segments to file
        completion handlers, creating a seamless data flow for file reconstruction.

        The manager automatically wires together the client and assembler, subscribing
        the assembler's segment handler to the client's segment events. This creates
        an end-to-end pipeline that transforms raw protocol segments into complete
        files without requiring manual event handling.

        Args:
            options: Configuration object containing connection parameters, protocol
                settings, and other client-specific options required for ByteBlaster
                protocol communication.

        """
        self._client = ByteBlasterClient(options)
        self._assembler = FileAssembler(self._dispatch_file)
        self._client.subscribe(self._assembler.handle_segment)
        self._file_handlers: list[FileCompletionCallback] = []

    @property
    def client(self) -> ByteBlasterClient:
        """Access to the underlying ByteBlasterClient instance for advanced operations.

        Provides direct access to the low-level client when applications need to
        perform operations beyond standard file management, such as accessing
        protocol statistics, configuring advanced client options, or implementing
        custom segment filtering logic.
        """
        return self._client

    @property
    def assembler(self) -> FileAssembler:
        """Access to the FileAssembler instance for monitoring and diagnostics.

        Provides direct access to the file assembly component for applications
        that need to inspect assembly state, access segment statistics, or
        implement custom duplicate detection strategies beyond the default
        cache-based approach.
        """
        return self._assembler

    def subscribe(self, handler: FileCompletionCallback) -> None:
        """Subscribe a handler to receive completed file events.

        Registers an asynchronous callback function that will be invoked whenever
        a file is successfully reconstructed from protocol segments. Multiple
        handlers can be registered, and each will receive all completed files
        independently. Handlers are executed concurrently using asyncio.gather
        to maximize throughput and prevent blocking.

        The subscription system supports idempotent registration - attempting
        to subscribe the same handler multiple times will not create duplicate
        subscriptions.

        All registered handlers are executed concurrently using asyncio.TaskGroup
        for better performance and structured concurrency. Handler errors are
        isolated and logged but do not affect other handlers.

        Args:
            handler: Async callback function that accepts a CompletedFile object
                and performs application-specific processing such as file storage,
                validation, or forwarding to other systems.

        """
        if handler not in self._file_handlers:
            self._file_handlers.append(handler)

    def unsubscribe(self, handler: FileCompletionCallback) -> None:
        """Remove a handler from the completed file event subscription list.

        Safely removes a previously registered file completion handler from the
        subscription list. If the handler was not previously subscribed, the
        operation completes without error but logs a warning for debugging
        purposes.

        This method enables dynamic subscription management, allowing applications
        to add and remove file processors based on runtime conditions or
        configuration changes.

        Args:
            handler: The exact handler function reference that was previously
                registered via subscribe(). Function identity is used for
                matching, so lambda functions and bound methods must maintain
                the same object reference.

        """
        try:
            self._file_handlers.remove(handler)
        except ValueError:
            logger.warning("Handler not found in subscribers list.")

    def stream_files(self, max_queue_size: int = 100) -> FileStream:
        """Create an async iterator for streaming completed files.

        This method returns a FileStream that implements the async iterator protocol,
        allowing you to use 'async with' and 'async for' patterns for reactive file
        processing. The stream provides natural backpressure handling and structured
        concurrency support.

        Example usage:
            async with file_manager.stream_files() as files:
                async for completed_file in files:
                    await process_file(completed_file)

        Args:
            max_queue_size: Maximum number of files to buffer before dropping
                          new files (default: 100)

        Returns:
            FileStream that can be used as an async context manager and iterator

        """
        return FileStream(self, max_queue_size)

    async def _dispatch_file(self, file: CompletedFile) -> None:
        """Dispatch a completed file to all subscribed handlers using TaskGroup.

        Uses asyncio.TaskGroup for better error handling and structured concurrency.
        If any handler fails, the error is logged but other handlers continue processing.
        """
        logger.debug("Dispatching completed file: %s", file.filename)

        if not self._file_handlers:
            return

        async with asyncio.TaskGroup() as tg:
            for handler in self._file_handlers:
                tg.create_task(self._safe_handler_call(handler, file))

    async def _safe_handler_call(
        self, handler: FileCompletionCallback, file: CompletedFile
    ) -> None:
        """Safely call a file completion handler with error isolation."""
        try:
            await handler(file)
        except Exception:
            logger.exception("File completion handler error for file: %s", file.filename)

    async def start(self) -> None:
        """Start the ByteBlaster client and begin receiving data streams.

        Initiates the underlying ByteBlasterClient connection and begins the
        process of receiving protocol segments. Once started, the complete
        file management pipeline becomes active and will automatically process
        incoming segments, reconstruct files, and notify registered handlers
        of completed files.

        This method must be called before any file reception can occur. The
        startup process includes protocol handshaking, connection establishment,
        and activation of the segment processing pipeline.

        Raises:
            ConnectionError: If the client cannot establish a connection to
                the ByteBlaster source.
            ValueError: If the client configuration is invalid or incomplete.

        """
        await self._client.start()

    async def stop(self, shutdown_timeout: float | None = None) -> None:
        """Stop the client gracefully with optional timeout control.

        Initiates a controlled shutdown of the ByteBlaster client and file
        management pipeline. The shutdown process ensures that any files
        currently being assembled are completed where possible, pending
        file completion notifications are delivered, and all resources
        are properly cleaned up.

        The method provides timeout control to prevent indefinite blocking
        during shutdown, which is particularly important in service environments
        where graceful shutdown windows are time-bounded.

        Args:
            shutdown_timeout: Maximum time in seconds to wait for graceful shutdown
                completion. If None, the shutdown will wait indefinitely
                for all operations to complete. If the timeout expires,
                the shutdown will proceed forcefully.

        Raises:
            asyncio.TimeoutError: If the graceful shutdown cannot complete
                within the specified timeout period.

        """
        await self._client.stop(shutdown_timeout=shutdown_timeout)
