"""Tests for the crypto module in ByteBlaster."""

import zlib

import pytest

from byteblaster.utils import crypto


def test_xor_encode_and_decode_bytes():
    original = b"ByteBlaster123"
    encoded = crypto.xor_encode(original)
    assert encoded != original
    decoded = crypto.xor_decode(encoded)
    assert decoded == original

    # XOR is symmetric
    assert crypto.xor_encode(encoded) == original
    assert crypto.xor_decode(original) == crypto.xor_encode(original)


@pytest.mark.parametrize(
    ("text", "encoding"),
    [
        ("Hello, World!", "ascii"),
        ("Привет", "utf-8"),
        ("こんにちは", "utf-8"),
        ("", "ascii"),
    ],
)
def test_xor_encode_decode_string(text: str, encoding: str):
    encoded = crypto.xor_encode_string(text, encoding)
    assert isinstance(encoded, bytes)
    decoded = crypto.xor_decode_string(encoded, encoding)
    assert decoded == text

    # Round-trip
    assert crypto.xor_decode_string(crypto.xor_encode_string(text, encoding), encoding) == text


def test_xor_encode_string_unicode_error():
    # Latin-1 can't encode Cyrillic
    with pytest.raises(UnicodeEncodeError):
        crypto.xor_encode_string("Привет", encoding="latin-1")


def test_decompress_zlib_success():
    # Compress some data with zlib, add 2-byte header
    raw = b"ByteBlaster compression test"
    compressed = zlib.compress(raw)
    header = b"\xab\xcd"
    data_with_header = header + compressed
    result = crypto.decompress_zlib(data_with_header, skip_header_bytes=2)
    assert result == raw

    # Custom header length
    header3 = b"\x01\x02\x03"
    data_with_header3 = header3 + compressed
    result3 = crypto.decompress_zlib(data_with_header3, skip_header_bytes=3)
    assert result3 == raw


def test_decompress_zlib_too_short():
    with pytest.raises(ValueError):  # noqa: PT011
        crypto.decompress_zlib(b"\x00", skip_header_bytes=2)


def test_decompress_zlib_invalid_data():
    # Not valid zlib after header
    with pytest.raises(zlib.error):
        crypto.decompress_zlib(b"\x00\x00notzlib", skip_header_bytes=2)


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (b"\x01\x02\x03", (0x01 + 0x02 + 0x03) & 0xFFFF),
        (b"", 0),
        (b"\xff" * 10, (0xFF * 10) & 0xFFFF),
    ],
)
def test_calculate_checksum(data: bytes, expected: int):
    assert crypto.calculate_checksum(data) == expected


def test_verify_checksum():
    data = b"ByteBlaster"
    checksum = crypto.calculate_checksum(data)
    assert crypto.verify_checksum(data, checksum)
    assert not crypto.verify_checksum(data, checksum + 1)
    assert not crypto.verify_checksum(data, -1)


def test_xorbuffer_basic_usage():
    original = b"TestBuffer"
    encoded = crypto.xor_encode(original)
    buf = crypto.XorBuffer(encoded)

    # Available bytes
    assert buf.available() == len(original)

    # Peek does not consume
    peeked = buf.peek(4)
    assert peeked == original[:4]
    assert buf.available() == len(original)

    # Read consumes
    read = buf.read(4)
    assert read == original[:4]
    assert buf.available() == len(original) - 4

    # Append more data
    more = crypto.xor_encode(b"123")
    buf.append(more)
    assert buf.available() == len(original) - 4 + 3

    # Read rest
    rest = buf.read(100)
    assert rest == original[4:] + b"123"
    assert buf.available() == 0

    # Skip and clear
    buf.append(crypto.xor_encode(b"skipme"))
    skipped = buf.skip(3)
    assert skipped == 3
    assert buf.available() == len("skipme") - 3
    buf.clear()
    assert buf.available() == 0

    # Compact after partial read
    buf.append(crypto.xor_encode(b"abcdef"))
    _ = buf.read(2)
    buf.compact()
    assert buf.available() == 4
    assert buf.read(4) == b"cdef"
    assert buf.available() == 0


def test_xorbuffer_peek_offset_and_bounds():
    data = crypto.xor_encode(b"abcdefgh")
    buf = crypto.XorBuffer(data)
    # Offset peek
    assert buf.peek(3, offset=2) == b"cde"
    # Out of bounds
    assert buf.peek(100, offset=6) == b"gh"
    # Offset past end
    assert buf.peek(2, offset=100) == b""
