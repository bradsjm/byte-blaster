"""Handler for processing weather data segments from ByteBlaster."""

import logging
from pathlib import Path

from byteblaster import QuickBlockTransferSegment

logger = logging.getLogger(__name__)


class WeatherDataHandler:
    """Handler for processing and reconstructing weather data from ByteBlaster segments.

    This handler manages the complete lifecycle of weather data transmission through
    the ByteBlaster protocol. It receives individual QuickBlockTransferSegment objects,
    groups them by file identifier, and reconstructs complete weather data files when
    all segments for a given file have been received.

    The handler automatically filters out FILLFILE.TXT transmissions, which are used
    as filler data when no real weather information is being broadcast. It maintains
    an in-memory buffer of partial file segments and performs file reconstruction
    when segment sets are complete, writing the resulting files to a configurable
    output directory with proper error handling and logging.

    Key responsibilities include segment grouping, file reconstruction, directory
    management, and memory cleanup to prevent resource leaks during long-running
    operations.
    """

    def __init__(self, output_dir: str = "weather_data") -> None:
        """Initialize the weather data handler with file output configuration.

        Creates the output directory structure and initializes internal data structures
        for tracking partial file segments. The handler sets up a file segment buffer
        that groups incoming segments by their unique file key, enabling proper
        reconstruction of multi-segment files.

        The output directory is created immediately if it doesn't exist, ensuring
        that file writes will succeed when complete files are reconstructed. The
        internal segment tracking dictionary is initialized empty and will be
        populated as segments arrive.

        Args:
            output_dir: Directory path where reconstructed weather data files will be saved.
                       Directory will be created if it doesn't exist.

        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.file_segments: dict[str, list[QuickBlockTransferSegment]] = {}

    async def handle_segment(self, segment: QuickBlockTransferSegment) -> None:
        """Process an incoming weather data segment and trigger reconstruction when complete.

        This method implements the core segment processing logic for the ByteBlaster
        protocol. It filters out FILLFILE.TXT segments (which are filler data), groups
        segments by their unique file key, and monitors for file completion.

        The processing flow includes:
        1. Filtering out FILLFILE.TXT segments to ignore filler transmissions
        2. Grouping segments by file key to handle concurrent multi-file transfers
        3. Adding the segment to the appropriate file's segment collection
        4. Checking if all segments for a file have been received
        5. Triggering file reconstruction when the segment count matches total_blocks

        Debug logging tracks segment reception progress, and file reconstruction is
        automatically initiated when complete segment sets are detected. The method
        handles concurrent file transfers by maintaining separate segment collections
        for each unique file key.

        Args:
            segment: The QuickBlockTransferSegment containing file data, metadata,
                    and position information within the complete file.

        """
        # Skip FILLFILE.TXT - it's filler data when no real data is being transmitted
        if segment.filename == "FILLFILE.TXT":
            return

        logger.debug(
            "Received: %s block %d/%d",
            segment.filename,
            segment.block_number,
            segment.total_blocks,
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
        """Reconstruct a complete file from its segments and write to disk.

        This method handles the final phase of file reconstruction by sorting segments
        in the correct order, combining their content, and writing the complete file
        to the output directory. It includes comprehensive error handling for file
        system operations and automatic cleanup of memory resources.

        The reconstruction process includes:
        1. Sorting segments by block number to ensure correct file ordering
        2. Concatenating segment content in sequence to rebuild the original file
        3. Creating necessary parent directories for the output path
        4. Writing the complete file data with proper error handling
        5. Logging success/failure status with file size information
        6. Cleaning up the segment collection from memory to prevent leaks

        File system errors during write operations are caught and logged without
        crashing the handler, allowing processing to continue for other files.
        Memory cleanup ensures that completed files don't consume resources
        during long-running operations.

        Args:
            file_key: Unique identifier for the file being reconstructed.
            segments: Complete list of segments containing all blocks for the file.

        Raises:
            OSError: File system errors during directory creation or file writing
                    are caught and logged rather than propagated.

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
            logger.info("✓ Saved complete file: %s (%d bytes)", output_path, len(complete_data))
        except OSError:
            logger.exception("✗ Failed to save %s", output_path)

        # Clean up segments from memory
        del self.file_segments[file_key]
