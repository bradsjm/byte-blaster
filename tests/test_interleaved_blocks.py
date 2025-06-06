#!/usr/bin/env python3
"""Test script to verify ByteBlaster can handle interleaved blocks from multiple files.

This test verifies that the protocol can handle blocks from multiple files arriving
out of order, which allows higher priority files to interrupt lower priority transfers.
"""

import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from byte_blaster import QuickBlockTransferSegment


class InterleavedBlockHandler:
    """Test handler that tracks file reconstruction from interleaved blocks."""

    def __init__(self) -> None:
        """Initialize the handler."""
        self.file_segments: dict[str, list[QuickBlockTransferSegment]] = {}
        self.completed_files: list[str] = []
        self.received_order: list[str] = []

    async def handle_segment(self, segment: QuickBlockTransferSegment) -> None:
        """Handle received data segment.

        Args:
            segment: Received QuickBlockTransferSegment

        """
        # Track order of receipt
        self.received_order.append(f"{segment.filename}:{segment.block_number}")

        # Group segments by file key
        file_key = segment.key
        if file_key not in self.file_segments:
            self.file_segments[file_key] = []

        self.file_segments[file_key].append(segment)

        # Check if we have all segments for this file
        segments = self.file_segments[file_key]
        if len(segments) == segment.total_blocks:
            await self._reconstruct_file(file_key, segments)

    async def _reconstruct_file(
        self, file_key: str, segments: list[QuickBlockTransferSegment]
    ) -> None:
        """Reconstruct complete file from segments.

        Args:
            file_key: Unique file identifier
            segments: List of all segments for the file

        """
        # Sort segments by block number
        segments.sort(key=lambda s: s.block_number)

        # Verify all blocks are present
        for i, segment in enumerate(segments, 1):
            if segment.block_number != i:
                msg = f"Missing block {i} for file {segment.filename}"
                raise ValueError(msg)

        # Combine content
        complete_data = b"".join(segment.content for segment in segments)

        # Get filename from first segment
        filename = segments[0].filename
        self.completed_files.append(filename)

        print(
            f"✓ Reconstructed: {filename} ({len(complete_data)} bytes from {len(segments)} blocks)"
        )

        # Clean up segments from memory
        del self.file_segments[file_key]


def create_test_segment(
    filename: str,
    block_number: int,
    total_blocks: int,
    content: bytes,
    timestamp: datetime,
) -> QuickBlockTransferSegment:
    """Create a test segment with specified parameters.

    Args:
        filename: Name of the file
        block_number: Block number (1-based)
        total_blocks: Total number of blocks in file
        content: Block content
        timestamp: File timestamp for generating unique key

    Returns:
        QuickBlockTransferSegment for testing

    """
    return QuickBlockTransferSegment(
        filename=filename,
        block_number=block_number,
        total_blocks=total_blocks,
        content=content,
        checksum=sum(content) & 0xFFFF,
        length=len(content),
        timestamp=timestamp,
    )


async def test_interleaved_blocks() -> None:
    """Test that interleaved blocks from multiple files are handled correctly."""
    print("Testing interleaved block handling...")

    handler = InterleavedBlockHandler()

    # Create timestamps for different files (to ensure unique keys)
    time1 = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
    time2 = datetime(2024, 1, 1, 12, 0, 1, tzinfo=UTC)
    time3 = datetime(2024, 1, 1, 12, 0, 2, tzinfo=UTC)

    # Create segments for three different files with interleaved delivery
    segments = [
        # Low priority file starts
        create_test_segment("low_priority.txt", 1, 4, b"Low-1: ", time1),
        create_test_segment("low_priority.txt", 2, 4, b"Low-2: ", time1),
        # High priority file interrupts
        create_test_segment("high_priority.txt", 1, 2, b"High-1: URGENT", time2),
        create_test_segment("high_priority.txt", 2, 2, b"High-2: ALERT", time2),
        # Medium priority file starts
        create_test_segment("medium_priority.txt", 1, 3, b"Med-1: ", time3),
        # Low priority continues
        create_test_segment("low_priority.txt", 3, 4, b"Low-3: ", time1),
        # Medium priority continues
        create_test_segment("medium_priority.txt", 2, 3, b"Med-2: ", time3),
        create_test_segment("medium_priority.txt", 3, 3, b"Med-3: ", time3),
        # Low priority finishes
        create_test_segment("low_priority.txt", 4, 4, b"Low-4: END", time1),
    ]

    # Process segments in interleaved order
    for segment in segments:
        await handler.handle_segment(segment)

    # Verify all files were completed
    expected_files = {"high_priority.txt", "medium_priority.txt", "low_priority.txt"}
    completed_files = set(handler.completed_files)

    assert completed_files == expected_files, f"Expected {expected_files}, got {completed_files}"

    # Verify that high priority file completed first despite starting later
    assert handler.completed_files[0] == "high_priority.txt", (
        "High priority file should complete first"
    )

    # Verify the interleaved order was preserved
    expected_order = [
        "low_priority.txt:1",
        "low_priority.txt:2",
        "high_priority.txt:1",
        "high_priority.txt:2",
        "medium_priority.txt:1",
        "low_priority.txt:3",
        "medium_priority.txt:2",
        "medium_priority.txt:3",
        "low_priority.txt:4",
    ]

    assert handler.received_order == expected_order, (
        f"Unexpected receive order: {handler.received_order}"
    )

    print("✓ Interleaved blocks handled correctly")
    print(f"✓ Files completed in order: {' -> '.join(handler.completed_files)}")
    print(f"✓ Received {len(segments)} blocks in interleaved order")


