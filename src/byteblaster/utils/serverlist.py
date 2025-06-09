# pyright: reportPrivateUsage=none
"""Server list management with persistence and failover support.

This module provides the ServerListManager class for handling ByteBlaster server
lists, including loading from persistent storage, cycling through servers for
failover, and updating with new server lists received from the protocol.
"""

import json
import logging
import random
from pathlib import Path
from typing import Any

from byteblaster.protocol.models import ByteBlasterServerList

logger = logging.getLogger(__name__)


class ServerListManager:
    """Manages ByteBlaster server lists with persistence and failover.

    This class handles:
    - Loading server lists from persistent storage
    - Saving updated server lists
    - Providing next server for connection attempts
    - Falling back to defaults when persistence fails
    """

    def __init__(
        self,
        persist_path: str | Path = "servers.json",
        *,
        shuffle_on_load: bool = True,
        enable_persistence: bool = True,
    ) -> None:
        """Initialize server list manager.

        Args:
            persist_path: Path to persistence file
            shuffle_on_load: Whether to shuffle servers when loading
            enable_persistence: Whether to enable persistence (for testing)

        """
        self._persist_path = Path(persist_path)
        self._shuffle_on_load = shuffle_on_load
        self._enable_persistence = enable_persistence
        self._current_index = 0
        self._server_list = self._load_server_list()

    def _load_server_list(self) -> ByteBlasterServerList:
        """Load server list from persistence or use defaults.

        Returns:
            ByteBlasterServerList instance

        """
        if not self._enable_persistence:
            return self._create_default_server_list()

        if not self._persist_path.exists():
            logger.info("No server list file found at %s, using defaults", self._persist_path)
            return self._create_default_server_list()

        try:
            with self._persist_path.open("r", encoding="utf-8") as f:
                data = json.load(f)

            server_list = self._deserialize_server_list(data)
            logger.info("Loaded %d servers from %s", len(server_list), self._persist_path)

            if self._shuffle_on_load:
                self._shuffle_servers(server_list)
                logger.debug("Shuffled server order for load distribution")

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning("Failed to load server list from %s: %s", self._persist_path, e)
            logger.info("Using default server list")
            return self._create_default_server_list()

        return server_list

    def _create_default_server_list(self) -> ByteBlasterServerList:
        """Create server list with default servers.

        Returns:
            ByteBlasterServerList with default servers

        """
        server_list = ByteBlasterServerList()
        if self._shuffle_on_load:
            self._shuffle_servers(server_list)
        return server_list

    @staticmethod
    def _shuffle_servers(server_list: ByteBlasterServerList) -> None:
        """Shuffle servers in place for load distribution.

        Args:
            server_list: Server list to shuffle

        """
        random.shuffle(server_list.servers)
        random.shuffle(server_list.sat_servers)

    def _serialize_server_list(self, server_list: ByteBlasterServerList) -> dict[str, Any]:
        """Serialize server list to JSON-compatible format.

        Args:
            server_list: Server list to serialize

        Returns:
            Dictionary ready for JSON serialization

        """
        return {
            "servers": [f"{host}:{port}" for host, port in server_list.servers],
            "sat_servers": [f"{host}:{port}" for host, port in server_list.sat_servers],
            "received_at": server_list.received_at.isoformat(),
            "version": "1.0",
        }

    def _deserialize_server_list(self, data: dict[str, Any]) -> ByteBlasterServerList:
        """Deserialize server list from JSON data.

        Args:
            data: JSON data dictionary

        Returns:
            ByteBlasterServerList instance

        Raises:
            KeyError: If required keys are missing
            ValueError: If data format is invalid

        """
        if "servers" not in data:
            msg = "Missing 'servers' key in server list data"
            raise KeyError(msg)

        try:
            servers = [self._parse_server_string(server_str) for server_str in data["servers"]]
        except (ValueError, TypeError) as e:
            msg = f"Invalid server format in data: {e}"
            raise ValueError(msg) from e

        sat_servers = []
        if "sat_servers" in data:
            try:
                sat_servers = [
                    self._parse_server_string(server_str) for server_str in data["sat_servers"]
                ]
            except (ValueError, TypeError) as e:
                msg = f"Invalid satellite server format in data: {e}"
                raise ValueError(msg) from e

        return ByteBlasterServerList(
            servers=servers,
            sat_servers=sat_servers,
        )

    def save_server_list(self, server_list: ByteBlasterServerList) -> None:
        """Save server list to persistent storage.

        Args:
            server_list: Server list to save

        """
        if not self._enable_persistence:
            logger.debug("Persistence disabled, not saving server list")
            return

        try:
            # Ensure parent directory exists
            self._persist_path.parent.mkdir(parents=True, exist_ok=True)

            # Serialize data
            data = self._serialize_server_list(server_list)

            # Write to temporary file first for atomic operation
            temp_path = self._persist_path.with_suffix(".tmp")
            with temp_path.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            # Atomic rename to final file
            temp_path.replace(self._persist_path)

            self._server_list = server_list
            self._current_index = 0  # Reset index when list changes

            logger.info("Saved %d servers to %s", len(server_list), self._persist_path)

        except (OSError, ValueError):
            logger.exception("Failed to save server list to %s", self._persist_path)

    def get_next_server(self) -> tuple[str, int] | None:
        """Get next server for connection attempt.

        Returns:
            Tuple of (host, port) or None if no servers available

        """
        all_servers = self._server_list.get_all_servers()
        if not all_servers:
            logger.warning("No servers available")
            return None

        if self._current_index >= len(all_servers):
            self._current_index = 0
            logger.debug("Wrapped around to first server")

        server = all_servers[self._current_index]
        self._current_index += 1

        logger.debug(
            "Selected server: %s:%d (index %d)",
            server[0],
            server[1],
            self._current_index - 1,
        )
        return server

    def reset_index(self) -> None:
        """Reset server index to start from beginning."""
        self._current_index = 0
        logger.debug("Reset server index to 0")

    def get_current_server_list(self) -> ByteBlasterServerList:
        """Get current server list.

        Returns:
            Current ByteBlasterServerList instance

        """
        return self._server_list

    def get_server_count(self) -> int:
        """Get total number of available servers.

        Returns:
            Total server count

        """
        return len(self._server_list)

    def update_from_frame_content(self, content: str) -> None:
        """Update server list from protocol frame content.

        Args:
            content: Raw server list frame content

        Raises:
            ValueError: If content format is invalid

        """
        try:
            new_server_list = ByteBlasterServerList.from_server_list_frame(content)

            if len(new_server_list) == 0:
                logger.warning("Received empty server list, ignoring update")
                return

            logger.info(
                "Received server list update: %d servers, %d satellite servers",
                len(new_server_list.servers),
                len(new_server_list.sat_servers),
            )

            self.save_server_list(new_server_list)

        except ValueError:
            logger.exception("Failed to parse server list frame")
            raise

    def __len__(self) -> int:
        """Return total number of servers."""
        return len(self._server_list)

    def __bool__(self) -> bool:
        """Return True if any servers are available."""
        return bool(self._server_list)

    def _parse_server_string(self, server_string: str) -> tuple[str, int]:
        """Parse server string in format 'host:port' to (host, port) tuple."""
        return ByteBlasterServerList.parse_server(server_string)

    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"ServerListManager("
            f"servers={len(self._server_list.servers)}, "
            f"sat_servers={len(self._server_list.sat_servers)}, "
            f"current_index={self._current_index})"
        )
