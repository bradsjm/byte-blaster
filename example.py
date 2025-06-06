#!/usr/bin/env python3
"""Example usage of the ByteBlaster Python client.

This script demonstrates how to use the ByteBlaster client to connect to
EMWIN servers and receive weather data using the Quick Block Transfer protocol.
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path

from byte_blaster.client import ByteBlasterClientOptions

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from byte_blaster import ByteBlasterClient, QuickBlockTransferSegment

logger = logging.getLogger(__name__)


class WeatherDataHandler:
    """Example handler for processing weather data segments."""

    def __init__(self, output_dir: str = "weather_data") -> None:
        """Initialize handler with output directory.

        Args:
            output_dir: Directory to save received files

        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.file_segments: dict[str, list[QuickBlockTransferSegment]] = {}

    async def handle_segment(self, segment: QuickBlockTransferSegment) -> None:
        """Handle received data segment.

        Args:
            segment: Received QuickBlockTransferSegment

        """
        # Skip FILLFILE.TXT - it's filler data when no real data is being transmitted
        if segment.filename == "FILLFILE.TXT":
            return

        print(f"Received: {segment.filename} block {segment.block_number}/{segment.total_blocks}")

        # Group segments by file key
        file_key = segment.key
        if file_key not in self.file_segments:
            self.file_segments[file_key] = []

        self.file_segments[file_key].append(segment)

        # Check if we have all segments for this file
        segments = self.file_segments[file_key]
        if len(segments) == segment.total_blocks:
            await self._reconstruct_file(file_key, segments)

    async def _reconstruct_file(
        self, file_key: str, segments: list[QuickBlockTransferSegment]
    ) -> None:
        """Reconstruct complete file from segments.

        Args:
            file_key: Unique file identifier
            segments: List of all segments for the file

        """
        # Sort segments by block number
        segments.sort(key=lambda s: s.block_number)

        # Combine content
        complete_data = b"".join(segment.content for segment in segments)

        # Get filename from first segment
        filename = segments[0].filename
        output_path = self.output_dir / filename

        # Ensure parent directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Write file
        try:
            output_path.write_bytes(complete_data)
            print(f"✓ Saved complete file: {output_path} ({len(complete_data)} bytes)")
        except OSError as e:
            print(f"✗ Failed to save {output_path}: {e}")

        # Clean up segments from memory
        del self.file_segments[file_key]


async def main() -> None:
    """Run the ByteBlaster example client."""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler("byteblaster.log")],
    )

    # Email for authentication (replace with your email)
    email = "jb@nrgup.net"

    print("ByteBlaster Example Client")
    print(f"Email: {email}")
    print("Press Ctrl+C to stop\n")

    # Create data handler
    handler = WeatherDataHandler("weather_data")

    # Create client
    client = ByteBlasterClient(
        ByteBlasterClientOptions(
            email=email,
            server_list_path="servers.json",
            watchdog_timeout=30.0,  # 30 second timeout
            reconnect_delay=5.0,  # 5 second reconnect delay
            connection_timeout=10.0,  # 10 second connection timeout
        )
    )

    # Subscribe to data events
    client.subscribe(handler.handle_segment)

    # Add segment counter (excluding FILLFILE.TXT)
    segment_count = 0
    fill_file_count = 0

    def count_segments(segment: QuickBlockTransferSegment) -> None:
        nonlocal segment_count, fill_file_count
        if segment.filename == "FILLFILE.TXT":
            fill_file_count += 1
        else:
            segment_count += 1
            if segment_count % 10 == 0:
                print(
                    f"Data segments received: {segment_count} (skipped {fill_file_count} fill segments)"
                )

    client.subscribe(count_segments)

    # Setup signal handler for graceful shutdown
    shutdown_event = asyncio.Event()

    def signal_handler() -> None:
        print("\nShutdown signal received...")
        shutdown_event.set()

    # Register signal handlers
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda _s, _f: signal_handler())

    try:
        # Start client
        await client.start()

        print(f"Client started with {client.server_count} servers")
        print("Waiting for connection and data...")

        # Wait for shutdown signal
        await shutdown_event.wait()

    except KeyboardInterrupt:
        print("\nKeyboard interrupt received")
    except Exception as e:
        print(f"Error: {e}")
        logger.exception("Main loop error")
    finally:
        # Stop client
        print("Stopping client...")
        await client.stop(timeout=10.0)
        print("Client stopped")
        print(f"Data segments received: {segment_count}")
        print(f"Fill segments skipped: {fill_file_count}")
        print(f"Total segments processed: {segment_count + fill_file_count}")


def run_example() -> None:
    """Run the example using asyncio."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run_example()