async def test_same_filename_different_timestamps() -> None:
    """Test that files with same name but different timestamps are handled separately."""
    print("\nTesting same filename with different timestamps...")

    handler = InterleavedBlockHandler()

    # Create two files with same name but different timestamps
    time1 = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
    time2 = datetime(2024, 1, 1, 12, 0, 5, tzinfo=UTC)

    segments = [
        # First version of file
        create_test_segment("weather.txt", 1, 2, b"Version 1: Old data", time1),
        # Second version starts (interleaved)
        create_test_segment("weather.txt", 1, 3, b"Version 2: New ", time2),
        # First version continues
        create_test_segment("weather.txt", 2, 2, b" complete", time1),
        # Second version continues
        create_test_segment("weather.txt", 2, 3, b"updated ", time2),
        create_test_segment("weather.txt", 3, 3, b"data", time2),
    ]

    # Process segments
    for segment in segments:
        await handler.handle_segment(segment)

    # Should have completed both files (treated as separate due to different timestamps)
    assert len(handler.completed_files) == 2, (
        f"Expected 2 files, got {len(handler.completed_files)}"
    )
    assert all(filename == "weather.txt" for filename in handler.completed_files), "Wrong filenames"

    print("✓ Same filename with different timestamps handled as separate files")


async def test_out_of_order_blocks() -> None:
    """Test that blocks arriving out of order within a file are handled correctly."""
    print("\nTesting out-of-order blocks...")

    handler = InterleavedBlockHandler()

    # Create segments for a single file arriving out of order
    timestamp = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)

    segments = [
        create_test_segment("file.txt", 3, 4, b"Third ", timestamp),
        create_test_segment("file.txt", 1, 4, b"First ", timestamp),
        create_test_segment("file.txt", 4, 4, b"Fourth", timestamp),
        create_test_segment("file.txt", 2, 4, b"Second ", timestamp),
    ]

    # Process segments in out-of-order sequence
    for segment in segments:
        await handler.handle_segment(segment)

    # Verify file was completed correctly
    assert len(handler.completed_files) == 1, "Should have completed exactly one file"
    assert handler.completed_files[0] == "file.txt", "Wrong filename"

    print("✓ Out-of-order blocks within a file handled correctly")


async def test_unique_keys() -> None:
    """Test that segment keys properly distinguish between different files."""
    print("\nTesting segment key uniqueness...")

    # Create segments with same filename but different timestamps
    time1 = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
    time2 = datetime(2024, 1, 1, 12, 0, 1, tzinfo=UTC)

    segment1 = create_test_segment("test.txt", 1, 1, b"Content 1", time1)
    segment2 = create_test_segment("test.txt", 1, 1, b"Content 2", time2)

    # Keys should be different due to different timestamps
    assert segment1.key != segment2.key, (
        f"Keys should be different: {segment1.key} vs {segment2.key}"
    )

    # Keys should contain filename and timestamp
    assert "test.txt" in segment1.key, "Key should contain filename"
    assert "test.txt" in segment2.key, "Key should contain filename"

    print("✓ Segment keys are unique and properly formed")


async def main() -> None:
    """Run all interleaved block tests."""
    print("ByteBlaster Interleaved Block Test Suite")
    print("=" * 50)

    try:
        await test_interleaved_blocks()
        await test_same_filename_different_timestamps()
        await test_out_of_order_blocks()
        await test_unique_keys()

        print("=" * 50)
        print("✓ All interleaved block tests passed!")
        print(
            "\nVerification complete: ByteBlaster can handle interleaved blocks from multiple files."
        )
        print("This allows higher priority files to interrupt lower priority transfers.")

    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


def run_tests() -> None:
    """Run the tests using asyncio."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTests interrupted by user")
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run_tests()
