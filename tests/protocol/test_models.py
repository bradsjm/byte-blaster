"""Comprehensive tests for ByteBlaster protocol models.

This module provides thorough testing coverage for all protocol data models
including QBTSegment, ByteBlasterServerList, and protocol frame classes.
Tests cover normal operation, edge cases, error conditions, and integration
scenarios to ensure robust protocol handling.
"""

from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from byteblaster.protocol.models import (
    ByteBlasterServerList,
    DataBlockFrame,
    ProtocolFrame,
    QBTSegment,
    ServerListFrame,
)


class TestQBTSegment:
    """Test cases for QBTSegment data model."""

    def test_qbt_segment_when_default_initialization_then_has_expected_defaults(self):
        """Test QBTSegment creates with proper default values."""
        # Arrange & Act
        segment = QBTSegment()

        # Assert
        assert segment.filename == ""
        assert segment.block_number == 0
        assert segment.total_blocks == 0
        assert segment.content == b""
        assert segment.checksum == 0
        assert segment.length == 0
        assert segment.version == 1
        assert segment.header == ""
        assert segment.source == ""
        assert isinstance(segment.timestamp, datetime)
        assert isinstance(segment.received_at, datetime)
        assert segment.timestamp.tzinfo is UTC
        assert segment.received_at.tzinfo is UTC

    def test_qbt_segment_when_initialized_with_values_then_stores_correctly(self):
        """Test QBTSegment properly stores provided initialization values."""
        # Arrange
        test_timestamp = datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC)
        test_content = b"test data content"

        # Act
        segment = QBTSegment(
            filename="weather_alert.txt",
            block_number=3,
            total_blocks=10,
            content=test_content,
            checksum=12345,
            length=len(test_content),
            version=2,
            timestamp=test_timestamp,
            received_at=test_timestamp,
            header="WX_ALERT",
            source="NOAA",
        )

        # Assert
        assert segment.filename == "weather_alert.txt"
        assert segment.block_number == 3
        assert segment.total_blocks == 10
        assert segment.content == test_content
        assert segment.checksum == 12345
        assert segment.length == len(test_content)
        assert segment.version == 2
        assert segment.timestamp == test_timestamp
        assert segment.received_at == test_timestamp
        assert segment.header == "WX_ALERT"
        assert segment.source == "NOAA"

    def test_qbt_segment_key_when_filename_and_timestamp_set_then_generates_correct_key(self):
        """Test key property generates correct identifier from filename and timestamp."""
        # Arrange
        test_timestamp = datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC)
        segment = QBTSegment(
            filename="Weather_Alert.TXT",
            timestamp=test_timestamp,
        )
        expected_key = "weather_alert.txt_2024-01-15t12:00:00+00:00"

        # Act
        key = segment.key

        # Assert
        assert key == expected_key

    def test_qbt_segment_key_when_empty_filename_then_uses_empty_string(self):
        """Test key property handles empty filename correctly."""
        # Arrange
        test_timestamp = datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC)
        segment = QBTSegment(filename="", timestamp=test_timestamp)
        expected_key = "_2024-01-15t12:00:00+00:00"

        # Act
        key = segment.key

        # Assert
        assert key == expected_key

    def test_qbt_segment_str_when_complete_data_then_formats_correctly(self):
        """Test __str__ method formats segment information properly."""
        # Arrange
        test_timestamp = datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC)
        segment = QBTSegment(
            filename="test_file.dat",
            block_number=5,
            total_blocks=20,
            length=1024,
            version=3,
            timestamp=test_timestamp,
        )
        expected_str = (
            "[QBTSegment] "
            "Filename=test_file.dat "
            "Date=2024-01-15 12:00:00+00:00 "
            "Block#5/20 "
            "V3 "
            "Length=1024"
        )

        # Act
        result = str(segment)

        # Assert
        assert result == expected_str

    def test_qbt_segment_str_when_default_values_then_formats_with_zeros(self):
        """Test __str__ method handles default values correctly."""
        # Arrange
        segment = QBTSegment()

        # Act
        result = str(segment)

        # Assert
        assert "[QBTSegment]" in result
        assert "Filename=" in result
        assert "Block#0/0" in result
        assert "V1" in result
        assert "Length=0" in result


