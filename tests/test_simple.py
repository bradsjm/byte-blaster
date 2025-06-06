#!/usr/bin/env python3
"""Simple test script to verify ByteBlaster package functionality."""

import sys
from pathlib import Path

from byte_blaster.client import ByteBlasterClientOptions

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from byte_blaster import ByteBlasterClient, ByteBlasterServerList, QuickBlockTransferSegment
from byte_blaster.server.manager import ServerListManager
from byte_blaster.utils.crypto import verify_checksum, xor_decode, xor_encode


def test_xor_operations():
    """Test XOR encoding and decoding."""
    print("Testing XOR operations...")

    test_data = b"Hello, ByteBlaster!"
    encoded = xor_encode(test_data)
    decoded = xor_decode(encoded)

    assert decoded == test_data, "XOR decode failed"
    assert encoded != test_data, "XOR encode failed"
    print("✓ XOR operations work correctly")


def test_checksum():
    """Test checksum calculation."""
    print("Testing checksum verification...")

    test_data = b"Test checksum data"
    checksum = sum(test_data) & 0xFFFF

    assert verify_checksum(test_data, checksum), "Checksum verification failed"
    assert not verify_checksum(test_data, checksum + 1), "Invalid checksum accepted"
    print("✓ Checksum verification works correctly")


def test_server_list():
    """Test server list functionality."""
    print("Testing server list...")

    server_list = ByteBlasterServerList()
    assert len(server_list) > 0, "No default servers"
    assert bool(server_list), "Server list reports empty"

    all_servers = server_list.get_all_servers()
    assert len(all_servers) > 0, "No servers available"
    print(f"✓ Server list has {len(all_servers)} servers")


def test_segment():
    """Test QuickBlockTransferSegment."""
    print("Testing data segment...")

    segment = QuickBlockTransferSegment(
        filename="test.txt",
        block_number=1,
        total_blocks=5,
        content=b"test content",
        checksum=123,
        length=12,
    )

    assert segment.filename == "test.txt"
    assert segment.block_number == 1
    assert segment.total_blocks == 5
    assert "test.txt" in segment.key
    print("✓ Data segment works correctly")


def test_server_manager():
    """Test server manager."""
    print("Testing server manager...")

    manager = ServerListManager(enable_persistence=False)
    assert len(manager) > 0, "No servers in manager"

    server = manager.get_next_server()
    assert server is not None, "No server returned"
    assert len(server) == 2, "Invalid server format"

    host, port = server
    assert isinstance(host, str), "Host is not string"
    assert isinstance(port, int), "Port is not integer"
    assert 1 <= port <= 65535, "Port out of range"
    print(f"✓ Server manager returned {host}:{port}")


def test_client_creation():
    """Test client creation."""
    print("Testing client creation...")

    client = ByteBlasterClient(ByteBlasterClientOptions("test@example.com"))
    assert client.email == "test@example.com"
    assert not client.is_connected
    assert not client.is_running
    assert client.server_count > 0
    print("✓ Client created successfully")


def main():
    """Run all tests."""
    print("ByteBlaster Simple Test Suite")
    print("=" * 40)

    try:
        test_xor_operations()
        test_checksum()
        test_server_list()
        test_segment()
        test_server_manager()
        test_client_creation()

        print("=" * 40)
        print("✓ All tests passed!")
        print("\nBasic functionality verified. The ByteBlaster package is working correctly.")

    except Exception as e:
        print(f"✗ Test failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
