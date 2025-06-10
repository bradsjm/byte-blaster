# pyright: reportPrivateUsage=false
"""Comprehensive tests for the ByteBlaster protocol decoder module.

This module provides thorough test coverage for the ProtocolDecoder class and
DecoderState enum, testing all state transitions, frame processing, error
handling, and edge cases in the ByteBlaster protocol implementation.
"""

import re
from datetime import UTC, datetime
from unittest.mock import Mock, patch

import pytest

from byteblaster.protocol.decoder import DecoderState, ProtocolDecoder
from byteblaster.protocol.models import (
    ByteBlasterServerList,
    DataBlockFrame,
    QBTSegment,
    ServerListFrame,
)
from byteblaster.utils.crypto import xor_encode


class TestDecoderState:
    """Test cases for the DecoderState enumeration."""

    def test_decoder_state_when_all_states_defined_then_has_expected_values(self) -> None:
        """Test that all decoder states are properly defined with expected string values."""
        assert DecoderState.RESYNC.value == "RESYNC"
        assert DecoderState.START_FRAME.value == "START_FRAME"
        assert DecoderState.FRAME_TYPE.value == "FRAME_TYPE"
        assert DecoderState.SERVER_LIST.value == "SERVER_LIST"
        assert DecoderState.BLOCK_HEADER.value == "BLOCK_HEADER"
        assert DecoderState.BLOCK_BODY.value == "BLOCK_BODY"
        assert DecoderState.VALIDATE.value == "VALIDATE"

    def test_decoder_state_when_compared_then_equality_works(self) -> None:
        """Test that decoder state comparisons work correctly."""
        assert DecoderState.RESYNC == DecoderState.RESYNC
        assert DecoderState.RESYNC != DecoderState.START_FRAME

    def test_decoder_state_when_used_in_set_then_hashable(self) -> None:
        """Test that decoder states can be used in sets (are hashable)."""
        states = {DecoderState.RESYNC, DecoderState.START_FRAME, DecoderState.RESYNC}
        assert len(states) == 2
        assert DecoderState.RESYNC in states
        assert DecoderState.START_FRAME in states