class TestByteBlasterServerList:
    """Test cases for ByteBlasterServerList server management."""

    def test_server_list_when_default_initialization_then_loads_default_servers(self):
        """Test server list initializes with default servers when none provided."""
        # Arrange & Act
        server_list = ByteBlasterServerList()

        # Assert
        assert len(server_list.servers) == len(ByteBlasterServerList.DEFAULT_SERVERS)
        assert len(server_list.sat_servers) == len(ByteBlasterServerList.DEFAULT_SAT_SERVERS)
        assert isinstance(server_list.received_at, datetime)
        assert server_list.received_at.tzinfo is UTC

        # Verify default servers are parsed correctly
        expected_first_server = ("emwin.weathermessage.com", 2211)
        assert server_list.servers[0] == expected_first_server

    def test_server_list_when_custom_servers_provided_then_uses_custom_servers(self):
        """Test server list uses provided servers instead of defaults."""
        # Arrange
        custom_servers = [("test.example.com", 8080), ("backup.example.com", 9090)]
        custom_sat_servers = [("sat.example.com", 7070)]

        # Act
        server_list = ByteBlasterServerList(
            servers=custom_servers,
            sat_servers=custom_sat_servers,
        )

        # Assert
        assert server_list.servers == custom_servers
        assert server_list.sat_servers == custom_sat_servers

    @pytest.mark.parametrize(
        ("server_string", "expected_host", "expected_port"),
        [
            ("example.com:8080", "example.com", 8080),
            ("192.168.1.100:2211", "192.168.1.100", 2211),
            ("localhost:1000", "localhost", 1000),
            ("weather.gov:80", "weather.gov", 80),
            ("test-server.example.org:65535", "test-server.example.org", 65535),
            ("host.with.many.dots:1", "host.with.many.dots", 1),
        ],
    )
    def test_parse_server_when_valid_format_then_returns_host_port_tuple(
        self,
        server_string: str,
        expected_host: str,
        expected_port: int,
    ):
        """Test parse_server correctly parses valid server strings."""
        # Arrange & Act
        host, port = ByteBlasterServerList.parse_server(server_string)

        # Assert
        assert host == expected_host
        assert port == expected_port

    @pytest.mark.parametrize(
        "invalid_server_string",
        [
            "no_port_specified",
            "example.com:",
            "example.com:abc",
            "example.com:-1",
            "example.com:0",
            "example.com:65536",
            "example.com:99999",
            "",
            ":",
        ],
    )
    def test_parse_server_when_invalid_format_then_raises_value_error(
        self,
        invalid_server_string: str,
    ):
        """Test parse_server raises ValueError for invalid server strings."""
        # Arrange & Act & Assert
        with pytest.raises(ValueError, match=r"(Invalid|Port out of range)"):
            ByteBlasterServerList.parse_server(invalid_server_string)

    def test_parse_server_when_empty_host_then_accepts_format(self):
        """Test parse_server accepts empty host (e.g., ':8080')."""
        # Arrange & Act
        host, port = ByteBlasterServerList.parse_server(":8080")

        # Assert
        assert host == ""
        assert port == 8080

    def test_parse_server_when_ipv6_like_format_then_handles_correctly(self):
        """Test parse_server handles IPv6-like addresses with multiple colons."""
        # Arrange
        server_string = "2001:db8::1:8080"

        # Act
        host, port = ByteBlasterServerList.parse_server(server_string)

        # Assert
        assert host == "2001:db8::1"
        assert port == 8080

    def test_from_server_list_frame_when_simple_format_then_parses_correctly(self):
        """Test parsing simple server list frame format."""
        # Arrange
        content = "/ServerList/server1.com:2211|server2.com:2211|server3.com:1000"

        # Act
        server_list = ByteBlasterServerList.from_server_list_frame(content)

        # Assert
        assert len(server_list.servers) == 3
        assert server_list.servers[0] == ("server1.com", 2211)
        assert server_list.servers[1] == ("server2.com", 2211)
        assert server_list.servers[2] == ("server3.com", 1000)
        assert len(server_list.sat_servers) == 0

    def test_from_server_list_frame_when_simple_format_with_end_marker_then_parses_correctly(self):
        """Test parsing simple server list format with end marker."""
        # Arrange
        content = "/ServerList/server1.com:2211|server2.com:2211\\ServerList\\"

        # Act
        server_list = ByteBlasterServerList.from_server_list_frame(content)

        # Assert
        assert len(server_list.servers) == 2
        assert server_list.servers[0] == ("server1.com", 2211)
        assert server_list.servers[1] == ("server2.com", 2211)
        assert len(server_list.sat_servers) == 0

    def test_from_server_list_frame_when_empty_server_list_then_uses_defaults(self):
        """Test parsing server list frame with empty server list uses defaults via __post_init__."""
        # Arrange
        content = "/ServerList/"

        # Act
        server_list = ByteBlasterServerList.from_server_list_frame(content)

        # Assert - __post_init__ populates empty lists with defaults
        assert len(server_list.servers) == len(ByteBlasterServerList.DEFAULT_SERVERS)
        assert len(server_list.sat_servers) == len(ByteBlasterServerList.DEFAULT_SAT_SERVERS)

    def test_from_server_list_frame_when_whitespace_and_pipes_then_filters_empty(self):
        """Test parsing handles whitespace and empty entries correctly."""
        # Arrange
        content = "/ServerList/server1.com:2211| |server2.com:2211||server3.com:1000| "

        # Act
        server_list = ByteBlasterServerList.from_server_list_frame(content)

        # Assert
        assert len(server_list.servers) == 3
        assert server_list.servers[0] == ("server1.com", 2211)
        assert server_list.servers[1] == ("server2.com", 2211)
        assert server_list.servers[2] == ("server3.com", 1000)

    def test_from_server_list_frame_when_invalid_format_then_raises_value_error(self):
        """Test parsing raises ValueError for unrecognizable format."""
        # Arrange
        content = "InvalidFrameFormat"

        # Act & Assert
        with pytest.raises(ValueError, match="Unable to parse server list"):
            ByteBlasterServerList.from_server_list_frame(content)

    def test_from_server_list_frame_when_some_invalid_servers_then_filters_out_invalid(self):
        """Test parsing filters out invalid servers while keeping valid ones."""
        # Arrange
        content = "/ServerList/valid.com:2211|invalid_no_port|valid2.com:1000|invalid:99999"

        # Act
        with patch("byteblaster.protocol.models.logger") as mock_logger:
            server_list = ByteBlasterServerList.from_server_list_frame(content)

        # Assert
        assert len(server_list.servers) == 2
        assert server_list.servers[0] == ("valid.com", 2211)
        assert server_list.servers[1] == ("valid2.com", 1000)
        mock_logger.warning.assert_called()

    def test_get_all_servers_when_both_types_present_then_returns_combined_list(self):
        """Test get_all_servers returns combined list of all server types."""
        # Arrange
        regular_servers = [("server1.com", 2211), ("server2.com", 2211)]
        sat_servers = [("sat1.com", 3000), ("sat2.com", 3001)]
        server_list = ByteBlasterServerList(
            servers=regular_servers,
            sat_servers=sat_servers,
        )

        # Act
        all_servers = server_list.get_all_servers()

        # Assert
        assert len(all_servers) == 4
        assert all_servers[:2] == regular_servers
        assert all_servers[2:] == sat_servers

    def test_get_all_servers_when_initialized_with_empty_lists_then_returns_defaults(self):
        """Test get_all_servers returns default servers when initialized with empty lists."""
        # Arrange
        server_list = ByteBlasterServerList(servers=[], sat_servers=[])

        # Act
        all_servers = server_list.get_all_servers()

        # Assert - __post_init__ populates empty lists with defaults
        expected_count = len(ByteBlasterServerList.DEFAULT_SERVERS) + len(
            ByteBlasterServerList.DEFAULT_SAT_SERVERS,
        )
        assert len(all_servers) == expected_count
        assert all_servers[0] == ("emwin.weathermessage.com", 2211)

    def test_len_when_servers_present_then_returns_total_count(self):
        """Test __len__ returns total count of all servers."""
        # Arrange
        server_list = ByteBlasterServerList(
            servers=[("server1.com", 2211), ("server2.com", 2211)],
            sat_servers=[("sat1.com", 3000)],
        )

        # Act
        length = len(server_list)

        # Assert
        assert length == 3

    def test_len_when_initialized_empty_then_returns_default_count(self):
        """Test __len__ returns default server count when initialized with empty lists."""
        # Arrange
        server_list = ByteBlasterServerList(servers=[], sat_servers=[])

        # Act
        length = len(server_list)

        # Assert - __post_init__ populates empty lists with defaults
        expected_count = len(ByteBlasterServerList.DEFAULT_SERVERS) + len(
            ByteBlasterServerList.DEFAULT_SAT_SERVERS,
        )
        assert length == expected_count

    def test_bool_when_servers_present_then_returns_true(self):
        """Test __bool__ returns True when servers are available."""
        # Arrange
        server_list = ByteBlasterServerList(
            servers=[("server1.com", 2211)],
            sat_servers=[],
        )

        # Act & Assert
        assert bool(server_list) is True

    def test_bool_when_sat_servers_only_then_returns_true(self):
        """Test __bool__ returns True when only satellite servers are available."""
        # Arrange
        server_list = ByteBlasterServerList(
            servers=[],
            sat_servers=[("sat1.com", 3000)],
        )

        # Act & Assert
        assert bool(server_list) is True

    def test_bool_when_initialized_empty_then_returns_true_due_to_defaults(self):
        """Test __bool__ returns True when initialized empty due to default server population."""
        # Arrange
        server_list = ByteBlasterServerList(servers=[], sat_servers=[])

        # Act & Assert - __post_init__ populates with defaults, so not empty
        assert bool(server_list) is True

    def test_server_list_when_explicit_empty_initialization_bypasses_defaults(self):
        """Test that we can create truly empty server list by bypassing __post_init__."""
        # Arrange - Create instance with non-empty lists, then clear them to bypass __post_init__
        server_list = ByteBlasterServerList(
            servers=[("temp.com", 1000)],
            sat_servers=[("temp_sat.com", 2000)],
        )
        # Clear after initialization to test empty behavior
        server_list.servers = []
        server_list.sat_servers = []

        # Act & Assert
        assert len(server_list) == 0
        assert bool(server_list) is False
        assert server_list.get_all_servers() == []


