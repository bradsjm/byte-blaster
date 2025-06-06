#!/usr/bin/env python3
"""Test script to verify ByteBlaster connection timeout functionality.

This script tests the connection timeout feature by attempting to connect to
both reachable and unreachable servers to ensure proper timeout behavior.
"""

import asyncio
import logging
import sys
import time
from pathlib import Path

from byte_blaster.client import ByteBlasterClientOptions

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from byte_blaster import ByteBlasterClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


async def test_connection_timeout() -> None:
    """Test connection timeout functionality."""
    print("Testing ByteBlaster connection timeout...")

    # Test with a very short timeout to ensure it works
    client = ByteBlasterClient(options=ByteBlasterClientOptions(
        email="test@example.com",
        connection_timeout=2.0,  # 2 second timeout
        reconnect_delay=1.0,  # 1 second between attempts
        watchdog_timeout=10.0,  # 10 second watchdog
        )
    )

    print(f"Client configured with {client.server_count} servers")
    print("Testing connection timeout behavior...")

    # Start the client
    start_time = time.time()

    try:
        await client.start()

        # Let it run for a bit to test timeout behavior
        await asyncio.sleep(15.0)

    except KeyboardInterrupt:
        print("\nTest interrupted")
    finally:
        # Stop the client
        await client.stop(timeout=5.0)

    elapsed = time.time() - start_time
    print(f"Test completed in {elapsed:.1f} seconds")


async def test_working_servers() -> None:
    """Test connection to working servers only."""
    print("\nTesting connection to working servers only...")

    # Create a custom server list with only working servers
    import json
    from pathlib import Path

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
    test_servers_path = Path("test_servers.json")
    with test_servers_path.open("w") as f:
        json.dump(working_servers, f, indent=2)

    try:
        client = ByteBlasterClient(ByteBlasterClientOptions(
            email="test@example.com",
            server_list_path="test_servers.json",
            connection_timeout=10.0,
            reconnect_delay=2.0,
            watchdog_timeout=30.0,
        ))

        print(f"Client configured with {client.server_count} working servers")

        # Simple counter to track segments
        segment_count = 0

        def count_segments(_segment):
            nonlocal segment_count
            segment_count += 1
            if segment_count % 5 == 0:
                print(f"Received {segment_count} segments")

        client.subscribe(count_segments)

        start_time = time.time()

        await client.start()
        print("Client started, waiting for connection...")

        # Wait for connection and some data
        await asyncio.sleep(30.0)

        elapsed = time.time() - start_time
        print(f"Connected for {elapsed:.1f} seconds, received {segment_count} segments")

    except Exception as e:
        logger.exception("Error in working servers test: %s", e)
    finally:
        await client.stop(timeout=5.0)
        # Clean up test file
        if test_servers_path.exists():
            test_servers_path.unlink()


async def main() -> None:
    """Run connection tests."""
    print("ByteBlaster Connection Test")
    print("=" * 50)

    # Test 1: Connection timeout with mixed servers
    await test_connection_timeout()

    # Test 2: Connection to working servers only
    await test_working_servers()

    print("\nAll tests completed!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"Test failed: {e}")
        sys.exit(1)
