"""Cryptographic and encoding utilities for ByteBlaster protocol.

This module provides utilities for XOR encoding/decoding and compression handling
as required by the ByteBlaster protocol specification.
"""

import zlib


def xor_encode(data: bytes) -> bytes:
    """Encode bytes by XOR-ing each byte with 0xFF.

    The ByteBlaster protocol requires all transmitted data to be XOR'ed with 0xFF.
    This function applies that encoding.

    Args:
        data: Raw bytes to encode

    Returns:
        XOR-encoded bytes

    Example:
        >>> data = b"Hello"
        >>> encoded = xor_encode(data)
        >>> decoded = xor_decode(encoded)
        >>> decoded == data
        True

    """
    return bytes(b ^ 0xFF for b in data)


def xor_decode(data: bytes) -> bytes:
    """Decode bytes by XOR-ing each byte with 0xFF.

    The ByteBlaster protocol XOR's all data with 0xFF. Since XOR is symmetric,
    decoding uses the same operation as encoding.

    Args:
        data: XOR-encoded bytes to decode

    Returns:
        Decoded bytes

    """
    return bytes(b ^ 0xFF for b in data)


def xor_encode_string(text: str, encoding: str = "ascii") -> bytes:
    """Encode a string by converting to bytes and XOR-ing with 0xFF.

    Args:
        text: String to encode
        encoding: Character encoding to use (default: ascii)

    Returns:
        XOR-encoded bytes

    Raises:
        UnicodeEncodeError: If text cannot be encoded with specified encoding

    """
    try:
        text_bytes = text.encode(encoding)
    except UnicodeEncodeError as e:
        msg = f"Cannot encode text with {encoding}: {text}"
        raise UnicodeEncodeError(encoding, text, 0, len(text), msg) from e

    return xor_encode(text_bytes)


def xor_decode_string(data: bytes, encoding: str = "ascii") -> str:
    """Decode XOR-encoded bytes to string.

    Args:
        data: XOR-encoded bytes to decode
        encoding: Character encoding to use (default: ascii)

    Returns:
        Decoded string

    Raises:
        UnicodeDecodeError: If decoded bytes cannot be decoded as specified encoding

    """
    decoded_bytes = xor_decode(data)
    try:
        return decoded_bytes.decode(encoding)
    except UnicodeDecodeError as e:
        msg = f"Cannot decode bytes with {encoding}: {decoded_bytes}"
        raise UnicodeDecodeError(encoding, decoded_bytes, 0, len(decoded_bytes), msg) from e


def decompress_zlib(data: bytes, skip_header_bytes: int = 2) -> bytes:
    """Decompress zlib-compressed data, optionally skipping header bytes.

    The ByteBlaster protocol V2 uses zlib compression but includes extra header
    bytes that need to be skipped before decompression.

    Args:
        data: Compressed data bytes
        skip_header_bytes: Number of header bytes to skip (default: 2)

    Returns:
        Decompressed data

    Raises:
        ValueError: If data is too short or decompression fails
        zlib.error: If decompression fails due to invalid data

    """
    if len(data) < skip_header_bytes:
        msg = f"Data too short: need at least {skip_header_bytes} bytes, got {len(data)}"
        raise ValueError(msg)

    # Skip header bytes as they're not part of the deflate stream
    compressed_data = data[skip_header_bytes:]

    try:
        return zlib.decompress(compressed_data)
    except zlib.error as e:
        msg = f"Failed to decompress data: {e}"
        raise zlib.error(msg) from e


def verify_checksum(data: bytes, expected_checksum: int) -> bool:
    """Verify data checksum using simple byte sum.

    The ByteBlaster protocol uses a simple checksum that's the sum of all bytes
    in the data as a 16-bit unsigned decimal.

    Args:
        data: Data bytes to verify
        expected_checksum: Expected checksum value

    Returns:
        True if checksum matches, False otherwise

    """
    if expected_checksum < 0:
        return False

    calculated_checksum = sum(data) & 0xFFFF  # Keep as 16-bit unsigned
    return calculated_checksum == expected_checksum


def calculate_checksum(data: bytes) -> int:
    """Calculate checksum for data using simple byte sum.

    Args:
        data: Data bytes to checksum

    Returns:
        Checksum as 16-bit unsigned integer

    """
    return sum(data) & 0xFFFF


class XorBuffer:
    """Buffer that automatically XOR decodes data as it's read.

    This class provides a convenient way to work with XOR-encoded data streams,
    automatically decoding data as it's consumed.
    """

    def __init__(self, initial_data: bytes = b"") -> None:
        """Initialize buffer with optional initial data.

        Args:
            initial_data: Initial XOR-encoded data to add to buffer

        """
        self._buffer = bytearray(initial_data)
        self._position = 0

    def append(self, data: bytes) -> None:
        """Append XOR-encoded data to buffer.

        Args:
            data: XOR-encoded bytes to append

        """
        self._buffer.extend(data)

    def peek(self, size: int, offset: int = 0) -> bytes:
        """Peek at decoded data without consuming it.

        Args:
            size: Number of bytes to peek at
            offset: Offset from current position to start peek

        Returns:
            Decoded bytes (may be shorter than requested if not enough data)

        """
        start = self._position + offset
        end = min(start + size, len(self._buffer))

        if start >= len(self._buffer):
            return b""

        encoded_data = bytes(self._buffer[start:end])
        return xor_decode(encoded_data)

    def read(self, size: int) -> bytes:
        """Read and consume decoded data from buffer.

        Args:
            size: Number of bytes to read

        Returns:
            Decoded bytes (may be shorter than requested if not enough data)

        """
        data = self.peek(size)
        self._position += len(data)
        return data

    def skip(self, size: int) -> int:
        """Skip bytes in buffer without decoding.

        Args:
            size: Number of bytes to skip

        Returns:
            Number of bytes actually skipped

        """
        available = len(self._buffer) - self._position
        to_skip = min(size, available)
        self._position += to_skip
        return to_skip

    def available(self) -> int:
        """Get number of bytes available to read."""
        return len(self._buffer) - self._position

    def clear(self) -> None:
        """Clear buffer and reset position."""
        self._buffer.clear()
        self._position = 0

    def compact(self) -> None:
        """Remove consumed data from buffer to free memory."""
        if self._position > 0:
            del self._buffer[: self._position]
            self._position = 0