class TestProtocolFrame:
    """Test cases for ProtocolFrame base class."""

    def test_protocol_frame_when_initialized_then_stores_values_correctly(self):
        """Test ProtocolFrame stores initialization values properly."""
        # Arrange
        test_timestamp = datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC)
        test_content = b"test frame content"

        # Act
        frame = ProtocolFrame(
            frame_type="test_frame",
            content=test_content,
            timestamp=test_timestamp,
        )

        # Assert
        assert frame.frame_type == "test_frame"
        assert frame.content == test_content
        assert frame.timestamp == test_timestamp

    def test_protocol_frame_when_no_timestamp_then_uses_current_time(self):
        """Test ProtocolFrame uses current UTC time when timestamp not provided."""
        # Arrange & Act
        frame = ProtocolFrame(frame_type="test", content=b"data")

        # Assert
        assert isinstance(frame.timestamp, datetime)
        assert frame.timestamp.tzinfo is UTC


class TestDataBlockFrame:
    """Test cases for DataBlockFrame specialized frame type."""

    def test_data_block_frame_when_initialized_then_has_correct_frame_type(self):
        """Test DataBlockFrame automatically sets correct frame type."""
        # Arrange & Act
        frame = DataBlockFrame(content=b"block data")

        # Assert
        assert frame.frame_type == "data_block"
        assert frame.content == b"block data"
        assert frame.segment is None

    def test_data_block_frame_when_segment_provided_then_stores_segment(self):
        """Test DataBlockFrame properly stores attached QBT segment."""
        # Arrange
        segment = QBTSegment(filename="test.dat", block_number=1)

        # Act
        frame = DataBlockFrame(content=b"data", segment=segment)

        # Assert
        assert frame.segment is segment
        assert frame.frame_type == "data_block"

    def test_data_block_frame_when_inherits_from_protocol_frame_then_has_base_attributes(self):
        """Test DataBlockFrame inherits ProtocolFrame attributes correctly."""
        # Arrange & Act
        frame = DataBlockFrame(content=b"test data")

        # Assert
        assert hasattr(frame, "timestamp")
        assert isinstance(frame.timestamp, datetime)
        assert frame.timestamp.tzinfo is UTC


