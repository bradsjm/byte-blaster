"""Protocol data models for ByteBlaster communication.

This module defines the core data structures used in the ByteBlaster protocol,
including QuickBlockTransferSegment for data blocks and ByteBlasterServerList
for server management.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import ClassVar

logger = logging.getLogger(__name__)


@dataclass
class QuickBlockTransferSegment:
    """A QuickBlockTransferSegment represents a single data block in the protocol.

    The Quick Block Transfer protocol divides messages into small pieces to allow
    interruption of large, low priority messages by messages of a more immediate
    nature. This ensures timely notification of impending severe weather events.
    """

    # Block identification
    filename: str = ""
    block_number: int = 0
    total_blocks: int = 0

    # Content and metadata
    content: bytes = field(default_factory=bytes)
    checksum: int = 0
    length: int = 0
    version: int = 1

    # Timestamps
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    received_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    # Protocol metadata
    header: str = ""
    source: str = ""

    @property
    def key(self) -> str:
        """Get unique key for this segment (filename + timestamp)."""
        return f"{self.filename}_{self.timestamp.isoformat()}"

    def __str__(self) -> str:
        """Return string representation of this segment."""
        return (
            f"[QuickBlockTransferSegment] "
            f"Filename={self.filename} "
            f"Date={self.timestamp} "
            f"Block#{self.block_number}/{self.total_blocks} "
            f"V{self.version} "
            f"Length={self.length}"
        )


@dataclass
class ByteBlasterServerList:
    """Container for ByteBlaster server lists.

    Maintains both regular servers and satellite servers, with support for
    shuffling to distribute load and updating from server-provided lists.
    """

    # Default server lists as class variables
    DEFAULT_SERVERS: ClassVar[list[str]] = [
        "emwin.weathermessage.com:2211",
        "master.weathermessage.com:2211",
        "emwin.interweather.net:1000",
        "wxmesg.upstateweather.com:2211",
    ]

    DEFAULT_SAT_SERVERS: ClassVar[list[str]] = []

    # Server list regex for parsing server list frames
    SERVER_LIST_REGEX: ClassVar[re.Pattern[str]] = re.compile(
        r"^/ServerList/(?P<ServerList>.*?)(?:\\ServerList\\/SatServers/(?P<SatServers>.*?)\\SatServers\\)?$"
    )

    # Instance attributes
    servers: list[tuple[str, int]] = field(default_factory=list)
    sat_servers: list[tuple[str, int]] = field(default_factory=list)
    received_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        """Initialize with default servers if none provided."""
        if not self.servers:
            self.servers = [self.parse_server(server) for server in self.DEFAULT_SERVERS]
        if not self.sat_servers:
            self.sat_servers = [self.parse_server(server) for server in self.DEFAULT_SAT_SERVERS]

    @staticmethod
    def parse_server(server_string: str) -> tuple[str, int]:
        """Parse server string in format 'host:port' to (host, port) tuple."""
        if ":" not in server_string:
            msg = f"Invalid server format: {server_string}. Expected 'host:port'"
            raise ValueError(msg)

        host, port_str = server_string.rsplit(":", 1)
        try:
            port = int(port_str)
        except ValueError as e:
            msg = f"Invalid port in server string: {server_string}"
            raise ValueError(msg) from e

        if port <= 0 or port > 65535:
            msg = f"Port out of range (1-65535): {port}"
            raise ValueError(msg)

        return host, port

    @classmethod
    def from_server_list_frame(cls, content: str) -> "ByteBlasterServerList":
        """Create server list from a server list frame content.

        Args:
            content: Raw server list frame content

        Returns:
            New ByteBlasterServerList instance

        Raises:
            ValueError: If content doesn't match expected format

        """
        # Handle simple server list format: /ServerList/server1|server2|server3
        if content.startswith("/ServerList/"):
            # Extract server list part
            server_list_part = content[12:]  # Remove "/ServerList/"

            # Look for end markers and clean up
            if "\\ServerList\\" in server_list_part:
                server_list_part = server_list_part.split("\\ServerList\\")[0]

            # Parse regular servers (separated by |)
            servers = []
            if server_list_part:
                server_entries = [s.strip() for s in server_list_part.split("|") if s.strip()]
                try:
                    servers = [cls.parse_server(server) for server in server_entries]
                except ValueError as e:
                    logger.warning("Failed to parse some servers: %s", e)
                    # Filter out invalid servers
                    servers: list[tuple[str, int]] = []
                    for server in server_entries:
                        try:
                            servers.append(cls.parse_server(server))
                        except ValueError:
                            logger.debug("Skipping invalid server: %s", server)

            return cls(
                servers=servers,
                sat_servers=[],
                received_at=datetime.now(UTC),
            )

        # Try original regex for full format
        match = cls.SERVER_LIST_REGEX.match(content)
        if not match:
            msg = f"Unable to parse server list: {content[:100]}..."
            raise ValueError(msg)

        # Extract server lists from regex match
        server_list_str = match.group("ServerList")
        sat_servers_str = (
            match.group("SatServers") if match.lastindex and match.lastindex >= 2 else None
        )

        # Parse regular servers (separated by |)
        servers = []
        if server_list_str:
            server_entries = [s.strip() for s in server_list_str.split("|") if s.strip()]
            servers = [cls.parse_server(server) for server in server_entries]

        # Parse satellite servers (separated by +)
        sat_servers = []
        if sat_servers_str:
            sat_entries = [s.strip() for s in sat_servers_str.split("+") if s.strip()]
            sat_servers = [cls.parse_server(server) for server in sat_entries]

        return cls(
            servers=servers,
            sat_servers=sat_servers,
            received_at=datetime.now(UTC),
        )

    def get_all_servers(self) -> list[tuple[str, int]]:
        """Get combined list of all servers (regular + satellite)."""
        return self.servers + self.sat_servers

    def __len__(self) -> int:
        """Return total number of servers."""
        return len(self.servers) + len(self.sat_servers)

    def __bool__(self) -> bool:
        """Return True if any servers are available."""
        return len(self.servers) > 0 or len(self.sat_servers) > 0


@dataclass
class ProtocolFrame:
    """Base class for protocol frames."""

    frame_type: str
    content: bytes
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class DataBlockFrame(ProtocolFrame):
    """Frame containing a data block."""

    frame_type: str = field(default="data_block", init=False)
    segment: QuickBlockTransferSegment | None = None


@dataclass
class ServerListFrame(ProtocolFrame):
    """Frame containing a server list update."""

    frame_type: str = field(default="server_list", init=False)
    server_list: ByteBlasterServerList | None = None
