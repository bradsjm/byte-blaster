"""Protocol decoder implementing the ByteBlaster state machine.

This module contains the ProtocolDecoder class that implements the complete
ByteBlaster protocol state machine for parsing incoming data streams into
protocol frames and data segments.
"""

import logging
import re
from collections.abc import Callable
from datetime import UTC, datetime
from enum import Enum

from byteblaster.protocol.models import (
    ByteBlasterServerList,
    DataBlockFrame,
    ProtocolFrame,
    QBTSegment,
    ServerListFrame,
)
from byteblaster.utils.crypto import XorBuffer, decompress_zlib, verify_checksum

logger = logging.getLogger(__name__)


class DecoderState(Enum):
    """Enumeration of protocol decoder states in the ByteBlaster state machine.

    This enumeration defines all possible states that the ProtocolDecoder can be in
    during the processing of incoming data streams. The decoder follows a strict
    state machine pattern to parse the ByteBlaster protocol, transitioning between
    these states based on the data content and parsing progress.

    The state transitions follow this general flow:
    RESYNC -> START_FRAME -> FRAME_TYPE -> (SERVER_LIST | BLOCK_HEADER) ->
    BLOCK_BODY -> VALIDATE -> START_FRAME (repeating)

    States:
        RESYNC: Searching for frame synchronization bytes (6 consecutive 0xFF)
        START_FRAME: Skipping null bytes to find the start of frame content
        FRAME_TYPE: Analyzing header bytes to determine frame type
        SERVER_LIST: Processing server list frame content
        BLOCK_HEADER: Parsing data block header (80 bytes with protocol metadata)
        BLOCK_BODY: Reading data block body content
        VALIDATE: Performing checksum validation and emitting completed frames
    """

    RESYNC = "RESYNC"
    START_FRAME = "START_FRAME"
    FRAME_TYPE = "FRAME_TYPE"
    SERVER_LIST = "SERVER_LIST"
    BLOCK_HEADER = "BLOCK_HEADER"
    BLOCK_BODY = "BLOCK_BODY"
    VALIDATE = "VALIDATE"


type FrameHandler = Callable[[ProtocolFrame], None]


