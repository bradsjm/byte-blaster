"""Handler for processing weather data segments from ByteBlaster."""

import logging
from pathlib import Path

from byteblaster import QuickBlockTransferSegment

logger = logging.getLogger(__name__)


class WeatherDataHandler:
    """Example handler for processing weather data segments."""

    def __init__(self, output_dir: str = "weather_data") -> None:
        """Initialize handler with output directory.

        Args:
            output_dir: Directory to save received files

        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.file_segments: dict[str, list[QuickBlockTransferSegment]] = {}

    async def handle_segment(self, segment: QuickBlockTransferSegment) -> None:
        """Handle received data segment.

        Args:
            segment: Received QuickBlockTransferSegment

        """
        # Skip FILLFILE.TXT - it's filler data when no real data is being transmitted
        if segment.filename == "FILLFILE.TXT":
            return

        logger.debug(
            f"Received: {segment.filename} block {segment.block_number}/{segment.total_blocks}"
        )

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

        # Combine content
        complete_data = b"".join(segment.content for segment in segments)

        # Get filename from first segment
        filename = segments[0].filename
        output_path = self.output_dir / filename

        # Ensure parent directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Write file
        try:
            output_path.write_bytes(complete_data)
            logger.info(f"✓ Saved complete file: {output_path} ({len(complete_data)} bytes)")
        except OSError as e:
            logger.error(f"✗ Failed to save {output_path}: {e}")

        # Clean up segments from memory
        del self.file_segments[file_key]
