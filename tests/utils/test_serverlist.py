# pyright: reportPrivateUsage=false
"""Unit tests for ServerListManager and ByteBlasterServerList."""

import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

from byteblaster.protocol.models import ByteBlasterServerList
from byteblaster.utils.serverlist import ServerListManager


@pytest.fixture
def temp_persist_path() -> Iterator[Path]:
    """Fixture for a temporary file path for persistence."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "servers.json"


def make_server_list(
    servers: list[tuple[str, int]] | None = None,
    sat_servers: list[tuple[str, int]] | None = None,
) -> ByteBlasterServerList:
    """Create a ByteBlasterServerList with custom servers."""
    _servers: list[tuple[str, int]] = (
        servers if servers is not None else [("host1", 1234), ("host2", 5678)]
    )
    _sat_servers: list[tuple[str, int]] = (
        sat_servers if sat_servers is not None else [("sat1", 4321)]
    )
    return ByteBlasterServerList(servers=_servers, sat_servers=_sat_servers)


def test_loads_default_when_no_file(temp_persist_path: Path) -> None:
    mgr = ServerListManager(persist_path=temp_persist_path)
    # Should load defaults if file does not exist
    server_list = mgr.get_current_server_list()
    assert isinstance(server_list, ByteBlasterServerList)
    assert len(server_list) > 0


def test_persistence_roundtrip(temp_persist_path: Path) -> None:
    mgr = ServerListManager(persist_path=temp_persist_path)
    # Save a custom server list
    custom_list = make_server_list(
        servers=[("foo", 1111), ("bar", 2222)],
        sat_servers=[("sat", 3333)],
    )
    mgr.save_server_list(custom_list)
    # New manager should load the same list
    mgr2 = ServerListManager(persist_path=temp_persist_path)
    loaded = mgr2.get_current_server_list()
    assert set(loaded.servers) == {("foo", 1111), ("bar", 2222)}
    assert set(loaded.sat_servers) == {("sat", 3333)}


def test_disable_persistence(temp_persist_path: Path) -> None:
    mgr = ServerListManager(persist_path=temp_persist_path, enable_persistence=False)
    # Should never write a file
    custom_list = make_server_list()
    mgr.save_server_list(custom_list)
    assert not temp_persist_path.exists()


def test_shuffle_on_load(monkeypatch: pytest.MonkeyPatch, temp_persist_path: Path) -> None:
    # Patch random.shuffle to track calls
    shuffle_calls: list[list[object]] = []

    def fake_shuffle(lst: list[object]) -> None:
        shuffle_calls.append(list(lst))

    monkeypatch.setattr("random.shuffle", fake_shuffle)
    ServerListManager(persist_path=temp_persist_path, shuffle_on_load=True)
    assert shuffle_calls  # Should have shuffled at least once


def test_get_next_server_cycles(temp_persist_path: Path) -> None:
    servers = [("a", 1), ("b", 2), ("c", 3)]
    mgr = ServerListManager(persist_path=temp_persist_path, enable_persistence=True)
    # Use update_from_frame_content to update the server list
    frame = "/ServerList/a:1|b:2|c:3"
    mgr.update_from_frame_content(frame)
    seen: list[tuple[str, int] | None] = []
    for _ in range(5):
        s = mgr.get_next_server()
        seen.append(s)
    # Should cycle through servers in order
    assert seen[:3] == servers
    assert seen[3] == servers[0]
    assert seen[4] == servers[1]


def test_reset_index(temp_persist_path: Path) -> None:
    servers = [("a", 1), ("b", 2)]
    mgr = ServerListManager(persist_path=temp_persist_path, enable_persistence=True)
    frame = "/ServerList/a:1|b:2"
    mgr.update_from_frame_content(frame)
    # Call get_next_server to increment index, then reset
    mgr.get_next_server()
    mgr.reset_index()
    # After reset, next server should be the first one
    assert mgr.get_next_server() == servers[0]


def test_update_from_frame_content_valid(temp_persist_path: Path) -> None:
    mgr = ServerListManager(persist_path=temp_persist_path, enable_persistence=True)
    frame = "/ServerList/foo:1111|bar:2222"
    mgr.update_from_frame_content(frame)
    sl = mgr.get_current_server_list()
    assert ("foo", 1111) in sl.servers
    assert ("bar", 2222) in sl.servers


def test_update_from_frame_content_empty(temp_persist_path: Path) -> None:
    mgr = ServerListManager(persist_path=temp_persist_path, enable_persistence=False)
    frame = "/ServerList/"
    mgr.update_from_frame_content(frame)
    # Should not update to empty list (should fallback to defaults)
    assert len(mgr.get_current_server_list()) > 0


def test_update_from_frame_content_invalid(temp_persist_path: Path) -> None:
    mgr = ServerListManager(persist_path=temp_persist_path, enable_persistence=False)
    with pytest.raises(ValueError, match="Unable to parse server list"):
        mgr.update_from_frame_content("not a valid frame")


def test_serialize_deserialize_roundtrip(temp_persist_path: Path) -> None:
    mgr = ServerListManager(persist_path=temp_persist_path, enable_persistence=False)
    orig = make_server_list(servers=[("x", 9)], sat_servers=[("y", 8)])
    # Use public API for serialization/deserialization if available, else test protected for coverage
    data = mgr._serialize_server_list(orig)
    restored = mgr._deserialize_server_list(data)
    assert set(restored.servers) == {("x", 9)}
    assert set(restored.sat_servers) == {("y", 8)}


def test_repr(temp_persist_path: Path) -> None:
    mgr = ServerListManager(persist_path=temp_persist_path, enable_persistence=False)
    r = repr(mgr)
    assert "ServerListManager" in r
    assert "servers=" in r
    assert "current_index=" in r


def test_parse_server_string_valid() -> None:
    # Use public API: ByteBlasterServerList.parse_server
    assert ByteBlasterServerList.parse_server("host:1234") == ("host", 1234)


def test_parse_server_string_invalid() -> None:
    # Use public API: ByteBlasterServerList.parse_server
    with pytest.raises(ValueError, match="Invalid server format"):
        ByteBlasterServerList.parse_server("noport")
    with pytest.raises(ValueError, match="Invalid port in server string"):
        ByteBlasterServerList.parse_server("host:badport")
    with pytest.raises(ValueError, match="Port out of range"):
        ByteBlasterServerList.parse_server("host:99999")
