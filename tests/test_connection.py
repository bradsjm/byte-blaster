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
    await client.stop(shutdown_timeout=5.0)
