"""ByteBlaster utilities package.

This package contains utility functions and classes for the ByteBlaster
protocol implementation, including cryptographic operations, compression
handling, and other helper functions.
"""

from byte_blaster.utils.crypto import (
    XorBuffer,
    calculate_checksum,
    decompress_zlib,
    verify_checksum,
    xor_decode,
    xor_decode_string,
    xor_encode,
    xor_encode_string,
)

__all__ = [
    "XorBuffer",
    "calculate_checksum",
    "decompress_zlib",
    "verify_checksum",
    "xor_decode",
    "xor_decode_string",
    "xor_encode",
    "xor_encode_string",
]