class TestServerListFrame:
    """Test cases for ServerListFrame specialized frame type."""

    def test_server_list_frame_when_initialized_then_has_correct_frame_type(self):
        """Test ServerListFrame automatically sets correct frame type."""
        # Arrange & Act
        frame = ServerListFrame(content=b"server list data")

        # Assert
        assert frame.frame_type == "server_list"
        assert frame.content == b"server list data"
        assert frame.server_list is None

    def test_server_list_frame_when_server_list_provided_then_stores_server_list(self):
        """Test ServerListFrame properly stores attached server list."""
        # Arrange
        server_list = ByteBlasterServerList()

        # Act
        frame = ServerListFrame(content=b"data", server_list=server_list)

        # Assert
        assert frame.server_list is server_list
        assert frame.frame_type == "server_list"

    def test_server_list_frame_when_inherits_from_protocol_frame_then_has_base_attributes(self):
        """Test ServerListFrame inherits ProtocolFrame attributes correctly."""
        # Arrange & Act
        frame = ServerListFrame(content=b"test data")

        # Assert
        assert hasattr(frame, "timestamp")
        assert isinstance(frame.timestamp, datetime)
        assert frame.timestamp.tzinfo is UTC


@pytest.fixture
def sample_qbt_segment():
    """Fixture providing a sample QBT segment for testing."""
    return QBTSegment(
        filename="sample_weather.dat",
        block_number=5,
        total_blocks=10,
        content=b"Sample weather data content",
        checksum=54321,
        length=27,
        version=2,
        header="WEATHER_DATA",
        source="NOAA_WX",
    )


