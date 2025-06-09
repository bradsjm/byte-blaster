# pyright: reportPrivateUsage=false
"""Comprehensive tests for WeatherDataHandler class."""

import logging
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from byteblaster.handler import WeatherDataHandler
from byteblaster.protocol.models import QBTSegment


class TestWeatherDataHandlerInit:
    """Test WeatherDataHandler initialization."""

    def test_init_with_default_output_dir(self):
        """Test initialization with default output directory."""
        with patch.object(Path, "mkdir") as mock_mkdir:
            handler = WeatherDataHandler()

            assert handler.output_dir == Path("weather_data")
            assert handler.file_segments == {}
            mock_mkdir.assert_called_once_with(exist_ok=True)

    def test_init_with_custom_output_dir(self):
        """Test initialization with custom output directory."""
        custom_dir = "custom_weather_data"
        with patch.object(Path, "mkdir") as mock_mkdir:
            handler = WeatherDataHandler(output_dir=custom_dir)

            assert handler.output_dir == Path(custom_dir)
            assert handler.file_segments == {}
            mock_mkdir.assert_called_once_with(exist_ok=True)

    def test_init_creates_output_directory(self, tmp_path: Path) -> None:
        """Test that initialization creates the output directory."""
        output_dir = tmp_path / "test_weather_data"
        WeatherDataHandler(output_dir=str(output_dir))

        assert output_dir.exists()
        assert output_dir.is_dir()


