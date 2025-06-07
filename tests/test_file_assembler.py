"""Test script to verify ByteBlaster can handle interleaved blocks from multiple files.

This test verifies that the protocol can handle blocks from multiple files arriving
out of order, which allows higher priority files to interrupt lower priority transfers.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock
import logging

import pytest
from _pytest.logging import LogCaptureFixture

from byte_blaster import QBTSegment
from byte_blaster.file_manager import FileAssembler


def create_test_segment(
    filename: str,
    block_number: int,
    total_blocks: int,
    content: bytes,
    timestamp: datetime,
) -> QBTSegment:
    """Create a test segment with specified parameters.

    Args:
        filename: Name of the file
        block_number: Block number (1-based)
        total_blocks: Total number of blocks in file
        content: Block content
        timestamp: File timestamp for generating unique key

    Returns:
        QBTSegment for testing

    """
    return QBTSegment(
        filename=filename,
        block_number=block_number,
        total_blocks=total_blocks,
        content=content,
        checksum=sum(content) & 0xFFFF,
        length=len(content),
        timestamp=timestamp,
    )


@pytest.mark.asyncio
async def test_interleaved_blocks() -> None:
    """Test that interleaved blocks from multiple files are handled correctly."""
    on_file_completed = AsyncMock()
    assembler = FileAssembler(on_file_completed=on_file_completed)

    time1 = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
    time2 = datetime(2024, 1, 1, 12, 0, 1, tzinfo=UTC)
    time3 = datetime(2024, 1, 1, 12, 0, 2, tzinfo=UTC)

    segments = [
        create_test_segment("low_priority.txt", 1, 4, b"Low-1: ", time1),
        create_test_segment("low_priority.txt", 2, 4, b"Low-2: ", time1),
        create_test_segment("high_priority.txt", 1, 2, b"High-1: URGENT", time2),
        create_test_segment("high_priority.txt", 2, 2, b"High-2: ALERT", time2),
        create_test_segment("medium_priority.txt", 1, 3, b"Med-1: ", time3),
        create_test_segment("low_priority.txt", 3, 4, b"Low-3: ", time1),
        create_test_segment("medium_priority.txt", 2, 3, b"Med-2: ", time3),
        create_test_segment("medium_priority.txt", 3, 3, b"Med-3: ", time3),
        create_test_segment("low_priority.txt", 4, 4, b"Low-4: END", time1),
    ]

    for segment in segments:
        await assembler.handle_segment(segment)

    assert on_file_completed.call_count == 3
    completed_files = {call.args[0].filename for call in on_file_completed.call_args_list}
    expected_files = {"high_priority.txt", "medium_priority.txt", "low_priority.txt"}
    assert completed_files == expected_files

    # To check the order, we'd need to inspect the mock calls.
    call_args = [call.args[0] for call in on_file_completed.call_args_list]
    assert call_args[0].filename == "high_priority.txt"
    assert call_args[1].filename == "medium_priority.txt"
    assert call_args[2].filename == "low_priority.txt"


@pytest.mark.asyncio
async def test_same_filename_different_timestamps() -> None:
    """Test that files with same name but different timestamps are handled separately."""
    on_file_completed = AsyncMock()
    assembler = FileAssembler(on_file_completed=on_file_completed)

    time1 = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
    time2 = datetime(2024, 1, 1, 12, 0, 5, tzinfo=UTC)

    segments = [
        create_test_segment("weather.txt", 1, 2, b"Version 1: Old data", time1),
        create_test_segment("weather.txt", 1, 3, b"Version 2: New ", time2),
        create_test_segment("weather.txt", 2, 2, b" complete", time1),
        create_test_segment("weather.txt", 2, 3, b"updated ", time2),
        create_test_segment("weather.txt", 3, 3, b"data", time2),
    ]

    for segment in segments:
        await assembler.handle_segment(segment)

    assert on_file_completed.call_count == 2
    completed_files = [call.args[0] for call in on_file_completed.call_args_list]
    assert all(cf.filename == "weather.txt" for cf in completed_files)
    assert completed_files[0].data == b"Version 1: Old data complete"
    assert completed_files[1].data == b"Version 2: New updated data"


@pytest.mark.asyncio
async def test_out_of_order_blocks() -> None:
    """Test that blocks arriving out of order within a file are handled correctly."""
    on_file_completed = AsyncMock()
    assembler = FileAssembler(on_file_completed=on_file_completed)

    timestamp = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)

    segments = [
        create_test_segment("file.txt", 3, 4, b"Third ", timestamp),
        create_test_segment("file.txt", 1, 4, b"First ", timestamp),
        create_test_segment("file.txt", 4, 4, b"Fourth", timestamp),
        create_test_segment("file.txt", 2, 4, b"Second ", timestamp),
    ]

    for segment in segments:
        await assembler.handle_segment(segment)

    assert on_file_completed.call_count == 1
    completed_file = on_file_completed.call_args.args[0]
    assert completed_file.filename == "file.txt"
    assert completed_file.data == b"First Second Third Fourth"


@pytest.mark.asyncio
async def test_unique_keys() -> None:
    """Test that segment keys properly distinguish between different files."""
    time1 = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
    time2 = datetime(2024, 1, 1, 12, 0, 1, tzinfo=UTC)

    segment1 = create_test_segment("file.txt", 1, 1, b"a", time1)
    segment2 = create_test_segment("file.txt", 1, 1, b"b", time2)
    segment3 = create_test_segment("other.txt", 1, 1, b"c", time1)

    assert segment1.key != segment2.key
    assert segment1.key != segment3.key
    assert segment2.key != segment3.key


@pytest.mark.asyncio
async def test_fillfile_is_ignored() -> None:
    """Test that FILLFILE.TXT segments are ignored."""
    on_file_completed = AsyncMock()
    assembler = FileAssembler(on_file_completed=on_file_completed)
    segment = create_test_segment("FILLFILE.TXT", 1, 1, b"filler", datetime.now(UTC))

    await assembler.handle_segment(segment)

    on_file_completed.assert_not_called()


@pytest.mark.asyncio
async def test_duplicate_segments_are_handled(caplog: LogCaptureFixture) -> None:
    """Test that duplicate segments for a completed file are ignored."""
    # Set the log capture level to INFO to catch the duplicate file warning
    caplog.set_level(logging.INFO)
    
    on_file_completed = AsyncMock()
    assembler = FileAssembler(on_file_completed=on_file_completed)
    timestamp = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)

    segment1 = create_test_segment("file.txt", 1, 1, b"data", timestamp)
    await assembler.handle_segment(segment1)

    on_file_completed.assert_called_once()
    assert on_file_completed.call_args.args[0].filename == "file.txt"

    # Handle the same segment again
    await assembler.handle_segment(segment1)
    on_file_completed.assert_called_once()  # No new file completion

    # The log should indicate a duplicate was skipped
    assert any("Skipping segment for duplicate file" in line for line in caplog.text.splitlines())
