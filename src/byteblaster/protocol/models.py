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
class QBTSegment:
    """Represents a single data block in the Quick Block Transfer (QBT) protocol.

    The QBTSegment class encapsulates all metadata and content for one block in the QBT
    protocol, which divides large messages into manageable segments to enable prioritized
    message delivery. This segmentation mechanism allows high-priority weather alerts to
    interrupt lower-priority bulk data transfers, ensuring critical weather information
    reaches recipients without delay.

    Each segment contains comprehensive metadata including block identification (filename,
    block number, total blocks), content validation (checksum, length), protocol versioning,
    and timing information for delivery tracking and debugging. The class provides utilities
    for generating unique identifiers and human-readable representations of segments.

    The segment structure supports the ByteBlaster protocol's requirement for reliable,
    ordered delivery of weather data while maintaining the ability to interrupt
    transmissions for emergency notifications.
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
        """Generate a unique identifier for this segment based on filename and timestamp.

        Creates a composite key by combining the segment's filename with its ISO-formatted
        timestamp, providing a unique identifier that can be used for tracking, caching,
        or deduplication purposes. The timestamp is formatted in ISO 8601 standard to
        ensure consistent string representation across different systems and time zones.

        Returns:
            A string in the format "filename_timestamp" where timestamp is ISO-formatted.

        """
        return f"{self.filename}_{self.timestamp.isoformat()}".lower()

    def __str__(self) -> str:
        """Generate a human-readable string representation of this QBT segment.

        Formats the segment's key metadata into a concise, readable format suitable for
        logging, debugging, and monitoring purposes. The string includes the filename,
        timestamp, block position within the sequence, protocol version, and content
        length to provide comprehensive segment identification at a glance.

        Returns:
            A formatted string containing segment identification and metadata.

        """
        return (
            f"[QBTSegment] "
            f"Filename={self.filename} "
            f"Date={self.timestamp} "
            f"Block#{self.block_number}/{self.total_blocks} "
            f"V{self.version} "
            f"Length={self.length}"
        )


@dataclass
class ByteBlasterServerList:
    """Manages ByteBlaster server connection endpoints for weather data distribution.

    The ByteBlasterServerList class maintains comprehensive server configuration for
    the ByteBlaster protocol, supporting both terrestrial and satellite server endpoints.
    This class handles server discovery, validation, and management for reliable weather
    data distribution across multiple connection points.

    The server list supports dynamic updates from server-provided configurations,
    enabling automatic failover and load distribution. It maintains separate collections
    for regular terrestrial servers and satellite servers, allowing the protocol to
    intelligently select appropriate connection endpoints based on availability and
    network conditions.

    Key responsibilities include parsing server list frames received from the network,
    validating server endpoint formats, providing fallback defaults, and offering
    unified access to all available servers. The class ensures robust server management
    with proper error handling for malformed server configurations.
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
        r"^/ServerList/(?P<ServerList>.*?)(?:\\ServerList\\/SatServers/(?P<SatServers>.*?)\\SatServers\\)?$",
    )

    # Instance attributes
    servers: list[tuple[str, int]] = field(default_factory=list)
    sat_servers: list[tuple[str, int]] = field(default_factory=list)
    received_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        """Initialize server lists with default endpoints when no servers are provided.

        Performs post-initialization setup by populating empty server lists with default
        server configurations. This ensures the server list always contains valid
        connection endpoints, providing reliable fallback options when dynamic server
        discovery fails or when initializing without explicit server configuration.

        The method parses default server strings into validated (host, port) tuples,
        ensuring all default servers meet the required format standards before adding
        them to the active server collections.
        """
        if not self.servers:
            self.servers = [self.parse_server(server) for server in self.DEFAULT_SERVERS]
        if not self.sat_servers:
            self.sat_servers = [self.parse_server(server) for server in self.DEFAULT_SAT_SERVERS]

    @staticmethod
    def parse_server(server_string: str) -> tuple[str, int]:
        """Parse and validate server endpoint string into host and port components.

        Converts server strings in the standard 'host:port' format into validated
        (host, port) tuples suitable for network connections. The method performs
        comprehensive validation including format checking, port number validation,
        and range verification to ensure all parsed servers represent valid network
        endpoints.

        The parser uses right-side string splitting to handle IPv6 addresses and
        hostnames containing colons correctly, ensuring robust parsing across
        different address formats.

        Args:
            server_string: Server endpoint in format 'hostname:port' or 'ip:port'.

        Returns:
            A tuple containing (hostname, port) where port is validated integer.

        Raises:
            ValueError: If server_string format is invalid, port is non-numeric,
                       or port number is outside valid range (1-65535).

        """
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
        r"""Parse server list frame content and create a new server list instance.

        Processes server list frames received from ByteBlaster servers, supporting both
        simplified and full server list formats. The method handles dynamic server
        configuration updates by parsing structured frame content and extracting
        terrestrial and satellite server endpoints.

        The parser supports two frame formats:
        1. Simple format: '/ServerList/server1|server2|server3'
        2. Full format: '/ServerList/servers\\ServerList\\/SatServers/satellites\\SatServers\\'

        For the simple format, servers are pipe-delimited and only terrestrial servers
        are specified. For the full format, the method uses regex parsing to extract
        both terrestrial servers (pipe-delimited) and satellite servers (plus-delimited).

        The method includes robust error handling, logging warnings for parsing failures
        while filtering out invalid server entries to maintain service availability
        with partial server lists.

        Args:
            content: Raw server list frame content containing server endpoints.

        Returns:
            New ByteBlasterServerList instance populated with parsed servers.

        Raises:
            ValueError: If content format is unrecognizable or completely unparseable.

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
        """Retrieve unified list of all available server endpoints.

        Combines terrestrial and satellite server collections into a single list,
        providing a comprehensive view of all available connection endpoints for
        the ByteBlaster protocol. This unified list enables connection logic to
        iterate through all servers regardless of type, supporting automatic
        failover and load distribution strategies.

        Returns:
            List of (hostname, port) tuples for all configured servers.

        """
        return self.servers + self.sat_servers

    def __len__(self) -> int:
        """Calculate total count of all configured servers.

        Provides the combined count of terrestrial and satellite servers,
        useful for monitoring server availability, load balancing decisions,
        and configuration validation.

        Returns:
            Total number of configured server endpoints.

        """
        return len(self.servers) + len(self.sat_servers)

    def __bool__(self) -> bool:
        """Determine if any server endpoints are available for connections.

        Evaluates server list availability by checking for the presence of either
        terrestrial or satellite servers. This boolean evaluation enables conditional
        logic for connection establishment and helps prevent connection attempts
        when no servers are configured.

        Returns:
            True if at least one server endpoint is configured, False otherwise.

        """
        return len(self.servers) > 0 or len(self.sat_servers) > 0


@dataclass
class ProtocolFrame:
    """Base class for all ByteBlaster protocol frame types.

    ProtocolFrame provides the foundational structure for all frame types in the
    ByteBlaster protocol, establishing common attributes and behaviors shared across
    different frame categories. This base class ensures consistent frame identification,
    content handling, and timestamp tracking throughout the protocol implementation.

    The frame structure supports protocol extensibility by providing a standardized
    foundation that specialized frame types can extend with additional functionality
    while maintaining compatibility with core protocol handling logic.
    """

    frame_type: str
    content: bytes
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class DataBlockFrame(ProtocolFrame):
    """Protocol frame specialized for carrying QBT data block segments.

    DataBlockFrame extends the base ProtocolFrame to handle data block transmissions
    in the ByteBlaster protocol. This frame type encapsulates QBT segments, providing
    structured transport for weather data blocks while maintaining protocol-level
    metadata and timing information.

    The frame automatically identifies itself as a data block type and provides
    optional segment attachment for parsed QBT content, enabling the protocol
    stack to efficiently process and route data blocks through the system.
    """

    frame_type: str = field(default="data_block", init=False)
    segment: QBTSegment | None = None


@dataclass
class ServerListFrame(ProtocolFrame):
    """Protocol frame specialized for carrying server configuration updates.

    ServerListFrame extends the base ProtocolFrame to handle dynamic server list
    updates in the ByteBlaster protocol. This frame type enables servers to
    distribute updated endpoint configurations to clients, supporting automatic
    server discovery and load balancing across the network.

    The frame automatically identifies itself as a server list type and provides
    optional server list attachment for parsed configuration data, enabling the
    protocol stack to efficiently update client-side server configurations
    without manual intervention.
    """

    frame_type: str = field(default="server_list", init=False)
    server_list: ByteBlasterServerList | None = None