class TestWeatherDataHandlerHandleSegment:
    """Test WeatherDataHandler.handle_segment method."""

    @pytest.fixture
    def handler(self, tmp_path: Path) -> WeatherDataHandler:
        """Create a WeatherDataHandler instance for testing."""
        return WeatherDataHandler(output_dir=str(tmp_path / "weather_data"))

    @pytest.fixture
    def sample_segment(self) -> QBTSegment:
        """Create a sample QBTSegment for testing."""
        timestamp = datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC)
        return QBTSegment(
            filename="test_file.txt",
            block_number=1,
            total_blocks=3,
            content=b"Test content block 1",
            checksum=12345,
            length=20,
            version=1,
            timestamp=timestamp,
            received_at=timestamp,
            header="TEST_HEADER",
            source="TEST_SOURCE",
        )

    @pytest.mark.asyncio
    async def test_handle_segment_filters_fillfile(
        self,
        handler: WeatherDataHandler,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that FILLFILE.TXT segments are filtered out."""
        fillfile_segment = QBTSegment(
            filename="FILLFILE.TXT",
            block_number=1,
            total_blocks=1,
            content=b"filler content",
        )

        with caplog.at_level(logging.DEBUG):
            await handler.handle_segment(fillfile_segment)

        assert handler.file_segments == {}
        assert "FILLFILE.TXT" not in caplog.text

    @pytest.mark.asyncio
    async def test_handle_segment_groups_by_file_key(
        self,
        handler: WeatherDataHandler,
        sample_segment: QBTSegment,
    ) -> None:
        """Test that segments are properly grouped by file key."""
        await handler.handle_segment(sample_segment)

        file_key = sample_segment.key
        assert file_key in handler.file_segments
        assert len(handler.file_segments[file_key]) == 1
        assert handler.file_segments[file_key][0] == sample_segment

    @pytest.mark.asyncio
    async def test_handle_segment_adds_to_existing_group(
        self,
        handler: WeatherDataHandler,
        sample_segment: QBTSegment,
    ) -> None:
        """Test that segments are added to existing file groups."""
        # Add first segment
        await handler.handle_segment(sample_segment)

        # Create second segment with same file key
        second_segment = QBTSegment(
            filename=sample_segment.filename,
            block_number=2,
            total_blocks=3,
            content=b"Test content block 2",
            timestamp=sample_segment.timestamp,  # Same timestamp for same key
        )

        await handler.handle_segment(second_segment)

        file_key = sample_segment.key
        assert len(handler.file_segments[file_key]) == 2
        assert second_segment in handler.file_segments[file_key]

    @pytest.mark.asyncio
    async def test_handle_segment_logs_debug_info(
        self,
        handler: WeatherDataHandler,
        sample_segment: QBTSegment,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that debug information is logged for non-FILLFILE segments."""
        with caplog.at_level(logging.DEBUG):
            await handler.handle_segment(sample_segment)

        expected_message = (
            f"Received: {sample_segment.filename} block "
            f"{sample_segment.block_number}/{sample_segment.total_blocks}"
        )
        assert expected_message in caplog.text

    @pytest.mark.asyncio
    async def test_handle_segment_triggers_reconstruction_when_complete(
        self,
        handler: WeatherDataHandler,
    ) -> None:
        """Test that file reconstruction is triggered when all segments are received."""
        timestamp = datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC)

        # Create segments for a 2-block file
        segment1 = QBTSegment(
            filename="complete_file.txt",
            block_number=1,
            total_blocks=2,
            content=b"First block",
            timestamp=timestamp,
        )
        segment2 = QBTSegment(
            filename="complete_file.txt",
            block_number=2,
            total_blocks=2,
            content=b"Second block",
            timestamp=timestamp,
        )

        with patch.object(handler, "_reconstruct_file", new_callable=AsyncMock) as mock_reconstruct:
            await handler.handle_segment(segment1)
            mock_reconstruct.assert_not_called()

            await handler.handle_segment(segment2)
            mock_reconstruct.assert_called_once_with(segment1.key, [segment1, segment2])

    @pytest.mark.asyncio
    async def test_handle_segment_concurrent_files(self, handler: WeatherDataHandler) -> None:
        """Test handling of multiple files concurrently."""
        timestamp1 = datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC)
        timestamp2 = datetime(2024, 1, 15, 13, 0, 0, tzinfo=UTC)

        # Segments for first file
        file1_seg1 = QBTSegment(
            filename="file1.txt",
            block_number=1,
            total_blocks=2,
            content=b"File 1 Block 1",
            timestamp=timestamp1,
        )
        file1_seg2 = QBTSegment(
            filename="file1.txt",
            block_number=2,
            total_blocks=2,
            content=b"File 1 Block 2",
            timestamp=timestamp1,
        )

        # Segments for second file
        file2_seg1 = QBTSegment(
            filename="file2.txt",
            block_number=1,
            total_blocks=2,
            content=b"File 2 Block 1",
            timestamp=timestamp2,
        )

        await handler.handle_segment(file1_seg1)
        await handler.handle_segment(file2_seg1)

        # Both files should have separate segment collections
        assert len(handler.file_segments) == 2
        assert len(handler.file_segments[file1_seg1.key]) == 1
        assert len(handler.file_segments[file2_seg1.key]) == 1

        with patch.object(handler, "_reconstruct_file", new_callable=AsyncMock) as mock_reconstruct:
            await handler.handle_segment(file1_seg2)
            mock_reconstruct.assert_called_once_with(file1_seg1.key, [file1_seg1, file1_seg2])


