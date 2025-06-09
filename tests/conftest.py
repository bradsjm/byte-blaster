"""Global fixtures for Byte Blaster tests."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from byteblaster.client import ByteBlasterClient, ByteBlasterClientOptions
from byteblaster.file_manager import ByteBlasterFileManager


@pytest.fixture
def mock_client() -> MagicMock:
    """Fixture for a mocked ByteBlasterClient."""
    client = MagicMock(spec=ByteBlasterClient)
    client.start = AsyncMock()
    client.stop = AsyncMock()
    client.subscribe = MagicMock()
    return client


@pytest.fixture
def file_manager(mock_client: MagicMock) -> ByteBlasterFileManager:
    """Fixture for ByteBlasterFileManager with a mocked client."""
    options = ByteBlasterClientOptions(email="test@example.com")
    manager = ByteBlasterFileManager(options)
    manager._client = mock_client  # type: ignore[protected-access]
    return manager
