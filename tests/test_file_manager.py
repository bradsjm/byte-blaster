from unittest.mock import AsyncMock, MagicMock

import pytest

from byte_blaster.client import ByteBlasterClientOptions, ByteBlasterClient
from byte_blaster.file_manager import ByteBlasterFileManager, CompletedFile


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
    manager._client = mock_client # type: ignore
    return manager


@pytest.mark.asyncio
async def test_file_manager_start_stop(file_manager: ByteBlasterFileManager, mock_client: MagicMock):
    """Test starting and stopping the file manager."""
    await file_manager.start()
    mock_client.start.assert_called_once()

    await file_manager.stop()
    mock_client.stop.assert_called_once()


def test_file_manager_subscribe_unsubscribe(file_manager: ByteBlasterFileManager):
    """Test subscribing and unsubscribing handlers."""
    handler1 = AsyncMock()
    handler2 = AsyncMock()

    file_manager.subscribe(handler1)
    file_manager.subscribe(handler2)
    assert handler1 in file_manager._file_handlers # type: ignore
    assert handler2 in file_manager._file_handlers # type: ignore

    file_manager.unsubscribe(handler1)
    assert handler1 not in file_manager._file_handlers # type: ignore
    assert handler2 in file_manager._file_handlers # type: ignore


@pytest.mark.asyncio
async def test_file_dispatch(file_manager: ByteBlasterFileManager):
    """Test that completed files are dispatched to handlers."""
    handler1 = AsyncMock()
    handler2 = AsyncMock()

    file_manager.subscribe(handler1)
    file_manager.subscribe(handler2)

    completed_file = CompletedFile(filename="test.txt", data=b"data")
    await file_manager._dispatch_file(completed_file) # type: ignore

    handler1.assert_called_once_with(completed_file)
    handler2.assert_called_once_with(completed_file) 