@pytest.fixture
def sample_server_list():
    """Fixture providing a sample server list for testing."""
    return ByteBlasterServerList(
        servers=[("primary.weather.gov", 2211), ("backup.weather.gov", 2211)],
        sat_servers=[("sat.weather.gov", 3000)],
    )


class TestIntegration:
    """Integration tests for protocol model interactions."""

    def test_data_block_frame_with_qbt_segment_integration(self, sample_qbt_segment: QBTSegment):
        """Test DataBlockFrame and QBTSegment work together correctly."""
        # Arrange
        frame_content = b"QBT segment frame data"

        # Act
        frame = DataBlockFrame(content=frame_content, segment=sample_qbt_segment)

        # Assert
        assert frame.segment
        assert frame.segment.filename == "sample_weather.dat"
        assert frame.segment.block_number == 5
        assert frame.content == frame_content
        assert frame.frame_type == "data_block"

    def test_server_list_frame_with_server_list_integration(
        self, sample_server_list: ByteBlasterServerList
    ):
        """Test ServerListFrame and ByteBlasterServerList work together correctly."""
        # Arrange
        frame_content = b"Server list frame data"

        # Act
        frame = ServerListFrame(content=frame_content, server_list=sample_server_list)

        # Assert
        assert frame.server_list
        assert len(frame.server_list) == 3
        assert frame.server_list.get_all_servers()[0] == ("primary.weather.gov", 2211)
        assert frame.content == frame_content
        assert frame.frame_type == "server_list"

    def test_server_list_parsing_and_frame_creation_integration(self):
        """Test complete workflow from server list parsing to frame creation."""
        server_list_content = "/ServerList/wx1.gov:2211|wx2.gov:2211"

        # Act
        parsed_servers = ByteBlasterServerList.from_server_list_frame(server_list_content)
        frame = ServerListFrame(
            content=server_list_content.encode(),
            server_list=parsed_servers,
        )

        # Assert
        assert frame.server_list
        assert len(frame.server_list.servers) == 2
        assert frame.server_list.servers[0] == ("wx1.gov", 2211)
        assert frame.server_list.servers[1] == ("wx2.gov", 2211)
        assert frame.frame_type == "server_list"