class TestProtocolDecoder:
    """Test cases for the ProtocolDecoder class."""

    def test_protocol_decoder_when_default_initialization_then_has_expected_defaults(
        self,
    ) -> None:
        """Test that decoder initializes with correct default state and empty buffers."""
        decoder = ProtocolDecoder()

        assert decoder.state == DecoderState.RESYNC
        assert decoder._buffer.available() == 0
        assert decoder._current_segment is None
        assert decoder._frame_handler is None
        assert decoder._remote_address == ""

    def test_protocol_decoder_when_initialized_with_handler_then_stores_handler(
        self,
    ) -> None:
        """Test that decoder correctly stores the provided frame handler."""
        handler = Mock()
        decoder = ProtocolDecoder(frame_handler=handler)

        assert decoder._frame_handler is handler

    def test_set_remote_address_when_called_then_stores_address(self) -> None:
        """Test that set_remote_address correctly stores the remote address."""
        decoder = ProtocolDecoder()
        address = "192.168.1.1:8080"

        decoder.set_remote_address(address)

        assert decoder._remote_address == address

    def test_set_frame_handler_when_called_then_updates_handler(self) -> None:
        """Test that set_frame_handler correctly updates the frame handler."""
        decoder = ProtocolDecoder()
        handler = Mock()

        decoder.set_frame_handler(handler)

        assert decoder._frame_handler is handler

    def test_reset_when_called_then_resets_to_initial_state(self) -> None:
        """Test that reset correctly resets decoder to initial state."""
        decoder = ProtocolDecoder()
        decoder._state = DecoderState.BLOCK_HEADER
        decoder._buffer.append(b"test data")
        decoder._current_segment = QBTSegment(filename="test.txt")

        decoder.reset()

        assert decoder._state == DecoderState.RESYNC
        assert decoder._buffer.available() == 0
        assert decoder._current_segment is None

    def test_feed_when_empty_data_then_no_processing(self) -> None:
        """Test that feeding empty data doesn't cause errors."""
        decoder = ProtocolDecoder()

        decoder.feed(b"")

        assert decoder._state == DecoderState.RESYNC
        assert decoder._buffer.available() == 0

    def test_feed_when_insufficient_sync_data_then_remains_in_resync(self) -> None:
        """Test that insufficient sync data keeps decoder in RESYNC state."""
        decoder = ProtocolDecoder()
        # Feed less than 6 sync bytes
        sync_data = xor_encode(b"\x00\x00\x00")

        decoder.feed(sync_data)

        assert decoder._state == DecoderState.RESYNC

    def test_synchronize_frame_when_sync_pattern_found_then_advances_state(self) -> None:
        """Test that valid sync pattern is detected and decoder advances."""
        decoder = ProtocolDecoder()
        # Create 6 consecutive sync bytes (0xFF when encoded, 0x00 when decoded)
        sync_data = xor_encode(b"\x00" * 6)

        decoder.feed(sync_data)

        assert decoder._state == DecoderState.START_FRAME

    def test_synchronize_frame_when_sync_pattern_in_middle_then_skips_to_sync(
        self,
    ) -> None:
        """Test that sync pattern detection skips garbage data at the beginning."""
        decoder = ProtocolDecoder()
        # Garbage data followed by sync pattern
        data = xor_encode(b"garbage\x00\x00\x00\x00\x00\x00")

        decoder.feed(data)

        assert decoder._state == DecoderState.START_FRAME

    def test_skip_null_bytes_when_null_bytes_present_then_skips_to_content(self) -> None:
        """Test that null bytes are properly skipped to find frame content."""
        decoder = ProtocolDecoder()
        decoder._state = DecoderState.START_FRAME
        # Null bytes followed by content
        data = xor_encode(b"\x00\x00\x00content")

        decoder.feed(data)

        assert decoder._state == DecoderState.FRAME_TYPE

    def test_determine_frame_type_when_data_block_header_then_sets_block_header_state(
        self,
    ) -> None:
        """Test that data block headers are correctly identified."""
        decoder = ProtocolDecoder()
        decoder._state = DecoderState.FRAME_TYPE
        # Data block header starts with "/PF"
        data = xor_encode(b"/PFtest_file.txt")

        decoder.feed(data)

        assert decoder._state == DecoderState.BLOCK_HEADER

    def test_determine_frame_type_when_server_list_header_then_sets_server_list_state(
        self,
    ) -> None:
        """Test that server list headers are correctly identified."""
        decoder = ProtocolDecoder()
        decoder._state = DecoderState.FRAME_TYPE
        # Server list header starts with "/Se"
        data = xor_encode(b"/ServerList/")

        decoder.feed(data)

        assert decoder._state == DecoderState.SERVER_LIST

    def test_determine_frame_type_when_unknown_header_then_resyncs(self) -> None:
        """Test that unknown frame types cause resynchronization."""
        decoder = ProtocolDecoder()
        decoder._state = DecoderState.FRAME_TYPE
        # Unknown header
        data = xor_encode(b"/UNKNOWNheader")

        decoder.feed(data)

        assert decoder._state == DecoderState.RESYNC

    def test_is_data_block_header_when_valid_header_then_returns_true(self) -> None:
        """Test data block header detection with valid headers."""
        assert ProtocolDecoder._is_data_block_header(b"/PF") is True
        assert ProtocolDecoder._is_data_block_header(b"/PFtest.txt") is True

    def test_is_data_block_header_when_invalid_header_then_returns_false(self) -> None:
        """Test data block header detection with invalid headers."""
        assert ProtocolDecoder._is_data_block_header(b"/Se") is False
        assert ProtocolDecoder._is_data_block_header(b"PF") is False
        assert ProtocolDecoder._is_data_block_header(b"/P") is False
        assert ProtocolDecoder._is_data_block_header(b"") is False

    def test_is_server_list_header_when_valid_header_then_returns_true(self) -> None:
        """Test server list header detection with valid headers."""
        assert ProtocolDecoder._is_server_list_header(b"/Se") is True
        assert ProtocolDecoder._is_server_list_header(b"/ServerList") is True

    def test_is_server_list_header_when_invalid_header_then_returns_false(self) -> None:
        """Test server list header detection with invalid headers."""
        assert ProtocolDecoder._is_server_list_header(b"/PF") is False
        assert ProtocolDecoder._is_server_list_header(b"Se") is False
        assert ProtocolDecoder._is_server_list_header(b"/S") is False
        assert ProtocolDecoder._is_server_list_header(b"") is False

    def test_process_server_list_when_null_terminated_then_processes_correctly(
        self,
    ) -> None:
        """Test server list processing with null-terminated content."""
        decoder = ProtocolDecoder()
        handler = Mock()
        decoder.set_frame_handler(handler)
        decoder._state = DecoderState.SERVER_LIST

        server_content = "/ServerList/192.168.1.1:8080|192.168.1.2:8080\x00"
        data = xor_encode(server_content.encode("ascii"))

        decoder.feed(data)

        assert decoder._state == DecoderState.START_FRAME
        handler.assert_called_once()
        frame = handler.call_args[0][0]
        assert isinstance(frame, ServerListFrame)

    def test_process_server_list_when_end_pattern_present_then_processes_correctly(
        self,
    ) -> None:
        """Test server list processing with end pattern marker."""
        decoder = ProtocolDecoder()
        handler = Mock()
        decoder.set_frame_handler(handler)
        decoder._state = DecoderState.SERVER_LIST

        server_content = "/ServerList/192.168.1.1:8080\\ServerList\\/SatServers/sat.example.com:8080\\SatServers\\\x00"
        data = xor_encode(server_content.encode("ascii"))

        decoder.feed(data)

        assert decoder._state == DecoderState.START_FRAME
        handler.assert_called_once()

    def test_process_block_header_when_insufficient_data_then_waits_for_more(
        self,
    ) -> None:
        """Test that block header processing waits for sufficient data."""
        decoder = ProtocolDecoder()
        decoder._state = DecoderState.BLOCK_HEADER
        # Less than 80 bytes
        data = xor_encode(b"/PFtest.txt short header")

        decoder.feed(data)

        assert decoder._state == DecoderState.BLOCK_HEADER  # Still waiting

    def test_process_block_header_when_valid_header_then_parses_correctly(self) -> None:
        """Test that valid block headers are parsed correctly."""
        decoder = ProtocolDecoder()
        decoder._state = DecoderState.BLOCK_HEADER

        # Create a valid 80-byte header
        header_content = "/PFtest.txt /PN 1 /PT 1 /CS 12345 /FD12/25/2023 10:30:00 AM /DL1024"
        header = header_content.ljust(78, " ") + "\r\n"
        data = xor_encode(header.encode("ascii"))

        decoder.feed(data)

        assert decoder._state == DecoderState.BLOCK_BODY
        assert decoder._current_segment is not None
        assert decoder._current_segment.filename == "test.txt"
        assert decoder._current_segment.block_number == 1
        assert decoder._current_segment.total_blocks == 1
        assert decoder._current_segment.checksum == 12345

    def test_process_block_header_when_invalid_format_then_raises_error(self) -> None:
        """Test that invalid header format raises ValueError."""
        decoder = ProtocolDecoder()
        decoder._state = DecoderState.BLOCK_HEADER

        # Invalid header format
        header = "Invalid header format".ljust(80, " ")
        data = xor_encode(header.encode("ascii"))

        with pytest.raises(ValueError, match="Invalid header format"):
            decoder.feed(data)

    @patch("byteblaster.protocol.decoder.datetime")
    def test_parse_header_groups_when_valid_match_then_creates_segment(
        self, mock_datetime: Mock
    ) -> None:
        """Test that header regex groups are parsed into QBTSegment correctly."""
        mock_now = datetime(2023, 12, 25, 15, 30, 45, tzinfo=UTC)
        mock_datetime.now.return_value = mock_now

        decoder = ProtocolDecoder()
        decoder.set_remote_address("192.168.1.1:8080")

        header_content = "/PFtest.txt /PN 2 /PT 5 /CS 54321 /FD12/25/2023 10:30:00 AM /DL512"
        header_str = header_content.ljust(78, " ") + "\r\n"
        match = decoder.HEADER_REGEX.match(header_str.encode("ascii"))
        assert match is not None

        segment = decoder._parse_header_groups(match, header_str)

        assert segment.filename == "test.txt"
        assert segment.block_number == 2
        assert segment.total_blocks == 5
        assert segment.checksum == 54321
        assert segment.length == 512
        assert segment.version == 2  # Has /DL parameter
        assert segment.source == "192.168.1.1:8080"
        assert segment.header == header_str

    def test_parse_header_groups_when_no_dl_parameter_then_v1_protocol(self) -> None:
        """Test that headers without /DL parameter are parsed as V1 protocol."""
        decoder = ProtocolDecoder()

        header_content = "/PFtest.txt /PN 1 /PT 1 /CS 12345 /FD12/25/2023 10:30:00 AM"
        header_str = header_content.ljust(78, " ") + "\r\n"
        match = decoder.HEADER_REGEX.match(header_str.encode("ascii"))
        assert match is not None

        segment = decoder._parse_header_groups(match, header_str)

        assert segment.version == 1
        assert segment.length == 1024  # V1 default

    def test_process_block_body_when_v1_protocol_then_reads_fixed_size(self) -> None:
        """Test that V1 protocol reads fixed 1024-byte blocks."""
        decoder = ProtocolDecoder()
        decoder._state = DecoderState.BLOCK_BODY
        decoder._current_segment = QBTSegment(
            filename="test.txt",
            version=1,
            length=1024,
            block_number=1,
            total_blocks=1,
        )

        # Less than 1024 bytes
        data = xor_encode(b"test content")
        decoder.feed(data)

        assert decoder._state == DecoderState.BLOCK_BODY  # Still waiting

        # Complete 1024 bytes
        content = b"test content".ljust(1024, b"\x00")
        data = xor_encode(content)
        decoder._buffer.clear()

        # Mock checksum validation to prevent segment from being emitted
        with patch("byteblaster.protocol.decoder.verify_checksum", return_value=True):
            decoder.feed(data)

        # After successful validation, state returns to START_FRAME and segment is processed
        assert decoder._state == DecoderState.START_FRAME
        assert decoder._current_segment is None  # Segment was processed and cleared

    def test_process_block_body_when_v2_protocol_then_reads_variable_size(self) -> None:
        """Test that V2 protocol reads variable-length blocks."""
        decoder = ProtocolDecoder()
        decoder._state = DecoderState.BLOCK_BODY
        decoder._current_segment = QBTSegment(
            filename="test.txt",
            version=2,
            length=500,
            block_number=1,
            total_blocks=1,
        )

        content = b"test content".ljust(500, b"\x00")
        data = xor_encode(content)

        # Mock decompression and checksum validation
        with (
            patch(
                "byteblaster.protocol.decoder.decompress_zlib", return_value=b"decompressed content"
            ),
            patch("byteblaster.protocol.decoder.verify_checksum", return_value=True),
        ):
            decoder.feed(data)

        # After successful validation, state returns to START_FRAME and segment is processed
        assert decoder._state == DecoderState.START_FRAME
        assert decoder._current_segment is None  # Segment was processed and cleared

    def test_validate_segment_when_invalid_block_numbers_then_skips_segment(
        self,
    ) -> None:
        """Test that segments with invalid block numbers are skipped."""
        decoder = ProtocolDecoder()
        decoder._state = DecoderState.VALIDATE
        decoder._current_segment = QBTSegment(
            filename="test.txt",
            block_number=0,  # Invalid
            total_blocks=1,
        )

        result = decoder._validate_segment()

        assert result is True
        assert decoder._current_segment is None

    def test_validate_segment_when_fillfile_then_skips_segment(self) -> None:
        """Test that FILLFILE.TXT segments are skipped."""
        decoder = ProtocolDecoder()
        decoder._state = DecoderState.VALIDATE
        decoder._current_segment = QBTSegment(
            filename="FILLFILE.TXT",
            block_number=1,
            total_blocks=1,
        )

        result = decoder._validate_segment()

        assert result is True
        assert decoder._current_segment is None

    def test_validate_segment_when_valid_segment_then_emits_frame(self) -> None:
        """Test that valid segments are emitted as DataBlockFrame."""
        decoder = ProtocolDecoder()
        handler = Mock()
        decoder.set_frame_handler(handler)
        decoder._current_segment = QBTSegment(
            filename="test.txt",
            block_number=1,
            total_blocks=1,
            content=b"test content",
        )

        with patch.object(decoder, "_validate_segment_checksum", return_value=True):
            decoder._validate_segment()

        handler.assert_called_once()
        frame = handler.call_args[0][0]
        assert isinstance(frame, DataBlockFrame)
        assert frame.segment
        assert frame.segment.filename == "test.txt"
        assert frame.content == b"test content"

    def test_validate_segment_when_text_file_then_trims_padding(self) -> None:
        """Test that text files have padding trimmed."""
        decoder = ProtocolDecoder()
        handler = Mock()
        decoder.set_frame_handler(handler)
        decoder._current_segment = QBTSegment(
            filename="test.txt",
            block_number=1,
            total_blocks=1,
            content=b"test content\x00\x00\x00   \r\n",
        )

        with patch.object(decoder, "_validate_segment_checksum", return_value=True):
            decoder._validate_segment()

        frame = handler.call_args[0][0]
        assert frame.content == b"test content"

    def test_validate_segment_checksum_when_v1_protocol_then_calls_v1_validation(
        self,
    ) -> None:
        """Test that V1 protocol uses V1 checksum validation."""
        decoder = ProtocolDecoder()
        segment = QBTSegment(version=1)

        with patch.object(decoder, "_validate_v1_checksum", return_value=True) as mock_v1:
            result = decoder._validate_segment_checksum(segment)

        assert result is True
        mock_v1.assert_called_once_with(segment)

    def test_validate_segment_checksum_when_v2_protocol_then_calls_v2_validation(
        self,
    ) -> None:
        """Test that V2 protocol uses V2 checksum validation."""
        decoder = ProtocolDecoder()
        segment = QBTSegment(version=2)

        with patch.object(decoder, "_validate_v2_checksum", return_value=True) as mock_v2:
            result = decoder._validate_segment_checksum(segment)

        assert result is True
        mock_v2.assert_called_once_with(segment)

    def test_validate_segment_checksum_when_unknown_version_then_returns_false(
        self,
    ) -> None:
        """Test that unknown protocol versions return False for checksum validation."""
        decoder = ProtocolDecoder()
        segment = QBTSegment(version=99)

        result = decoder._validate_segment_checksum(segment)

        assert result is False

    @patch("byteblaster.protocol.decoder.verify_checksum")
    def test_validate_v1_checksum_when_valid_then_returns_true(self, mock_verify: Mock) -> None:
        """Test V1 checksum validation with valid checksum."""
        mock_verify.return_value = True
        decoder = ProtocolDecoder()
        segment = QBTSegment(
            content=b"test content",
            checksum=12345,
        )

        result = decoder._validate_v1_checksum(segment)

        assert result is True
        mock_verify.assert_called_once_with(b"test content", 12345)

    @patch("byteblaster.protocol.decoder.verify_checksum")
    def test_validate_v1_checksum_when_invalid_then_returns_false(self, mock_verify: Mock) -> None:
        """Test V1 checksum validation with invalid checksum."""
        mock_verify.return_value = False
        decoder = ProtocolDecoder()
        segment = QBTSegment(
            content=b"test content",
            checksum=12345,
        )

        result = decoder._validate_v1_checksum(segment)

        assert result is False

    def test_validate_v2_checksum_when_compressed_data_then_validates_compressed(
        self,
    ) -> None:
        """Test V2 checksum validation with compressed data."""
        decoder = ProtocolDecoder()
        segment = QBTSegment(content=b"compressed_data")

        with (
            patch.object(decoder, "_is_compressed_data", return_value=True),
            patch.object(decoder, "_validate_compressed_data", return_value=True) as mock_validate,
        ):
            result = decoder._validate_v2_checksum(segment)

        assert result is True
        mock_validate.assert_called_once_with(segment)

    def test_validate_v2_checksum_when_uncompressed_data_then_validates_uncompressed(
        self,
    ) -> None:
        """Test V2 checksum validation with uncompressed data."""
        decoder = ProtocolDecoder()
        segment = QBTSegment(content=b"uncompressed_data")

        with (
            patch.object(decoder, "_is_compressed_data", return_value=False),
            patch.object(
                decoder, "_validate_uncompressed_v2_data", return_value=True
            ) as mock_validate,
        ):
            result = decoder._validate_v2_checksum(segment)

        assert result is True
        mock_validate.assert_called_once_with(segment)

    def test_is_compressed_data_when_zlib_header_then_returns_true(self) -> None:
        """Test compressed data detection with valid zlib headers."""
        decoder = ProtocolDecoder()

        # Common zlib headers
        assert decoder._is_compressed_data(b"\x78\x9c") is True  # Default compression
        assert decoder._is_compressed_data(b"\x78\x01") is True  # No compression
        assert decoder._is_compressed_data(b"\x78\xda") is True  # Best compression

    def test_is_compressed_data_when_no_zlib_header_then_returns_false(self) -> None:
        """Test compressed data detection with non-zlib data."""
        decoder = ProtocolDecoder()

        assert decoder._is_compressed_data(b"text data") is False
        assert decoder._is_compressed_data(b"\x00\x00") is False
        assert decoder._is_compressed_data(b"") is False

    @patch("zlib.decompress")
    @patch("byteblaster.protocol.decoder.verify_checksum")
    def test_validate_compressed_data_when_valid_then_returns_true(
        self, mock_verify: Mock, mock_decompress: Mock
    ) -> None:
        """Test compressed data validation with valid data."""
        mock_decompress.return_value = b"decompressed content"
        mock_verify.return_value = True

        decoder = ProtocolDecoder()
        segment = QBTSegment(
            content=b"\x78\x9ccompressed",
            checksum=12345,
        )

        result = decoder._validate_compressed_data(segment)

        assert result is True
        mock_decompress.assert_called_once_with(b"\x78\x9ccompressed")
        mock_verify.assert_called_once_with(b"decompressed content", 12345)

    @patch("zlib.decompress")
    @patch("byteblaster.protocol.decoder.verify_checksum")
    def test_validate_compressed_data_when_decompression_fails_then_returns_false(
        self, mock_verify: Mock, mock_decompress: Mock
    ) -> None:
        """Test compressed data validation when decompression fails."""
        mock_decompress.side_effect = OSError("Decompression failed")
        mock_verify.return_value = False

        decoder = ProtocolDecoder()
        segment = QBTSegment(content=b"invalid_compressed_data")

        result = decoder._validate_compressed_data(segment)

        assert result is False
        mock_verify.assert_called_once_with(b"invalid_compressed_data", 0)

    @patch("byteblaster.protocol.decoder.verify_checksum")
    def test_validate_uncompressed_v2_data_when_valid_then_returns_true(
        self, mock_verify: Mock
    ) -> None:
        """Test uncompressed V2 data validation with valid checksum."""
        mock_verify.return_value = True

        decoder = ProtocolDecoder()
        segment = QBTSegment(
            content=b"uncompressed content",
            checksum=12345,
        )

        result = decoder._validate_uncompressed_v2_data(segment)

        assert result is True
        mock_verify.assert_called_once_with(b"uncompressed content", 12345)

    def test_read_null_terminated_string_when_null_found_then_returns_string(
        self,
    ) -> None:
        """Test null-terminated string reading with valid terminator."""
        decoder = ProtocolDecoder()
        data = xor_encode(b"test string\x00remaining")
        decoder._buffer.append(data)

        result = decoder._read_null_terminated_string()

        assert result == "test string"

    def test_read_null_terminated_string_when_no_null_then_returns_none(self) -> None:
        """Test null-terminated string reading without terminator."""
        decoder = ProtocolDecoder()
        data = xor_encode(b"test string without null")
        decoder._buffer.append(data)

        result = decoder._read_null_terminated_string()

        assert result is None

    def test_emit_frame_when_handler_set_then_calls_handler(self) -> None:
        """Test that frame emission calls the configured handler."""
        decoder = ProtocolDecoder()
        handler = Mock()
        decoder.set_frame_handler(handler)

        frame = DataBlockFrame(
            content=b"test",
            segment=QBTSegment(filename="test.txt"),
        )

        decoder._emit_frame(frame)

        handler.assert_called_once_with(frame)

    def test_emit_frame_when_no_handler_then_no_error(self) -> None:
        """Test that frame emission without handler doesn't cause errors."""
        decoder = ProtocolDecoder()

        frame = DataBlockFrame(
            content=b"test",
            segment=QBTSegment(filename="test.txt"),
        )

        # Should not raise an exception
        decoder._emit_frame(frame)

    def test_emit_frame_when_handler_raises_exception_then_continues(self) -> None:
        """Test that handler exceptions don't crash the decoder."""
        decoder = ProtocolDecoder()
        handler = Mock(side_effect=Exception("Handler error"))
        decoder.set_frame_handler(handler)

        frame = DataBlockFrame(
            content=b"test",
            segment=QBTSegment(filename="test.txt"),
        )

        # Should not raise an exception despite handler error
        decoder._emit_frame(frame)

        handler.assert_called_once_with(frame)

    def test_process_current_state_when_unknown_state_then_raises_error(self) -> None:
        """Test that unknown decoder states raise RuntimeError."""
        decoder = ProtocolDecoder()
        decoder._state = "INVALID_STATE"  # type: ignore[assignment]

        with pytest.raises(RuntimeError, match="Unknown decoder state"):
            decoder._process_current_state()