class ProtocolDecoder:
    """Production-grade ByteBlaster protocol decoder implementing a robust state machine.

    This class provides a complete implementation of the ByteBlaster protocol decoder,
    designed to parse continuous byte streams from network connections into structured
    protocol frames. The decoder handles both V1 and V2 protocol variants with full
    error recovery, checksum validation, and data decompression capabilities.

    Key Features:
    - State machine-based parsing for reliable stream processing
    - Support for both V1 (fixed 1024-byte blocks) and V2 (variable-length, compressed) protocols
    - Automatic frame synchronization and error recovery
    - XOR-decoded buffer management with efficient memory usage
    - Comprehensive checksum validation with protocol-specific algorithms
    - Zlib decompression for V2 compressed data blocks
    - Server list frame parsing and data block frame processing
    - Configurable frame handlers for downstream processing integration

    Protocol Structure:
    The ByteBlaster protocol transmits data in frames, each beginning with 6 sync bytes
    (0xFF when encoded), followed by frame content. Data block frames contain an 80-byte
    ASCII header with metadata, followed by the actual data payload. Server list frames
    contain ASCII text with available server information.

    Error Handling:
    The decoder implements robust error recovery, automatically resyncing on corrupt
    data, validating checksums, and logging detailed diagnostic information. Invalid
    frames are logged but do not crash the decoder, ensuring continuous operation.

    Thread Safety:
    This class is not thread-safe. Each connection should use its own decoder instance.
    """

    # Protocol constants
    FRAME_SYNC_BYTES = 6
    HEADER_SIZE = 80
    V1_BODY_SIZE = 1024
    MAX_V2_BODY_SIZE = 1024

    # Header regex for parsing (matches both V1 and V2)
    HEADER_REGEX = re.compile(
        rb"^/PF(?P<PF>[A-Za-z0-9\-._]+)\s*/PN\s*(?P<PN>[0-9]+)\s*"
        rb"/PT\s*(?P<PT>[0-9]+)\s*/CS\s*(?P<CS>[0-9]+)\s*"
        rb"/FD(?P<FD>[0-9/: ]+[AP]M)\s*(/DL(?P<DL>[0-9]+)\s*)?\r\n$",
    )

    # Header date format
    HEADER_DATE_FORMAT = "%m/%d/%Y %I:%M:%S %p"

    def __init__(self, frame_handler: FrameHandler | None = None) -> None:
        """Initialize the ByteBlaster protocol decoder with default state and buffers.

        Sets up the decoder in the initial RESYNC state with an empty XOR buffer and
        prepares the internal state machine for processing incoming data. The decoder
        begins in resynchronization mode, scanning for frame sync patterns to establish
        proper frame boundaries.

        The initialization creates:
        - Internal XOR buffer for decoded data storage and manipulation
        - State machine starting in RESYNC mode for frame synchronization
        - Optional frame handler callback for processing completed frames
        - Storage for current segment metadata during multi-state processing

        Args:
            frame_handler: Optional callback function that receives completed ProtocolFrame
                objects. This handler is called synchronously when frames are fully
                decoded and validated. If None, frames are processed but not emitted.

        """
        self._state = DecoderState.RESYNC
        self._buffer = XorBuffer()
        self._current_segment: QBTSegment | None = None
        self._frame_handler = frame_handler
        self._remote_address = ""

    @property
    def state(self) -> DecoderState:
        """Get the current state of the protocol decoder state machine.

        Returns the current processing state, which indicates what type of data
        the decoder is expecting next and how it will process incoming bytes.
        This property is useful for monitoring decoder progress and debugging
        parsing issues.

        Returns:
            Current DecoderState enumeration value representing the active state
            in the parsing state machine.

        """
        return self._state

    def set_remote_address(self, address: str) -> None:
        """Set the remote server address for enhanced logging and segment tracking.

        Configures the remote address that will be included in decoded segment metadata
        and used for enhanced logging output. This address helps track the source of
        data blocks when processing connections from multiple servers or when debugging
        connection-specific issues.

        The remote address is embedded in QBTSegment objects as the 'source' field,
        enabling downstream processing to identify the origin of each data block.
        This is particularly useful in multi-server environments or when aggregating
        data from multiple ByteBlaster sources.

        Args:
            address: The remote server address, typically in "host:port" format or
                as an IP address. This string is stored as-is and included in all
                subsequent segment metadata.

        """
        self._remote_address = address

    def set_frame_handler(self, handler: FrameHandler) -> None:
        """Set or update the frame handler callback for processing completed frames.

        Configures the callback function that will receive all successfully decoded
        and validated protocol frames. The handler is called synchronously during
        frame processing, so implementations should be efficient and avoid blocking
        operations to prevent decoder stalls.

        The frame handler receives ProtocolFrame objects, which can be either
        DataBlockFrame or ServerListFrame instances. Handlers should implement
        appropriate type checking and processing logic for each frame type.

        Error Handling:
        If the frame handler raises an exception, it is logged but does not affect
        decoder operation. The decoder continues processing subsequent frames to
        maintain stream continuity.

        Args:
            handler: Callable that accepts a ProtocolFrame object. The handler
                is responsible for any downstream processing, storage, or forwarding
                of the decoded frame data.

        """
        self._frame_handler = handler

    def feed(self, data: bytes) -> None:
        """Feed raw network data to the decoder for incremental processing.

        Accepts raw bytes from network connections and processes them through the
        protocol state machine. This method is designed for streaming operation,
        where data arrives in arbitrary-sized chunks from network I/O operations.
        The decoder maintains internal buffering to handle partial frames and
        incomplete data sequences.

        Processing Flow:
        1. Appends incoming data to the internal XOR buffer
        2. Triggers state machine processing to parse buffered content
        3. Automatically handles frame boundaries and state transitions
        4. Emits completed frames via the configured frame handler

        The method processes all available buffered data in the current call,
        potentially completing multiple frames if sufficient data is available.
        Partial frames remain buffered for completion when additional data arrives.

        Error Recovery:
        If processing encounters invalid data or corruption, the decoder automatically
        transitions to resynchronization mode to recover frame boundaries without
        losing subsequent valid data.

        Args:
            data: Raw bytes received from network connection. Can be any size from
                single bytes to large buffers. The decoder handles arbitrary chunk
                sizes efficiently through internal buffering.

        """
        self._buffer.append(data)
        self._process_buffer()

    def reset(self) -> None:
        """Reset the decoder to initial state, clearing all buffers and progress.

        Performs a complete reset of the decoder state machine, returning it to the
        initial RESYNC state and clearing all internal buffers and temporary data.
        This operation is typically used after encountering unrecoverable errors
        or when starting processing of a new data stream.

        Reset Operations:
        - Sets state machine to RESYNC for frame synchronization
        - Clears the internal XOR buffer, discarding any buffered data
        - Resets current segment processing state
        - Logs the reset operation for debugging purposes

        This method provides a clean slate for processing new data streams and
        ensures no state contamination between different connections or after
        error conditions that require full recovery.
        """
        self._state = DecoderState.RESYNC
        self._buffer.clear()
        self._current_segment = None
        logger.debug("Decoder state reset")

    def _process_buffer(self) -> None:
        """Process buffer according to current state."""
        while True:
            if not self._process_current_state():
                break

    def _process_current_state(self) -> bool:  # noqa: PLR0911
        """Process current state and return True if should continue."""
        if self._state == DecoderState.RESYNC:
            return self._handle_resync()
        if self._state == DecoderState.START_FRAME:
            return self._handle_start_frame()
        if self._state == DecoderState.FRAME_TYPE:
            return self._handle_frame_type()
        if self._state == DecoderState.SERVER_LIST:
            return self._handle_server_list()
        if self._state == DecoderState.BLOCK_HEADER:
            return self._handle_block_header()
        if self._state == DecoderState.BLOCK_BODY:
            return self._handle_block_body()
        if self._state == DecoderState.VALIDATE:
            return self._handle_validate()

        msg = f"Unknown decoder state: {self._state}"
        raise RuntimeError(msg)

    def _handle_resync(self) -> bool:
        """Handle RESYNC state."""
        if not self._synchronize_frame():
            return False
        self._state = DecoderState.START_FRAME
        return True

    def _handle_start_frame(self) -> bool:
        """Handle START_FRAME state."""
        if not self._skip_null_bytes():
            return False
        self._state = DecoderState.FRAME_TYPE
        return True

    def _handle_frame_type(self) -> bool:
        """Handle FRAME_TYPE state."""
        return self._determine_frame_type()

    def _handle_server_list(self) -> bool:
        """Handle SERVER_LIST state."""
        if not self._process_server_list():
            return False
        self._state = DecoderState.START_FRAME
        return True

    def _handle_block_header(self) -> bool:
        """Handle BLOCK_HEADER state."""
        if not self._process_block_header():
            return False
        self._state = DecoderState.BLOCK_BODY
        return True

    def _handle_block_body(self) -> bool:
        """Handle BLOCK_BODY state."""
        if not self._process_block_body():
            return False
        self._state = DecoderState.VALIDATE
        return True

    def _handle_validate(self) -> bool:
        """Handle VALIDATE state."""
        if not self._validate_segment():
            return False
        self._state = DecoderState.START_FRAME
        return True

    def _synchronize_frame(self) -> bool:
        """Look for frame synchronization (6 consecutive 0xFF bytes).

        Returns:
            True if synchronization found, False if need more data

        """
        if self._buffer.available() < self.FRAME_SYNC_BYTES:
            return False

        # Look for 6 consecutive null bytes when decoded
        for start_pos in range(self._buffer.available() - self.FRAME_SYNC_BYTES + 1):
            sync_data = self._buffer.peek(self.FRAME_SYNC_BYTES, start_pos)
            if sync_data == b"\x00" * self.FRAME_SYNC_BYTES:
                # Found sync pattern, skip to just after it
                self._buffer.skip(start_pos + self.FRAME_SYNC_BYTES)
                logger.debug("Frame synchronization found at position %d", start_pos)
                return True

        # No sync found, keep the last 5 bytes in case sync spans chunks
        if self._buffer.available() > self.FRAME_SYNC_BYTES:
            self._buffer.skip(self._buffer.available() - self.FRAME_SYNC_BYTES + 1)

        logger.debug("Frame sync not found")
        return False

    def _skip_null_bytes(self) -> bool:
        """Skip null bytes to find start of frame.

        Returns:
            True if non-null byte found, False if need more data

        """
        while self._buffer.available() > 0:
            byte_data = self._buffer.peek(1)
            if not byte_data:
                return False

            if byte_data[0] != 0x00:  # Found non-null byte
                return True

            self._buffer.skip(1)

        return False

    def _determine_frame_type(self) -> bool:
        """Determine frame type by examining header.

        Returns:
            True if frame type determined, False if need more data

        """
        # Need at least 10 bytes to check frame type
        if self._buffer.available() < 10:
            return False

        # Peek at first 20 bytes to determine type
        header_start = self._buffer.peek(min(20, self._buffer.available()))

        if self._is_data_block_header(header_start):
            self._state = DecoderState.BLOCK_HEADER
            logger.debug("Detected data block frame")
            return True

        if self._is_server_list_header(header_start):
            self._state = DecoderState.SERVER_LIST
            logger.debug("Detected server list frame")
            return True

        # Unknown frame type
        header_str = header_start.decode("ascii", errors="replace")
        logger.warning("Unknown frame type, header starts: %r", header_str)
        # Skip this byte and try to resync
        self._buffer.skip(1)
        self._state = DecoderState.RESYNC
        return True

    @staticmethod
    def _is_data_block_header(header_data: bytes) -> bool:
        """Check if header indicates a data block.

        Args:
            header_data: Decoded header bytes

        Returns:
            True if data block header detected

        """
        return (
            len(header_data) >= 3
            and header_data[0] == ord("/")
            and header_data[1] == ord("P")
            and header_data[2] == ord("F")
        )

    @staticmethod
    def _is_server_list_header(header_data: bytes) -> bool:
        """Check if header indicates a server list.

        Args:
            header_data: Decoded header bytes

        Returns:
            True if server list header detected

        """
        return (
            len(header_data) >= 3
            and header_data[0] == ord("/")
            and header_data[1] == ord("S")
            and header_data[2] == ord("e")
        )

    def _process_server_list(self) -> bool:
        """Process server list frame.

        Returns:
            True if frame processed, False if need more data

        """
        # Read until null terminator or end marker
        content = self._read_null_terminated_string()
        if content is None:
            # Look for end pattern if no null terminator found
            available_data = self._buffer.peek(self._buffer.available())
            end_pattern = b"\\SatServers\\\x00"
            if end_pattern in available_data:
                end_pos = available_data.find(end_pattern) + len(end_pattern)
                content = self._buffer.read(end_pos - 1).decode("ascii", errors="replace")
                self._buffer.skip(1)  # Skip final null
            else:
                return False

        try:
            server_list = ByteBlasterServerList.from_server_list_frame(content)
            frame = ServerListFrame(
                content=content.encode("ascii"),
                server_list=server_list,
            )
            self._emit_frame(frame)
            logger.info("Processed server list with %d servers", len(server_list))

        except ValueError:
            logger.exception("Failed to parse server list: %r", content[:100])

        return True

    def _process_block_header(self) -> bool:
        """Process data block header.

        Returns:
            True if header processed, False if need more data

        """
        if self._buffer.available() < self.HEADER_SIZE:
            return False

        header_data = self._buffer.read(self.HEADER_SIZE)
        header_str = header_data.decode("ascii", errors="replace")

        logger.debug("Processing header: %s", header_str.strip())

        # Parse header with regex
        header_bytes = header_str.encode("ascii")
        match = self.HEADER_REGEX.match(header_bytes)

        if not match:
            msg = f"Invalid header format: {header_str}"
            raise ValueError(msg)

        self._current_segment = self._parse_header_groups(match, header_str)
        return True

    def _parse_header_groups(self, match: re.Match[bytes], header_str: str) -> QBTSegment:
        """Parse regex match groups into segment object.

        Args:
            match: Regex match object
            header_str: Original header string

        Returns:
            QBTSegment with parsed header data

        """
        groups = match.groupdict()

        # Parse basic fields
        filename = groups["PF"].decode("ascii")
        block_number = int(groups["PN"])
        total_blocks = int(groups["PT"])
        checksum = int(groups["CS"])

        # Parse timestamp
        timestamp = datetime.now(UTC)
        date_str = ""
        try:
            date_str = groups["FD"].decode("ascii")
            parsed_time = datetime.strptime(date_str, self.HEADER_DATE_FORMAT).astimezone(UTC)
            timestamp = parsed_time.replace(tzinfo=UTC)
        except (ValueError, KeyError) as e:
            logger.warning("Failed to parse header date '%s': %s", date_str, e)

        # Determine version and length
        version = 1
        length = self.V1_BODY_SIZE

        if groups.get("DL"):
            version = 2
            length = int(groups["DL"])
            if length <= 0 or length > self.MAX_V2_BODY_SIZE:
                msg = f"Invalid V2 length: {length} (must be 1-{self.MAX_V2_BODY_SIZE})"
                raise ValueError(msg)

        return QBTSegment(
            filename=filename,
            block_number=block_number,
            total_blocks=total_blocks,
            checksum=checksum,
            length=length,
            version=version,
            timestamp=timestamp,
            header=header_str,
            source=self._remote_address,
        )

    def _process_block_body(self) -> bool:
        """Process data block body.

        Returns:
            True if body processed, False if need more data

        """
        if not self._current_segment:
            msg = "No current segment for body processing"
            raise RuntimeError(msg)

        if self._buffer.available() < self._current_segment.length:
            return False

        # Read body data
        body_data = self._buffer.read(self._current_segment.length)

        # Decompress if V2
        if self._current_segment.version == 2:
            try:
                body_data = decompress_zlib(body_data)
            except Exception:
                logger.exception("Failed to decompress V2 data")
                raise

        self._current_segment.content = body_data
        return True

    def _validate_segment(self) -> bool:
        """Validate current segment and emit if valid.

        Returns:
            True (always continues processing)

        """
        if not self._current_segment:
            msg = "No current segment for validation"
            raise RuntimeError(msg)

        segment = self._current_segment
        self._current_segment = None

        # Validate block numbers
        if segment.total_blocks <= 0 or segment.block_number <= 0:
            logger.error("Invalid block numbers: %d/%d", segment.block_number, segment.total_blocks)
            return True

        if segment.block_number > segment.total_blocks:
            logger.error(
                "Block number exceeds total: %d > %d",
                segment.block_number,
                segment.total_blocks,
            )
            return True

        # Skip FILLFILE.TXT - it's filler when no data is being transmitted
        if segment.filename == "FILLFILE.TXT":
            logger.debug("Skipping FILLFILE.TXT (filler data)")
            return True

        # Handle compression and checksum validation based on protocol version
        checksum_valid = self._validate_segment_checksum(segment)

        # After validation, trim padding from text files.
        # The last block of a transmission may not be fully populated with content,
        # and for text files, this padding should be removed. The protocol specifies
        # null padding, but some sources may use whitespace.
        if segment.filename.upper().endswith((".TXT", ".WMO")):
            segment.content = segment.content.rstrip(b"\x00 \t\r\n")

        # Emit segment regardless of checksum status for data collection
        frame = DataBlockFrame(
            content=segment.content,
            segment=segment,
        )
        self._emit_frame(frame)

        logger.debug(
            "Processed segment: %s (checksum %s)",
            segment,
            "valid" if checksum_valid else "invalid",
        )
        return True

    def _validate_segment_checksum(self, segment: QBTSegment) -> bool:
        """Validate segment checksum based on protocol version.

        Args:
            segment: Segment to validate

        Returns:
            True if checksum is valid

        """
        if segment.version == 1:
            return self._validate_v1_checksum(segment)
        if segment.version == 2:
            return self._validate_v2_checksum(segment)
        return False

    def _validate_v1_checksum(self, segment: QBTSegment) -> bool:
        """Validate V1 protocol checksum.

        Args:
            segment: Segment to validate

        Returns:
            True if checksum is valid

        """
        # V1 checksum from the header can be a 32-bit value; it must be masked to
        # 16 bits for correct validation against the calculated 16-bit checksum.
        expected_checksum = segment.checksum & 0xFFFF
        checksum_valid = verify_checksum(segment.content, expected_checksum)
        if not checksum_valid:
            logger.warning(
                "V1 checksum validation failed for %s: expected %d (from header %d), calculated %d (length: %d)",
                segment.filename,
                expected_checksum,
                segment.checksum,
                sum(segment.content) & 0xFFFF,
                len(segment.content),
            )
        return checksum_valid

    def _validate_v2_checksum(self, segment: QBTSegment) -> bool:
        """Validate V2 protocol checksum with compression support.

        Args:
            segment: Segment to validate

        Returns:
            True if checksum is valid

        """
        # Check if data is compressed (starts with zlib header)
        if self._is_compressed_data(segment.content):
            return self._validate_compressed_data(segment)
        return self._validate_uncompressed_v2_data(segment)

    def _is_compressed_data(self, content: bytes) -> bool:
        """Check if data appears to be zlib compressed.

        Args:
            content: Data to check

        Returns:
            True if data appears compressed

        """
        return len(content) >= 2 and content[:2] in (b"\x78\x9c", b"\x78\xda", b"\x78\x01")

    def _validate_compressed_data(self, segment: QBTSegment) -> bool:
        """Validate compressed V2 data.

        Args:
            segment: Segment with compressed data

        Returns:
            True if checksum is valid

        """
        try:
            import zlib

            uncompressed_data = zlib.decompress(segment.content)

            # Checksum should be calculated on uncompressed data
            if verify_checksum(uncompressed_data, segment.checksum):
                segment.content = uncompressed_data
                logger.debug(
                    "V2 compressed data decompressed and validated for %s",
                    segment.filename,
                )
                return True

            logger.warning(
                "V2 compressed checksum validation failed for %s: expected %d, "
                "calculated %d (uncompressed length: %d)",
                segment.filename,
                segment.checksum,
                sum(uncompressed_data) & 0xFFFF,
                len(uncompressed_data),
            )

        except (OSError, ValueError) as e:
            logger.warning("V2 decompression failed for %s: %s", segment.filename, e)
            # Fall back to treating as uncompressed
            return verify_checksum(segment.content, segment.checksum)

        return False

    def _validate_uncompressed_v2_data(self, segment: QBTSegment) -> bool:
        """Validate uncompressed V2 data.

        Args:
            segment: Segment with uncompressed data

        Returns:
            True if checksum is valid

        """
        checksum_valid = verify_checksum(segment.content, segment.checksum)
        if not checksum_valid:
            logger.warning(
                "V2 uncompressed checksum validation failed for %s: expected %d, "
                "calculated %d (length: %d)",
                segment.filename,
                segment.checksum,
                sum(segment.content) & 0xFFFF,
                len(segment.content),
            )
        return checksum_valid

    def _read_null_terminated_string(self) -> str | None:
        """Read null-terminated string from buffer.

        Returns:
            Decoded string or None if null terminator not found

        """
        # Scan for null terminator
        for i in range(self._buffer.available()):
            byte_data = self._buffer.peek(1, i)
            if byte_data and byte_data[0] == 0x00:
                # Found terminator, read up to it
                string_data = self._buffer.read(i)
                self._buffer.skip(1)  # Skip the null terminator
                return string_data.decode("ascii", errors="replace")

        return None

    def _emit_frame(self, frame: ProtocolFrame) -> None:
        """Emit frame to handler if available.

        Args:
            frame: Frame to emit

        """
        if self._frame_handler:
            try:
                self._frame_handler(frame)
            except Exception:
                logger.exception("Frame handler error")
