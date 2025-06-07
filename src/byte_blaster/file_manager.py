"""High-level file manager for ByteBlaster client."""

import asyncio
import logging
from collections import deque
from typing import Callable, Coroutine, NamedTuple, Any

from byte_blaster.client import ByteBlasterClient, ByteBlasterClientOptions
from byte_blaster.protocol import QBTSegment

logger = logging.getLogger(__name__)


class CompletedFile(NamedTuple):
    """Represents a fully reconstructed file."""

    filename: str
    data: bytes


FileCompletionCallback = Callable[[CompletedFile], Coroutine[Any, Any, None]]


class FileAssembler:
    """Assembles file segments into complete files."""

    def __init__(
        self, on_file_completed: FileCompletionCallback, duplicate_cache_size: int = 100
    ) -> None:
        """Initialize the FileAssembler.

        Args:
            on_file_completed: Async callback to be invoked with completed files.
            duplicate_cache_size: The number of completed file keys to cache to prevent
                processing duplicates from server-side retransmissions.

        """
        self.on_file_completed = on_file_completed
        self.file_segments: dict[str, list[QBTSegment]] = {}
        self._recently_completed: deque[str] = deque(maxlen=duplicate_cache_size)

    async def handle_segment(self, segment: QBTSegment) -> None:
        """Process an incoming data segment.

        This method is intended to be subscribed to a `ByteBlasterClient`.

        Args:
            segment: The received segment.
        """
        file_key = segment.key

        # Check if this is a duplicate of a recently completed file
        if file_key in self._recently_completed:
            logger.debug("Skipping segment for duplicate file: %s", file_key)
            return

        # Skip FILLFILE.TXT - it's filler data when no real data is being transmitted
        if segment.filename == "FILLFILE.TXT":
            return

        # Group segments by file key
        if file_key not in self.file_segments:
            self.file_segments[file_key] = []

        self.file_segments[file_key].append(segment)

        # Check if we have all segments for this file
        segments = self.file_segments[file_key]
        if len(segments) == segment.total_blocks:
            await self._reconstruct_and_notify(file_key, segments)

    async def _reconstruct_and_notify(
        self, file_key: str, segments: list[QBTSegment]
    ) -> None:
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
        except Exception as e:
            logger.error(f"Error reconstructing file {file_key}: {e}", exc_info=True)
        finally:
            # Clean up segments from memory
            if file_key in self.file_segments:
                del self.file_segments[file_key]


class ByteBlasterFileManager:
    """
    A high-level manager for the ByteBlaster client that abstracts away
    segment and block handling, providing a simple interface for receiving
    completed files.
    """

    def __init__(
        self,
        options: ByteBlasterClientOptions,
    ) -> None:
        """Initialize the ByteBlasterFileManager.

        Args:
            options: Configuration options for the underlying client.
        """
        self._client = ByteBlasterClient(options)
        self._assembler = FileAssembler(self._dispatch_file)
        self._client.subscribe(self._assembler.handle_segment)
        self._file_handlers: list[FileCompletionCallback] = []

    @property
    def client(self) -> ByteBlasterClient:
        """The underlying ByteBlasterClient instance."""
        return self._client

    @property
    def assembler(self) -> FileAssembler:
        """The FileAssembler instance."""
        return self._assembler

    def subscribe(self, handler: FileCompletionCallback) -> None:
        """Subscribe to completed file events.
        Args:
            handler: Async function to call when files are completed.
        """
        if handler not in self._file_handlers:
            self._file_handlers.append(handler)

    def unsubscribe(self, handler: FileCompletionCallback) -> None:
        """Unsubscribe from completed file events.
        Args:
            handler: The handler function to remove.
        """
        try:
            self._file_handlers.remove(handler)
        except ValueError:
            logger.warning("Handler not found in subscribers list.")

    async def _dispatch_file(self, file: CompletedFile) -> None:
        """Dispatch a completed file to all subscribed handlers."""
        logger.debug(f"Dispatching completed file: {file.filename}")
        tasks = [handler(file) for handler in self._file_handlers]
        await asyncio.gather(*tasks)

    async def start(self) -> None:
        """Start the client and begin receiving data."""
        await self._client.start()

    async def stop(self, timeout: float | None = None) -> None:
        """Stop the client gracefully.

        Args:
            timeout: Optional timeout in seconds to wait for shutdown.
        """
        await self._client.stop(timeout=timeout)