class TestProtocolDecoderIntegration:
    """Integration tests for complete protocol processing scenarios."""

    def test_complete_v1_data_block_processing(self) -> None:
        """Test complete processing of a V1 data block from sync to emission."""
        decoder = ProtocolDecoder()
        handler = Mock()
        decoder.set_frame_handler(handler)

        # Create complete V1 frame: sync + header + body
        sync_bytes = b"\x00" * 6
        header = (
            "/PFtest.txt /PN 1 /PT 1 /CS 12345 /FD12/25/2023 10:30:00 AM".ljust(78, " ") + "\r\n"
        )
        body = b"test content".ljust(1024, b"\x00")

        complete_frame = sync_bytes + header.encode("ascii") + body
        encoded_data = xor_encode(complete_frame)

        # Mock checksum validation
        with patch("byteblaster.protocol.decoder.verify_checksum", return_value=True):
            decoder.feed(encoded_data)

        # Verify frame was emitted
        handler.assert_called_once()
        frame = handler.call_args[0][0]
        assert isinstance(frame, DataBlockFrame)
        assert frame.segment is not None
        assert frame.segment.filename == "test.txt"
        assert frame.segment.version == 1
        assert frame.content.startswith(b"test content")

    def test_complete_v2_data_block_processing(self) -> None:
        """Test complete processing of a V2 data block with compression."""
        decoder = ProtocolDecoder()
        handler = Mock()
        decoder.set_frame_handler(handler)

        # Create complete V2 frame with compressed data
        sync_bytes = b"\x00" * 6
        header_content = "/PFtest.txt /PN 1 /PT 1 /CS 12345 /FD12/25/2023 10:30:00 AM /DL100"
        header = header_content.ljust(78, " ") + "\r\n"
        # Simulate compressed data
        body = b"\x78\x9c" + b"compressed_content".ljust(98, b"\x00")

        complete_frame = sync_bytes + header.encode("ascii") + body
        encoded_data = xor_encode(complete_frame)

        # Mock decompression and checksum validation
        with (
            patch(
                "byteblaster.protocol.decoder.decompress_zlib",
                return_value=b"decompressed content",
            ),
            patch("byteblaster.protocol.decoder.verify_checksum", return_value=True),
        ):
            decoder.feed(encoded_data)

        # Verify frame was emitted
        handler.assert_called_once()
        frame = handler.call_args[0][0]
        assert isinstance(frame, DataBlockFrame)
        assert frame.segment is not None
        assert frame.segment.filename == "test.txt"
        assert frame.segment.version == 2

    def test_complete_server_list_processing(self) -> None:
        """Test complete processing of a server list frame."""
        decoder = ProtocolDecoder()
        handler = Mock()
        decoder.set_frame_handler(handler)

        # Create complete server list frame
        sync_bytes = b"\x00" * 6
        server_content = "/ServerList/192.168.1.1:8080|192.168.1.2:8080\x00"

        complete_frame = sync_bytes + server_content.encode("ascii")
        encoded_data = xor_encode(complete_frame)

        decoder.feed(encoded_data)

        # Verify frame was emitted
        handler.assert_called_once()
        frame = handler.call_args[0][0]
        assert isinstance(frame, ServerListFrame)
        assert frame.server_list is not None
        assert len(frame.server_list) > 0

    def test_multiple_frames_processing(self) -> None:
        """Test processing multiple frames in sequence."""
        decoder = ProtocolDecoder()
        handler = Mock()
        decoder.set_frame_handler(handler)

        # Create two complete frames back-to-back
        sync_bytes = b"\x00" * 6

        # First frame - server list
        server_content = "/ServerList/192.168.1.1:8080\x00"
        frame1 = sync_bytes + server_content.encode("ascii")

        # Second frame - data block
        header = (
            "/PFtest.txt /PN 1 /PT 1 /CS 12345 /FD12/25/2023 10:30:00 AM".ljust(78, " ") + "\r\n"
        )
        body = b"test content".ljust(1024, b"\x00")
        frame2 = sync_bytes + header.encode("ascii") + body

        complete_data = frame1 + frame2
        encoded_data = xor_encode(complete_data)

        # Mock checksum validation for data block
        with patch("byteblaster.protocol.decoder.verify_checksum", return_value=True):
            decoder.feed(encoded_data)

        # Verify both frames were emitted
        assert handler.call_count == 2
        frame1_emitted = handler.call_args_list[0][0][0]
        frame2_emitted = handler.call_args_list[1][0][0]

        assert isinstance(frame1_emitted, ServerListFrame)
        assert isinstance(frame2_emitted, DataBlockFrame)

    def test_chunked_data_processing(self) -> None:
        """Test processing data that arrives in small chunks."""
        decoder = ProtocolDecoder()
        handler = Mock()
        decoder.set_frame_handler(handler)

        # Create complete frame
        sync_bytes = b"\x00" * 6
        header = (
            "/PFtest.txt /PN 1 /PT 1 /CS 12345 /FD12/25/2023 10:30:00 AM".ljust(78, " ") + "\r\n"
        )
        body = b"test content".ljust(1024, b"\x00")

        complete_frame = sync_bytes + header.encode("ascii") + body
        encoded_data = xor_encode(complete_frame)

        # Feed data in small chunks
        chunk_size = 10
        with patch("byteblaster.protocol.decoder.verify_checksum", return_value=True):
            for i in range(0, len(encoded_data), chunk_size):
                chunk = encoded_data[i : i + chunk_size]
                decoder.feed(chunk)

        # Verify frame was eventually emitted
        handler.assert_called_once()
        frame = handler.call_args[0][0]
        assert isinstance(frame, DataBlockFrame)

    def test_error_recovery_after_corruption(self) -> None:
        """Test that decoder recovers from data corruption."""
        decoder = ProtocolDecoder()
        handler = Mock()
        decoder.set_frame_handler(handler)

        # Feed corrupted data followed by valid frame
        corrupted_data = xor_encode(b"corrupted garbage data")
        decoder.feed(corrupted_data)

        # Now feed valid frame
        sync_bytes = b"\x00" * 6
        server_content = "/ServerList/192.168.1.1:8080\x00"
        valid_frame = sync_bytes + server_content.encode("ascii")
        encoded_valid = xor_encode(valid_frame)

        decoder.feed(encoded_valid)

        # Should recover and process the valid frame
        handler.assert_called_once()
        frame = handler.call_args[0][0]
        assert isinstance(frame, ServerListFrame)