class TestWeatherDataHandlerReconstructFile:
    """Test WeatherDataHandler._reconstruct_file method."""

    @pytest.fixture
    def handler(self, tmp_path: Path) -> WeatherDataHandler:
        """Create a WeatherDataHandler instance for testing."""
        return WeatherDataHandler(output_dir=str(tmp_path / "weather_data"))

    @pytest.fixture
    def sample_segments(self) -> list[QBTSegment]:
        """Create sample segments for testing file reconstruction."""
        timestamp = datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC)
        return [
            QBTSegment(
                filename="test_file.txt",
                block_number=2,
                total_blocks=3,
                content=b"Second block",
                timestamp=timestamp,
            ),
            QBTSegment(
                filename="test_file.txt",
                block_number=1,
                total_blocks=3,
                content=b"First block",
                timestamp=timestamp,
            ),
            QBTSegment(
                filename="test_file.txt",
                block_number=3,
                total_blocks=3,
                content=b"Third block",
                timestamp=timestamp,
            ),
        ]

    @pytest.mark.asyncio
    async def test_reconstruct_file_sorts_segments_by_block_number(
        self,
        handler: WeatherDataHandler,
        sample_segments: list[QBTSegment],
    ) -> None:
        """Test that segments are sorted by block number before reconstruction."""
        file_key = sample_segments[0].key
        handler.file_segments[file_key] = sample_segments.copy()

        await handler._reconstruct_file(file_key, sample_segments)

        output_path = handler.output_dir / "test_file.txt"
        assert output_path.exists()

        content = output_path.read_bytes()
        assert content == b"First blockSecond blockThird block"

    @pytest.mark.asyncio
    async def test_reconstruct_file_creates_parent_directories(
        self,
        handler: WeatherDataHandler,
    ) -> None:
        """Test that parent directories are created when necessary."""
        timestamp = datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC)
        segment = QBTSegment(
            filename="subdir/nested/file.txt",
            block_number=1,
            total_blocks=1,
            content=b"Test content",
            timestamp=timestamp,
        )

        file_key = segment.key
        handler.file_segments[file_key] = [segment]

        await handler._reconstruct_file(file_key, [segment])

        output_path = handler.output_dir / "subdir" / "nested" / "file.txt"
        assert output_path.exists()
        assert output_path.read_bytes() == b"Test content"

    @pytest.mark.asyncio
    async def test_reconstruct_file_logs_success(
        self,
        handler: WeatherDataHandler,
        sample_segments: list[QBTSegment],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that successful file reconstruction is logged."""
        file_key = sample_segments[0].key
        handler.file_segments[file_key] = sample_segments.copy()

        with caplog.at_level(logging.INFO):
            await handler._reconstruct_file(file_key, sample_segments)

        output_path = handler.output_dir / "test_file.txt"
        expected_size = sum(len(seg.content) for seg in sample_segments)
        expected_message = f"✓ Saved complete file: {output_path} ({expected_size} bytes)"
        assert expected_message in caplog.text

    @pytest.mark.asyncio
    async def test_reconstruct_file_handles_write_errors(
        self,
        handler: WeatherDataHandler,
        sample_segments: list[QBTSegment],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test error handling when file write fails."""
        file_key = sample_segments[0].key
        handler.file_segments[file_key] = sample_segments.copy()

        with (
            patch.object(Path, "write_bytes", side_effect=OSError("Permission denied")),
            caplog.at_level(logging.ERROR),
        ):
            await handler._reconstruct_file(file_key, sample_segments)

        output_path = handler.output_dir / "test_file.txt"
        expected_message = f"✗ Failed to save {output_path}"
        assert expected_message in caplog.text

    @pytest.mark.asyncio
    async def test_reconstruct_file_cleans_up_memory(
        self,
        handler: WeatherDataHandler,
        sample_segments: list[QBTSegment],
    ) -> None:
        """Test that segment memory is cleaned up after reconstruction."""
        file_key = sample_segments[0].key
        handler.file_segments[file_key] = sample_segments.copy()

        assert file_key in handler.file_segments

        await handler._reconstruct_file(file_key, sample_segments)

        assert file_key not in handler.file_segments

    @pytest.mark.asyncio
    async def test_reconstruct_file_cleans_up_memory_even_on_error(
        self,
        handler: WeatherDataHandler,
        sample_segments: list[QBTSegment],
    ) -> None:
        """Test that segment memory is cleaned up even when file write fails."""
        file_key = sample_segments[0].key
        handler.file_segments[file_key] = sample_segments.copy()

        with patch.object(Path, "write_bytes", side_effect=OSError("Permission denied")):
            await handler._reconstruct_file(file_key, sample_segments)

        assert file_key not in handler.file_segments

    @pytest.mark.asyncio
    async def test_reconstruct_file_empty_content(self, handler: WeatherDataHandler) -> None:
        """Test reconstruction of file with empty content."""
        timestamp = datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC)
        segment = QBTSegment(
            filename="empty_file.txt",
            block_number=1,
            total_blocks=1,
            content=b"",
            timestamp=timestamp,
        )

        file_key = segment.key
        handler.file_segments[file_key] = [segment]

        await handler._reconstruct_file(file_key, [segment])

        output_path = handler.output_dir / "empty_file.txt"
        assert output_path.exists()
        assert output_path.read_bytes() == b""

    @pytest.mark.asyncio
    async def test_reconstruct_file_large_content(self, handler: WeatherDataHandler) -> None:
        """Test reconstruction of file with large content."""
        timestamp = datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC)
        large_content = b"X" * 10000  # 10KB of data

        segment = QBTSegment(
            filename="large_file.txt",
            block_number=1,
            total_blocks=1,
            content=large_content,
            timestamp=timestamp,
        )

        file_key = segment.key
        handler.file_segments[file_key] = [segment]

        await handler._reconstruct_file(file_key, [segment])

        output_path = handler.output_dir / "large_file.txt"
        assert output_path.exists()
        assert output_path.read_bytes() == large_content


