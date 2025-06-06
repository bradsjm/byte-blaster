"""Basic tests to verify package functionality and imports."""

import pytest

from byte_blaster import ByteBlasterClient, QuickBlockTransferSegment, ByteBlasterServerList
from byte_blaster.client import ByteBlasterClientOptions
from byte_blaster.utils.crypto import xor_encode, xor_decode, verify_checksum
from byte_blaster.server.manager import ServerListManager


def test_package_imports():
    """Test that all main components can be imported."""
    # Test that classes exist and can be instantiated
    assert ByteBlasterClient is not None
    assert QuickBlockTransferSegment is not None
    assert ByteBlasterServerList is not None
    assert ServerListManager is not None


def test_xor_encoding():
    """Test XOR encoding and decoding functions."""
    test_data = b"Hello, World!"

    # Test encoding and decoding
    encoded = xor_encode(test_data)
    decoded = xor_decode(encoded)

    assert decoded == test_data
    assert encoded != test_data


def test_checksum_verification():
    """Test checksum calculation and verification."""
    test_data = b"Test data for checksum"

    # Calculate checksum manually
    expected_checksum = sum(test_data) & 0xFFFF

    # Test verification
    assert verify_checksum(test_data, expected_checksum)
    assert not verify_checksum(test_data, expected_checksum + 1)
    assert not verify_checksum(test_data, -1)


def test_server_list_creation():
    """Test server list creation and basic functionality."""
    server_list = ByteBlasterServerList()

    # Should have default servers
    assert len(server_list) > 0
    assert bool(server_list)

    # Test getting all servers
    all_servers = server_list.get_all_servers()
    assert len(all_servers) == len(server_list.servers)


def test_segment_creation():
    """Test QuickBlockTransferSegment creation."""
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
    assert segment.content == b"test content"
    assert segment.key.startswith("test.txt_")


@pytest.mark.asyncio
async def test_client_creation():
    """Test ByteBlaster client creation."""
    client = ByteBlasterClient(ByteBlasterClientOptions("test@example.com"))

    assert client.email == "test@example.com"
    assert not client.is_connected
    assert not client.is_running
    assert client.server_count > 0


def test_server_manager():
    """Test server list manager basic functionality."""
    manager = ServerListManager(enable_persistence=False)

    assert len(manager) > 0
    assert bool(manager)

    # Test getting next server
    server = manager.get_next_server()
    assert server is not None
    assert len(server) == 2  # (host, port)
    assert isinstance(server[0], str)
    assert isinstance(server[1], int)