@pytest.fixture
def sample_qbt_segment() -> QBTSegment:
    """Fixture providing a sample QBTSegment for testing."""
    return QBTSegment(
        filename="test.txt",
        block_number=1,
        total_blocks=5,
        content=b"sample content",
        checksum=12345,
        length=14,
        version=1,
        timestamp=datetime(2023, 12, 25, 10, 30, 0, tzinfo=UTC),
        source="192.168.1.1:8080",
    )


@pytest.fixture
def sample_server_list() -> ByteBlasterServerList:
    """Fixture providing a sample ByteBlasterServerList for testing."""
    return ByteBlasterServerList(
        servers=[("192.168.1.1", 8080), ("192.168.1.2", 8080)],
        sat_servers=[("sat1.example.com", 8080)],
    )


class TestProtocolDecoderEdgeCases:
    """Test edge cases and error conditions in protocol decoder."""

    def test_feed_when_very_large_data_then_processes_correctly(self) -> None:
        """Test that very large data chunks are processed correctly."""
        decoder = ProtocolDecoder()
        # Create large data chunk (larger than typical buffer sizes)
        large_data = b"A" * 10000
        encoded_data = xor_encode(large_data)

        # Should not raise exceptions
        decoder.feed(encoded_data)

    def test_synchronize_frame_when_partial_sync_at_end_then_preserves_data(
        self,
    ) -> None:
        """Test that partial sync patterns at buffer end are preserved."""
        decoder = ProtocolDecoder()

        # Feed data ending with partial sync pattern
        data = xor_encode(b"garbage\x00\x00\x00")  # Only 3 of 6 sync bytes
        decoder.feed(data)

        # Buffer should preserve the partial sync pattern
        assert decoder._buffer.available() >= 3

    def test_skip_null_bytes_when_only_null_bytes_then_consumes_all(self) -> None:
        """Test that buffer of only null bytes is completely consumed."""
        decoder = ProtocolDecoder()
        decoder._state = DecoderState.START_FRAME

        null_data = xor_encode(b"\x00" * 100)
        decoder.feed(null_data)

        # Should have consumed all null bytes but still be waiting for content
        assert decoder._state == DecoderState.START_FRAME

    def test_read_null_terminated_string_when_unicode_decode_error_then_handles_gracefully(
        self,
    ) -> None:
        """Test that unicode decode errors in string reading are handled."""
        decoder = ProtocolDecoder()

        # Feed invalid UTF-8/ASCII data followed by null
        invalid_data = b"\xff\xfe\x00"  # Invalid ASCII followed by null
        encoded_data = xor_encode(invalid_data)
        decoder._buffer.append(encoded_data)

        result = decoder._read_null_terminated_string()

        # Should handle decode errors gracefully
        assert result is not None  # Should not crash

    def test_header_regex_constants_when_accessed_then_defined_correctly(self) -> None:
        """Test that header regex and constants are properly defined."""
        assert ProtocolDecoder.FRAME_SYNC_BYTES == 6
        assert ProtocolDecoder.HEADER_SIZE == 80
        assert ProtocolDecoder.V1_BODY_SIZE == 1024
        assert ProtocolDecoder.MAX_V2_BODY_SIZE == 1024
        assert isinstance(ProtocolDecoder.HEADER_REGEX, re.Pattern)
        assert isinstance(ProtocolDecoder.HEADER_DATE_FORMAT, str)
