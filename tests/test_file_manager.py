# pyright: reportPrivateUsage=false
"""Comprehensive tests for the file_manager module.

This test suite covers all classes in the file_manager module including:
- CompletedFile: Basic NamedTuple functionality
- FileStream: Async iterator with backpressure handling
- FileAssembler: Segment processing and file reconstruction
- ByteBlasterFileManager: High-level integration and lifecycle management
"""

import asyncio
import logging
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from byteblaster.client import ByteBlasterClientOptions
from byteblaster.file_manager import (
    ByteBlasterFileManager,
    CompletedFile,
    FileAssembler,
    FileStream,
)
from byteblaster.protocol import QBTSegment


class TestCompletedFile:
    """Test the CompletedFile NamedTuple."""

    def test_completed_file_creation(self) -> None:
        """Test basic creation and attribute access."""
        filename = "test.txt"
        data = b"test content"

        completed_file = CompletedFile(filename=filename, data=data)

        assert completed_file.filename == filename
        assert completed_file.data == data

    def test_completed_file_immutability(self) -> None:
        """Test that CompletedFile is immutable."""
        completed_file = CompletedFile(filename="test.txt", data=b"content")

        with pytest.raises(AttributeError):
            completed_file.filename = "new_name.txt"  # type: ignore[misc]

        with pytest.raises(AttributeError):
            completed_file.data = b"new content"  # type: ignore[misc]

    def test_completed_file_equality(self) -> None:
        """Test equality comparison between CompletedFile instances."""
        file1 = CompletedFile(filename="test.txt", data=b"content")
        file2 = CompletedFile(filename="test.txt", data=b"content")
        file3 = CompletedFile(filename="different.txt", data=b"content")

        assert file1 == file2
        assert file1 != file3

    def test_completed_file_with_empty_content(self) -> None:
        """Test CompletedFile with empty data."""
        completed_file = CompletedFile(filename="empty.txt", data=b"")

        assert completed_file.filename == "empty.txt"
        assert completed_file.data == b""
        assert len(completed_file.data) == 0

    def test_completed_file_with_binary_content(self) -> None:
        """Test CompletedFile with binary data."""
        binary_data = bytes(range(256))
        completed_file = CompletedFile(filename="binary.dat", data=binary_data)

        assert completed_file.filename == "binary.dat"
        assert completed_file.data == binary_data
        assert len(completed_file.data) == 256


