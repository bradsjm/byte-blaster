#!/usr/bin/env python3
"""Test script to verify ByteBlaster connection timeout functionality.

This script tests the connection timeout feature by attempting to connect to
both reachable and unreachable servers to ensure proper timeout behavior.
"""

import asyncio
import json
from pathlib import Path

import pytest

from byteblaster import ByteBlasterClient, QBTSegment
from byteblaster.client import ByteBlasterClientOptions


@pytest.mark.asyncio
async def test_connection_timeout() -> None:
    """Test connection timeout functionality."""
    # Test with a very short timeout to ensure it works
    client = ByteBlasterClient(options=ByteBlasterClientOptions(
        email="test@example.com",
        connection_timeout=2.0,  # 2 second timeout
        reconnect_delay=1.0,  # 1 second between attempts
        watchdog_timeout=10.0,  # 10 second watchdog
    ))

    # Start the client
    await client.start()

    # Let it run for a bit to test timeout behavior
    await asyncio.sleep(5.0)

    # Stop the client
    await client.stop(timeout=5.0)


@pytest.mark.asyncio
async def test_working_servers(tmp_path: Path) -> None:
    """Test connection to working servers only."""
    # Create a custom server list with only working servers
    working_servers = {
        "servers": [
            "emwin.interweather.net:1000",
            "emwin.weathermessage.com:2211",
            "master.weathermessage.com:2211",
        ],
        "sat_servers": [],
        "received_at": "2024-01-01T00:00:00Z",
        "version": "1.0",
    }

    # Save to temporary file
    test_servers_path = tmp_path / "test_servers.json"
    with test_servers_path.open("w") as f:
        json.dump(working_servers, f, indent=2)

    client = ByteBlasterClient(ByteBlasterClientOptions(
        email="test@example.com",
        server_list_path=str(test_servers_path),
        connection_timeout=10.0,
        reconnect_delay=2.0,
        watchdog_timeout=30.0,
    ))

    # Simple counter to track segments
    segment_count = 0

    def count_segments(_segment: QBTSegment):
        nonlocal segment_count
        segment_count += 1

    client.subscribe(count_segments)

    await client.start()

    # Wait for connection and some data
    await asyncio.sleep(10.0)

    await client.stop(timeout=5.0)

    assert segment_count > 0