class TestWeatherDataHandlerIntegration:
    """Integration tests for WeatherDataHandler."""

    @pytest.fixture
    def handler(self, tmp_path: Path) -> WeatherDataHandler:
        """Create a WeatherDataHandler instance for testing."""
        return WeatherDataHandler(output_dir=str(tmp_path / "weather_data"))

    @pytest.mark.asyncio
    async def test_complete_file_workflow(self, handler: WeatherDataHandler) -> None:
        """Test the complete workflow from segments to reconstructed file."""
        timestamp = datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC)

        # Create segments for a complete file (received out of order)
        segments = [
            QBTSegment(
                filename="weather_report.txt",
                block_number=3,
                total_blocks=3,
                content=b"End of report.",
                timestamp=timestamp,
            ),
            QBTSegment(
                filename="weather_report.txt",
                block_number=1,
                total_blocks=3,
                content=b"Weather Report: ",
                timestamp=timestamp,
            ),
            QBTSegment(
                filename="weather_report.txt",
                block_number=2,
                total_blocks=3,
                content=b"Sunny, 75F. ",
                timestamp=timestamp,
            ),
        ]

        # Process segments
        for segment in segments:
            await handler.handle_segment(segment)

        # Verify file was created with correct content
        output_path = handler.output_dir / "weather_report.txt"
        assert output_path.exists()

        expected_content = b"Weather Report: Sunny, 75F. End of report."
        assert output_path.read_bytes() == expected_content

        # Verify memory was cleaned up
        assert len(handler.file_segments) == 0

    @pytest.mark.asyncio
    async def test_multiple_files_concurrent_processing(
        self,
        handler: WeatherDataHandler,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test processing multiple files concurrently."""
        timestamp1 = datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC)
        timestamp2 = datetime(2024, 1, 15, 13, 0, 0, tzinfo=UTC)

        # Create segments for two different files
        file1_segments = [
            QBTSegment(
                filename="file1.txt",
                block_number=1,
                total_blocks=2,
                content=b"File 1 content part 1",
                timestamp=timestamp1,
            ),
            QBTSegment(
                filename="file1.txt",
                block_number=2,
                total_blocks=2,
                content=b"File 1 content part 2",
                timestamp=timestamp1,
            ),
        ]

        file2_segments = [
            QBTSegment(
                filename="file2.txt",
                block_number=1,
                total_blocks=2,
                content=b"File 2 content part 1",
                timestamp=timestamp2,
            ),
            QBTSegment(
                filename="file2.txt",
                block_number=2,
                total_blocks=2,
                content=b"File 2 content part 2",
                timestamp=timestamp2,
            ),
        ]

        # Process segments in interleaved order
        all_segments = [
            file1_segments[0],
            file2_segments[0],
            file2_segments[1],  # Complete file2 first
            file1_segments[1],  # Complete file1 second
        ]

        with caplog.at_level(logging.INFO):
            for segment in all_segments:
                await handler.handle_segment(segment)

        # Verify both files were created
        file1_path = handler.output_dir / "file1.txt"
        file2_path = handler.output_dir / "file2.txt"

        assert file1_path.exists()
        assert file2_path.exists()

        assert file1_path.read_bytes() == b"File 1 content part 1File 1 content part 2"
        assert file2_path.read_bytes() == b"File 2 content part 1File 2 content part 2"

        # Verify both completions were logged
        assert "✓ Saved complete file:" in caplog.text
        assert str(file1_path) in caplog.text
        assert str(file2_path) in caplog.text

        # Verify memory was cleaned up
        assert len(handler.file_segments) == 0

    @pytest.mark.asyncio
    async def test_partial_file_memory_management(self, handler: WeatherDataHandler) -> None:
        """Test that partial files remain in memory until complete."""
        timestamp = datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC)

        # Create only first segment of a 3-segment file
        segment1 = QBTSegment(
            filename="incomplete_file.txt",
            block_number=1,
            total_blocks=3,
            content=b"First block",
            timestamp=timestamp,
        )

        await handler.handle_segment(segment1)

        # Verify segment is stored in memory
        file_key = segment1.key
        assert file_key in handler.file_segments
        assert len(handler.file_segments[file_key]) == 1

        # Verify no file was written yet
        output_path = handler.output_dir / "incomplete_file.txt"
        assert not output_path.exists()

    @pytest.mark.asyncio
    async def test_fillfile_filtering_with_real_files(self, handler: WeatherDataHandler) -> None:
        """Test that FILLFILE segments are filtered while real files are processed."""
        timestamp = datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC)

        segments = [
            QBTSegment(filename="FILLFILE.TXT", block_number=1, total_blocks=1, content=b"filler"),
            QBTSegment(
                filename="real_file.txt",
                block_number=1,
                total_blocks=2,
                content=b"Real content 1",
                timestamp=timestamp,
            ),
            QBTSegment(
                filename="FILLFILE.TXT",
                block_number=1,
                total_blocks=1,
                content=b"more filler",
            ),
            QBTSegment(
                filename="real_file.txt",
                block_number=2,
                total_blocks=2,
                content=b"Real content 2",
                timestamp=timestamp,
            ),
        ]

        for segment in segments:
            await handler.handle_segment(segment)

        # Verify only real file was created
        real_file_path = handler.output_dir / "real_file.txt"
        fillfile_path = handler.output_dir / "FILLFILE.TXT"

        assert real_file_path.exists()
        assert not fillfile_path.exists()

        assert real_file_path.read_bytes() == b"Real content 1Real content 2"


class TestWeatherDataHandlerEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.fixture
    def handler(self, tmp_path: Path) -> WeatherDataHandler:
        """Create a WeatherDataHandler instance for testing."""
        return WeatherDataHandler(output_dir=str(tmp_path / "weather_data"))

    @pytest.mark.asyncio
    async def test_single_block_file(self, handler: WeatherDataHandler) -> None:
        """Test handling of single-block files."""
        timestamp = datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC)
        segment = QBTSegment(
            filename="single_block.txt",
            block_number=1,
            total_blocks=1,
            content=b"Complete file in one block",
            timestamp=timestamp,
        )

        await handler.handle_segment(segment)

        output_path = handler.output_dir / "single_block.txt"
        assert output_path.exists()
        assert output_path.read_bytes() == b"Complete file in one block"
        assert len(handler.file_segments) == 0

    @pytest.mark.asyncio
    async def test_binary_content(self, handler: WeatherDataHandler) -> None:
        """Test handling of binary file content."""
        timestamp = datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC)
        binary_content = bytes(range(256))  # Binary data with all byte values

        segment = QBTSegment(
            filename="binary_file.bin",
            block_number=1,
            total_blocks=1,
            content=binary_content,
            timestamp=timestamp,
        )

        await handler.handle_segment(segment)

        output_path = handler.output_dir / "binary_file.bin"
        assert output_path.exists()
        assert output_path.read_bytes() == binary_content

    @pytest.mark.asyncio
    async def test_filename_with_special_characters(self, handler: WeatherDataHandler) -> None:
        """Test handling of filenames with special characters."""
        timestamp = datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC)
        segment = QBTSegment(
            filename="file with spaces & symbols!.txt",
            block_number=1,
            total_blocks=1,
            content=b"Content with special filename",
            timestamp=timestamp,
        )

        await handler.handle_segment(segment)

        output_path = handler.output_dir / "file with spaces & symbols!.txt"
        assert output_path.exists()
        assert output_path.read_bytes() == b"Content with special filename"

    @pytest.mark.asyncio
    async def test_zero_length_content(self, handler: WeatherDataHandler) -> None:
        """Test handling of segments with zero-length content."""
        timestamp = datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC)
        segments = [
            QBTSegment(
                filename="mixed_content.txt",
                block_number=1,
                total_blocks=3,
                content=b"Start",
                timestamp=timestamp,
            ),
            QBTSegment(
                filename="mixed_content.txt",
                block_number=2,
                total_blocks=3,
                content=b"",  # Empty block
                timestamp=timestamp,
            ),
            QBTSegment(
                filename="mixed_content.txt",
                block_number=3,
                total_blocks=3,
                content=b"End",
                timestamp=timestamp,
            ),
        ]

        for segment in segments:
            await handler.handle_segment(segment)

        output_path = handler.output_dir / "mixed_content.txt"
        assert output_path.exists()
        assert output_path.read_bytes() == b"StartEnd"


# Test Coverage Summary:
# ====================
#
# This comprehensive test suite covers all major functionality of the WeatherDataHandler class:
#
# 1. **Initialization Testing** (3 tests):
#    - Default output directory creation
#    - Custom output directory handling
#    - Filesystem directory creation
#
# 2. **Segment Handling** (6 tests):
#    - FILLFILE.TXT filtering (filler data exclusion)
#    - Segment grouping by unique file key
#    - Adding segments to existing groups
#    - Debug logging verification
#    - File reconstruction triggering when complete
#    - Concurrent multi-file processing
#
# 3. **File Reconstruction** (7 tests):
#    - Segment sorting by block number
#    - Parent directory creation
#    - Success logging
#    - Error handling for file system failures
#    - Memory cleanup after successful reconstruction
#    - Memory cleanup even when errors occur
#    - Empty and large content handling
#
# 4. **Integration Testing** (4 tests):
#    - Complete end-to-end workflow
#    - Multiple concurrent file processing
#    - Partial file memory management
#    - FILLFILE filtering with real files
#
# 5. **Edge Cases** (5 tests):
#    - Single-block files
#    - Binary content handling
#    - Special characters in filenames
#    - Zero-length content blocks
#    - Mixed content with empty blocks
#
# Total: 25 test cases covering:
# - All public methods (__init__, handle_segment)
# - Private method behavior (_reconstruct_file)
# - Error conditions and recovery
# - Memory management and cleanup
# - File system operations
# - Logging and debugging
# - Protocol-specific requirements (FILLFILE filtering)
# - Concurrent processing scenarios
# - Edge cases and boundary conditions
#
# The tests use proper async/await patterns, mock external dependencies,
# and follow pytest best practices with descriptive names and clear assertions.