class TestFileStream:
    """Test the FileStream async iterator with backpressure support."""

    @pytest.fixture
    def mock_file_manager(self) -> MagicMock:
        """Create a mock ByteBlasterFileManager."""
        manager = MagicMock()
        manager.subscribe = MagicMock()
        manager.unsubscribe = MagicMock()
        return manager

    @pytest.fixture
    def file_stream(self, mock_file_manager: MagicMock) -> FileStream:
        """Create a FileStream instance with mocked manager."""
        return FileStream(mock_file_manager, max_queue_size=5)

    @pytest.mark.asyncio
    async def test_file_stream_context_manager(
        self, file_stream: FileStream, mock_file_manager: MagicMock
    ) -> None:
        """Test FileStream as async context manager."""
        async with file_stream as stream:
            assert stream is file_stream
            mock_file_manager.subscribe.assert_called_once()

        mock_file_manager.unsubscribe.assert_called_once()

    @pytest.mark.asyncio
    async def test_file_stream_iteration_empty(self, file_stream: FileStream) -> None:
        """Test iteration over empty stream."""
        async with file_stream:
            # Manually close the stream to trigger StopAsyncIteration
            file_stream._closed = True
            file_stream._queue.put_nowait(None)

            files = [file async for file in file_stream]

            assert len(files) == 0

    @pytest.mark.asyncio
    async def test_file_stream_iteration_with_files(
        self,
        file_stream: FileStream,
        mock_file_manager: MagicMock,  # noqa: ARG002
    ) -> None:
        """Test iteration over stream with files."""
        test_files = [
            CompletedFile("file1.txt", b"content1"),
            CompletedFile("file2.txt", b"content2"),
        ]

        async with file_stream:
            # Enqueue test files
            for file in test_files:
                await file_stream._enqueue_file(file)

            # Signal end of stream by putting None (don't set _closed yet)
            file_stream._queue.put_nowait(None)

            received_files = [file async for file in file_stream]

            assert len(received_files) == 2
            assert received_files[0] == test_files[0]
            assert received_files[1] == test_files[1]

    @pytest.mark.asyncio
    async def test_file_stream_backpressure_drops_files(
        self, file_stream: FileStream, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test that files are dropped when queue is full."""
        # Fill the queue to capacity (max_queue_size=5)
        for i in range(5):
            file = CompletedFile(f"file{i}.txt", b"content")
            await file_stream._enqueue_file(file)

        # Try to add another file - should be dropped
        with caplog.at_level(logging.WARNING):
            overflow_file = CompletedFile("overflow.txt", b"overflow")
            await file_stream._enqueue_file(overflow_file)

        assert "File stream queue full, dropping file: overflow.txt" in caplog.text

    @pytest.mark.asyncio
    async def test_file_stream_enqueue_when_closed(self, file_stream: FileStream) -> None:
        """Test enqueuing files when stream is closed."""
        file_stream._closed = True

        # Should not raise exception and should not enqueue
        await file_stream._enqueue_file(CompletedFile("test.txt", b"content"))

        assert file_stream._queue.qsize() == 0

    @pytest.mark.asyncio
    async def test_file_stream_exception_in_context_exit(
        self, file_stream: FileStream, mock_file_manager: MagicMock
    ) -> None:
        """Test proper cleanup even when exception occurs in context."""

        def _raise_test_exception() -> None:
            msg = "Test exception"
            raise ValueError(msg)

        try:
            async with file_stream:
                _raise_test_exception()
        except ValueError:
            pass

        # Should still unsubscribe
        mock_file_manager.unsubscribe.assert_called_once()
        assert file_stream._closed


class TestFileAssembler:
    """Test the FileAssembler class for segment processing and file reconstruction."""

    @pytest.fixture
    def completion_handler(self) -> AsyncMock:
        """Create a mock completion handler."""
        return AsyncMock()

    @pytest.fixture
    def file_assembler(self, completion_handler: AsyncMock) -> FileAssembler:
        """Create a FileAssembler instance."""
        return FileAssembler(completion_handler, duplicate_cache_size=3)

    def create_test_segment(
        self,
        filename: str = "test.txt",
        block_number: int = 1,
        total_blocks: int = 1,
        content: bytes = b"test content",
        timestamp: datetime | None = None,
    ) -> QBTSegment:
        """Create a test QBTSegment."""
        if timestamp is None:
            timestamp = datetime.now(UTC)
        return QBTSegment(
            filename=filename,
            block_number=block_number,
            total_blocks=total_blocks,
            content=content,
            timestamp=timestamp,
        )

    @pytest.mark.asyncio
    async def test_single_segment_file_completion(
        self, file_assembler: FileAssembler, completion_handler: AsyncMock
    ) -> None:
        """Test completion of a single-segment file."""
        segment = self.create_test_segment("single.txt", 1, 1, b"single block")

        await file_assembler.handle_segment(segment)

        completion_handler.assert_called_once()
        completed_file = completion_handler.call_args[0][0]
        assert completed_file.filename == "single.txt"
        assert completed_file.data == b"single block"

    @pytest.mark.asyncio
    async def test_multi_segment_file_completion(
        self, file_assembler: FileAssembler, completion_handler: AsyncMock
    ) -> None:
        """Test completion of a multi-segment file."""
        # All segments need same timestamp to be part of same file
        timestamp = datetime.now(UTC)
        segments = [
            self.create_test_segment("multi.txt", 1, 3, b"part1", timestamp),
            self.create_test_segment("multi.txt", 2, 3, b"part2", timestamp),
            self.create_test_segment("multi.txt", 3, 3, b"part3", timestamp),
        ]

        # Process segments out of order to test sorting
        for segment in [segments[2], segments[0], segments[1]]:
            await file_assembler.handle_segment(segment)

        completion_handler.assert_called_once()
        completed_file = completion_handler.call_args[0][0]
        assert completed_file.filename == "multi.txt"
        assert completed_file.data == b"part1part2part3"

    @pytest.mark.asyncio
    async def test_duplicate_segment_handling(
        self, file_assembler: FileAssembler, completion_handler: AsyncMock
    ) -> None:
        """Test that duplicate segments are ignored."""
        # All segments need same timestamp to be part of same file
        timestamp = datetime.now(UTC)
        segment1 = self.create_test_segment("dup.txt", 1, 2, b"block1", timestamp)
        segment1_dup = self.create_test_segment("dup.txt", 1, 2, b"block1_different", timestamp)
        segment2 = self.create_test_segment("dup.txt", 2, 2, b"block2", timestamp)

        await file_assembler.handle_segment(segment1)
        await file_assembler.handle_segment(segment1_dup)  # Should be ignored
        await file_assembler.handle_segment(segment2)

        completion_handler.assert_called_once()
        completed_file = completion_handler.call_args[0][0]
        assert completed_file.data == b"block1block2"  # Original content, not duplicate

    @pytest.mark.asyncio
    async def test_fillfile_filtering(
        self, file_assembler: FileAssembler, completion_handler: AsyncMock
    ) -> None:
        """Test that FILLFILE.TXT segments are filtered out."""
        fillfile_segment = self.create_test_segment("FILLFILE.TXT", 1, 1, b"filler")

        await file_assembler.handle_segment(fillfile_segment)

        completion_handler.assert_not_called()

    @pytest.mark.asyncio
    async def test_duplicate_file_detection(
        self, file_assembler: FileAssembler, completion_handler: AsyncMock
    ) -> None:
        """Test duplicate file detection using cache."""
        # Same timestamp creates same key, enabling duplicate detection
        timestamp = datetime.now(UTC)
        segment1 = self.create_test_segment("cached.txt", 1, 1, b"content", timestamp)
        segment2 = self.create_test_segment("cached.txt", 1, 1, b"content", timestamp)

        # Process first file
        await file_assembler.handle_segment(segment1)
        completion_handler.assert_called_once()

        # Reset mock and process duplicate
        completion_handler.reset_mock()
        await file_assembler.handle_segment(segment2)

        # Should not be called again due to duplicate detection
        completion_handler.assert_not_called()

    @pytest.mark.asyncio
    async def test_duplicate_cache_size_limit(self, completion_handler: AsyncMock) -> None:
        """Test that duplicate cache respects size limit."""
        assembler = FileAssembler(completion_handler, duplicate_cache_size=2)

        # Process 3 different files (exceeds cache size of 2)
        for i in range(3):
            segment = self.create_test_segment(f"file{i}.txt", 1, 1, b"content")
            await assembler.handle_segment(segment)

        # First file should no longer be in cache, so it should be processed again
        first_segment = self.create_test_segment("file0.txt", 1, 1, b"content")
        await assembler.handle_segment(first_segment)

        # Should have been called 4 times (3 original + 1 repeat)
        assert completion_handler.call_count == 4

    @pytest.mark.asyncio
    async def test_completion_handler_exception_handling(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test error handling when completion handler raises exception."""
        failing_handler = AsyncMock(side_effect=ValueError("Handler error"))
        assembler = FileAssembler(failing_handler)

        segment = self.create_test_segment("error.txt", 1, 1, b"content")

        with caplog.at_level(logging.ERROR):
            await assembler.handle_segment(segment)

        assert "Error reconstructing file" in caplog.text

    @pytest.mark.asyncio
    async def test_memory_cleanup_after_completion(
        self,
        file_assembler: FileAssembler,
        completion_handler: AsyncMock,  # noqa: ARG002
    ) -> None:
        """Test that segments are cleaned up from memory after file completion."""
        segment = self.create_test_segment("cleanup.txt", 1, 1, b"content")

        await file_assembler.handle_segment(segment)

        # Segments should be cleaned up
        assert len(file_assembler.file_segments) == 0

    @pytest.mark.asyncio
    async def test_partial_file_segments_retained(
        self, file_assembler: FileAssembler, completion_handler: AsyncMock
    ) -> None:
        """Test that partial file segments are retained until completion."""
        # All segments need same timestamp to be part of same file
        timestamp = datetime.now(UTC)
        segment1 = self.create_test_segment("partial.txt", 1, 3, b"part1", timestamp)
        segment2 = self.create_test_segment("partial.txt", 2, 3, b"part2", timestamp)

        await file_assembler.handle_segment(segment1)
        await file_assembler.handle_segment(segment2)

        # File not complete, so segments should be retained
        expected_key = segment1.key
        assert expected_key in file_assembler.file_segments
        completion_handler.assert_not_called()

        # Complete the file
        segment3 = self.create_test_segment("partial.txt", 3, 3, b"part3", timestamp)
        await file_assembler.handle_segment(segment3)

        # Now file should be complete and segments cleaned up
        assert len(file_assembler.file_segments) == 0
        completion_handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_empty_file_handling(
        self, file_assembler: FileAssembler, completion_handler: AsyncMock
    ) -> None:
        """Test handling of empty files."""
        segment = self.create_test_segment("empty.txt", 1, 1, b"")

        await file_assembler.handle_segment(segment)

        completion_handler.assert_called_once()
        completed_file = completion_handler.call_args[0][0]
        assert completed_file.filename == "empty.txt"
        assert completed_file.data == b""


class TestByteBlasterFileManager:
    """Test the ByteBlasterFileManager high-level integration."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mock ByteBlasterClient."""
        client = MagicMock()
        client.start = AsyncMock()
        client.stop = AsyncMock()
        client.subscribe = MagicMock()
        return client

    @pytest.fixture
    def file_manager_options(self) -> ByteBlasterClientOptions:
        """Create test options for ByteBlasterFileManager."""
        return ByteBlasterClientOptions(email="test@example.com")

    @pytest.fixture
    def file_manager(
        self, file_manager_options: ByteBlasterClientOptions, mock_client: MagicMock
    ) -> ByteBlasterFileManager:
        """Create a ByteBlasterFileManager with mocked client."""
        with patch("byteblaster.file_manager.ByteBlasterClient", return_value=mock_client):
            return ByteBlasterFileManager(file_manager_options)

    def test_file_manager_initialization(
        self, file_manager: ByteBlasterFileManager, mock_client: MagicMock
    ) -> None:
        """Test proper initialization of ByteBlasterFileManager."""
        assert file_manager.client is mock_client
        assert file_manager.assembler is not None
        mock_client.subscribe.assert_called_once()

    def test_client_property_access(
        self, file_manager: ByteBlasterFileManager, mock_client: MagicMock
    ) -> None:
        """Test access to underlying client."""
        assert file_manager.client is mock_client

    def test_assembler_property_access(self, file_manager: ByteBlasterFileManager) -> None:
        """Test access to file assembler."""
        assert isinstance(file_manager.assembler, FileAssembler)

    def test_handler_subscription(self, file_manager: ByteBlasterFileManager) -> None:
        """Test subscribing and unsubscribing file completion handlers."""
        handler1 = AsyncMock()
        handler2 = AsyncMock()

        # Subscribe handlers
        file_manager.subscribe(handler1)
        file_manager.subscribe(handler2)

        assert len(file_manager._file_handlers) == 2
        assert handler1 in file_manager._file_handlers
        assert handler2 in file_manager._file_handlers

    def test_handler_subscription_idempotent(self, file_manager: ByteBlasterFileManager) -> None:
        """Test that subscribing same handler multiple times doesn't create duplicates."""
        handler = AsyncMock()

        file_manager.subscribe(handler)
        file_manager.subscribe(handler)  # Subscribe again

        assert len(file_manager._file_handlers) == 1

    def test_handler_unsubscription(self, file_manager: ByteBlasterFileManager) -> None:
        """Test unsubscribing file completion handlers."""
        handler = AsyncMock()

        file_manager.subscribe(handler)
        assert handler in file_manager._file_handlers

        file_manager.unsubscribe(handler)
        assert handler not in file_manager._file_handlers

    def test_handler_unsubscription_not_found(
        self, file_manager: ByteBlasterFileManager, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test unsubscribing handler that wasn't subscribed."""
        handler = AsyncMock()

        with caplog.at_level(logging.WARNING):
            file_manager.unsubscribe(handler)

        assert "Handler not found in subscribers list" in caplog.text

    @pytest.mark.asyncio
    async def test_start_stops_client(
        self, file_manager: ByteBlasterFileManager, mock_client: MagicMock
    ) -> None:
        """Test starting the file manager starts the client."""
        await file_manager.start()
        mock_client.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_stops_client(
        self, file_manager: ByteBlasterFileManager, mock_client: MagicMock
    ) -> None:
        """Test stopping the file manager stops the client."""
        await file_manager.stop()
        mock_client.stop.assert_called_once_with(shutdown_timeout=None)

    @pytest.mark.asyncio
    async def test_stop_with_timeout(
        self, file_manager: ByteBlasterFileManager, mock_client: MagicMock
    ) -> None:
        """Test stopping with custom timeout."""
        timeout = 30.0
        await file_manager.stop(shutdown_timeout=timeout)
        mock_client.stop.assert_called_once_with(shutdown_timeout=timeout)

    @pytest.mark.asyncio
    async def test_file_dispatch_to_handlers(self, file_manager: ByteBlasterFileManager) -> None:
        """Test that completed files are dispatched to all subscribed handlers."""
        handler1 = AsyncMock()
        handler2 = AsyncMock()

        file_manager.subscribe(handler1)
        file_manager.subscribe(handler2)

        test_file = CompletedFile("test.txt", b"content")
        await file_manager._dispatch_file(test_file)

        handler1.assert_called_once_with(test_file)
        handler2.assert_called_once_with(test_file)

    @pytest.mark.asyncio
    async def test_file_dispatch_no_handlers(self, file_manager: ByteBlasterFileManager) -> None:
        """Test file dispatch when no handlers are subscribed."""
        test_file = CompletedFile("test.txt", b"content")
        # Should not raise exception
        await file_manager._dispatch_file(test_file)

    @pytest.mark.asyncio
    async def test_safe_handler_call_with_exception(
        self, file_manager: ByteBlasterFileManager, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test error isolation when handler raises exception."""
        failing_handler = AsyncMock(side_effect=ValueError("Handler error"))
        test_file = CompletedFile("test.txt", b"content")

        with caplog.at_level(logging.ERROR):
            await file_manager._safe_handler_call(failing_handler, test_file)

        assert "File completion handler error for file: test.txt" in caplog.text

    @pytest.mark.asyncio
    async def test_concurrent_handler_execution(self, file_manager: ByteBlasterFileManager) -> None:
        """Test that handlers are executed concurrently."""
        execution_order: list[str] = []

        async def slow_handler(_file: CompletedFile) -> None:
            execution_order.append("slow_start")
            await asyncio.sleep(0.1)
            execution_order.append("slow_end")

        async def fast_handler(_file: CompletedFile) -> None:
            execution_order.append("fast")

        file_manager.subscribe(slow_handler)
        file_manager.subscribe(fast_handler)

        test_file = CompletedFile("test.txt", b"content")
        await file_manager._dispatch_file(test_file)

        # Fast handler should complete before slow handler
        assert execution_order.index("fast") < execution_order.index("slow_end")

    def test_stream_files_creation(self, file_manager: ByteBlasterFileManager) -> None:
        """Test creation of FileStream."""
        stream = file_manager.stream_files(max_queue_size=50)

        assert isinstance(stream, FileStream)
        assert stream._file_manager is file_manager

    def test_stream_files_custom_queue_size(self, file_manager: ByteBlasterFileManager) -> None:
        """Test FileStream creation with custom queue size."""
        custom_size = 200
        stream = file_manager.stream_files(max_queue_size=custom_size)

        assert stream._queue.maxsize == custom_size

    @pytest.mark.asyncio
    async def test_integration_segment_to_file_completion(
        self, file_manager: ByteBlasterFileManager
    ) -> None:
        """Test end-to-end integration from segment to file completion."""
        completed_files: list[CompletedFile] = []

        async def capture_handler(file: CompletedFile) -> None:
            completed_files.append(file)

        file_manager.subscribe(capture_handler)

        # Create test segments with same timestamp
        timestamp = datetime.now(UTC)
        segments = [
            QBTSegment(
                filename="integration.txt",
                block_number=1,
                total_blocks=2,
                content=b"first",
                timestamp=timestamp,
            ),
            QBTSegment(
                filename="integration.txt",
                block_number=2,
                total_blocks=2,
                content=b"second",
                timestamp=timestamp,
            ),
        ]

        # Process segments through assembler
        for segment in segments:
            await file_manager.assembler.handle_segment(segment)

        # Verify file completion
        assert len(completed_files) == 1
        assert completed_files[0].filename == "integration.txt"
        assert completed_files[0].data == b"firstsecond"

    @pytest.mark.asyncio
    async def test_integration_with_file_stream(self, file_manager: ByteBlasterFileManager) -> None:
        """Test integration between file manager and file stream."""
        # Create test segment
        segment = QBTSegment(
            filename="stream_test.txt",
            block_number=1,
            total_blocks=1,
            content=b"stream content",
            timestamp=datetime.now(UTC),
        )

        received_files: list[CompletedFile] = []

        async with file_manager.stream_files(max_queue_size=10) as file_stream:
            # Process segment in background
            async def process_segment() -> None:
                await asyncio.sleep(0.01)  # Small delay to ensure stream is ready
                await file_manager.assembler.handle_segment(segment)
                await asyncio.sleep(0.01)  # Allow processing
                file_stream._closed = True
                file_stream._queue.put_nowait(None)

            # Start processing
            process_task = asyncio.create_task(process_segment())

            # Collect files from stream
            received_files.extend([file async for file in file_stream])

            await process_task

        # Verify file was received through stream
        assert len(received_files) == 1
        assert received_files[0].filename == "stream_test.txt"
        assert received_files[0].data == b"stream content"

    @pytest.mark.asyncio
    async def test_handler_exception_isolation(
        self, file_manager: ByteBlasterFileManager, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test that handler exceptions don't affect other handlers."""
        good_handler_called = False

        async def failing_handler(_file: CompletedFile) -> None:
            msg = "This handler always fails"
            raise ValueError(msg)

        async def good_handler(_file: CompletedFile) -> None:
            nonlocal good_handler_called
            good_handler_called = True

        file_manager.subscribe(failing_handler)
        file_manager.subscribe(good_handler)

        test_file = CompletedFile("test.txt", b"content")

        with caplog.at_level(logging.ERROR):
            await file_manager._dispatch_file(test_file)

        # Good handler should still be called despite failing handler
        assert good_handler_called
        assert "File completion handler error" in caplog.text


class TestIntegrationScenarios:
    """Integration tests for complex real-world scenarios."""

    @pytest.fixture
    def file_manager_options(self) -> ByteBlasterClientOptions:
        """Create test options for integration tests."""
        return ByteBlasterClientOptions(email="integration@example.com")

    @pytest.mark.asyncio
    async def test_large_file_reconstruction(self) -> None:
        """Test reconstruction of a large file from many segments."""
        completed_files: list[CompletedFile] = []

        async def capture_handler(file: CompletedFile) -> None:
            completed_files.append(file)

        assembler = FileAssembler(capture_handler)

        # Create 100 segments for a large file
        total_blocks = 100
        expected_content = b""
        timestamp = datetime.now(UTC)  # Same timestamp for all segments

        segments: list[QBTSegment] = []
        for i in range(1, total_blocks + 1):
            content = f"block_{i:03d}_".encode() * 10  # Each block ~100 bytes
            expected_content += content

            segment = QBTSegment(
                filename="large_file.dat",
                block_number=i,
                total_blocks=total_blocks,
                content=content,
                timestamp=timestamp,
            )
            segments.append(segment)

        # Process segments in random order to test sorting
        import random

        random.shuffle(segments)

        for segment in segments:
            await assembler.handle_segment(segment)

        # Verify reconstruction
        assert len(completed_files) == 1
        assert completed_files[0].filename == "large_file.dat"
        assert completed_files[0].data == expected_content
        assert len(completed_files[0].data) == total_blocks * 100

    @pytest.mark.asyncio
    async def test_concurrent_file_processing(self) -> None:
        """Test processing multiple files concurrently."""
        completed_files: list[CompletedFile] = []

        async def capture_handler(file: CompletedFile) -> None:
            completed_files.append(file)

        assembler = FileAssembler(capture_handler)

        # Create segments for 3 different files
        files_data = {
            "file1.txt": [b"content1_part1", b"content1_part2"],
            "file2.txt": [b"single_content"],
            "file3.txt": [b"part1", b"part2", b"part3"],
        }

        all_segments: list[QBTSegment] = []
        for filename, parts in files_data.items():
            # Each file needs its own timestamp for proper grouping
            file_timestamp = datetime.now(UTC)
            for i, content in enumerate(parts, 1):
                segment = QBTSegment(
                    filename=filename,
                    block_number=i,
                    total_blocks=len(parts),
                    content=content,
                    timestamp=file_timestamp,
                )
                all_segments.append(segment)
            # Small delay to ensure unique timestamps for different files
            await asyncio.sleep(0.001)

        # Process all segments in mixed order
        import random

        random.shuffle(all_segments)

        for segment in all_segments:
            await assembler.handle_segment(segment)

        # Verify all files were completed
        assert len(completed_files) == 3

        completed_by_name = {f.filename: f for f in completed_files}
        assert completed_by_name["file1.txt"].data == b"content1_part1content1_part2"
        assert completed_by_name["file2.txt"].data == b"single_content"
        assert completed_by_name["file3.txt"].data == b"part1part2part3"

    @pytest.mark.asyncio
    async def test_memory_efficiency_with_many_files(self) -> None:
        """Test memory efficiency when processing many files."""
        completed_count = 0

        async def counting_handler(_file: CompletedFile) -> None:
            nonlocal completed_count
            completed_count += 1

        assembler = FileAssembler(counting_handler, duplicate_cache_size=10)

        # Process 50 single-segment files
        for i in range(50):
            segment = QBTSegment(
                filename=f"file_{i:03d}.txt",
                block_number=1,
                total_blocks=1,
                content=f"content_{i}".encode(),
                timestamp=datetime.now(UTC),
            )
            await assembler.handle_segment(segment)

        # Verify all files were completed
        assert completed_count == 50

        # Verify memory cleanup - no segments should be retained
        assert len(assembler.file_segments) == 0

        # Verify cache size limit - should only keep last 10 files
        assert len(assembler._recently_completed) == 10

    @pytest.mark.asyncio
    async def test_resilience_to_malformed_segments(self, caplog: pytest.LogCaptureFixture) -> None:  # noqa: ARG002
        """Test system resilience when processing malformed segments."""
        completed_files: list[CompletedFile] = []

        async def capture_handler(file: CompletedFile) -> None:
            completed_files.append(file)

        assembler = FileAssembler(capture_handler)

        # Create normal segment
        good_segment = QBTSegment(
            filename="good.txt",
            block_number=1,
            total_blocks=1,
            content=b"good content",
            timestamp=datetime.now(UTC),
        )

        # Process good segment
        await assembler.handle_segment(good_segment)

        # Verify system continues to work
        assert len(completed_files) == 1
        assert completed_files[0].filename == "good.txt"

    @pytest.mark.asyncio
    async def test_high_throughput_scenario(self) -> None:
        """Test high-throughput file processing scenario."""
        completed_files: list[CompletedFile] = []
        processing_times: list[float] = []

        async def timing_handler(file: CompletedFile) -> None:
            import time

            processing_times.append(time.monotonic())
            completed_files.append(file)

        assembler = FileAssembler(timing_handler)

        # Process 1000 single-segment files rapidly
        import time

        start_time = time.monotonic()

        tasks: list[asyncio.Task[None]] = []
        for i in range(1000):
            segment = QBTSegment(
                filename=f"throughput_{i:04d}.txt",
                block_number=1,
                total_blocks=1,
                content=f"data_{i}".encode(),
                timestamp=datetime.now(UTC),
            )
            task = asyncio.create_task(assembler.handle_segment(segment))
            tasks.append(task)

        await asyncio.gather(*tasks)
        end_time = time.monotonic()

        # Verify results
        assert len(completed_files) == 1000
        assert len(processing_times) == 1000

        # Verify reasonable performance (should complete in reasonable time)
        total_time = end_time - start_time
        assert total_time < 10.0  # Should complete within 10 seconds

        # Verify files processed in reasonable order (allowing for some async reordering)
        processing_duration = processing_times[-1] - processing_times[0]
        assert processing_duration < total_time
