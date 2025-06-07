"""Basic tests to verify package functionality and imports."""

import pytest

from byte_blaster import (
    ByteBlasterClient,
    QBTSegment,
    ByteBlasterServerList,
    ServerListManager,
)
from byte_blaster.client import ByteBlasterClientOptions
from byte_blaster.utils.crypto import xor_encode, xor_decode, verify_checksum


@pytest.fixture
def client_options():
    """Fixture for ByteBlasterClientOptions."""
    return ByteBlasterClientOptions("test@example.com")


@pytest.fixture
def server_list():
    """Fixture for ByteBlasterServerList."""
    return ByteBlasterServerList()


@pytest.fixture
def server_manager():
    """Fixture for ServerListManager."""
    return ServerListManager(enable_persistence=False)


def test_package_imports():
    """Test that all main components can be imported."""
    # Test that classes exist and can be instantiated
    assert ByteBlasterClient is not None
    assert QBTSegment is not None
    assert ByteBlasterServerList is not None
    assert ServerListManager is not None
    assert ByteBlasterClientOptions is not None


@pytest.mark.parametrize(
    "test_data",
    [
        b"Hello, World!",
        b"",
        b"\x00\x01\x02\x03",
    ],
)
def test_xor_encoding(test_data: bytes):
    """Test XOR encoding and decoding functions."""
    # Test encoding and decoding
    encoded = xor_encode(test_data)
    decoded = xor_decode(encoded)

    assert decoded == test_data
    if test_data:
        assert encoded != test_data


@pytest.mark.parametrize(
    "test_data, is_valid",
    [
        (b"Test data for checksum", True),
        (b"Another test", True),
        (b"", True),
    ],
)
def test_checksum_verification(test_data: bytes, is_valid: bool):
    """Test checksum calculation and verification."""
    # Calculate checksum manually
    expected_checksum = sum(test_data) & 0xFFFF

    # Test verification
    assert verify_checksum(test_data, expected_checksum) == is_valid
    if is_valid:
        assert not verify_checksum(test_data, expected_checksum + 1)
        assert not verify_checksum(test_data, -1)


def test_server_list_creation(server_list: ByteBlasterServerList):
    """Test server list creation and basic functionality."""
    # Should have default servers
    assert len(server_list) > 0
    assert bool(server_list)

    # Test getting all servers
    all_servers = server_list.get_all_servers()
    assert len(all_servers) == len(server_list.servers)


def test_segment_creation():
    """Test QBTSegment creation."""
    segment = QBTSegment(
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
async def test_client_creation(client_options: ByteBlasterClientOptions):
    """Test ByteBlaster client creation."""
    client = ByteBlasterClient(client_options)

    assert client.email == "test@example.com"
    assert not client.is_connected
    assert not client.is_running
    assert client.server_count > 0


def test_server_manager(server_manager: ServerListManager):
    """Test server list manager basic functionality."""
    assert len(server_manager) > 0
    assert bool(server_manager)

    # Test getting next server
    server = server_manager.get_next_server()
    assert server is not None
    assert len(server) == 2  # (host, port)
    assert isinstance(server[0], str)
    assert isinstance(server[1], int)
