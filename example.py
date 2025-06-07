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

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from byte_blaster import (
    ByteBlasterClientOptions,
    ByteBlasterFileManager,
    CompletedFile,
)

logger = logging.getLogger(__name__)


class FileSaver:
    """Example handler for saving completed files."""

    def __init__(self, output_dir: str = "weather_data") -> None:
        """Initialize handler with output directory.

        Args:
            output_dir: Directory to save received files

        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.completed_files_count = 0
        self.total_bytes_received = 0

    async def save_file(self, file: CompletedFile) -> None:
        """Handle a completed file."""
        output_path = self.output_dir / file.filename

        # Ensure parent directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Write file
        try:
            output_path.write_bytes(file.data)
            self.completed_files_count += 1
            self.total_bytes_received += len(file.data)
            print(f"✓ Saved complete file: {output_path} ({len(file.data)} bytes)")
            if self.completed_files_count % 10 == 0:
                print(
                    f"Total files saved: {self.completed_files_count}, "
                    f"Total bytes: {self.total_bytes_received / 1024:.2f} KB"
                )
        except OSError as e:
            print(f"✗ Failed to save {output_path}: {e}")


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

    # Create file saver
    file_saver = FileSaver("weather_data")

    # Create client options
    options = ByteBlasterClientOptions(
        email=email,
        server_list_path="servers.json",
        watchdog_timeout=30.0,  # 30 second timeout
        reconnect_delay=5.0,  # 5 second reconnect delay
        connection_timeout=10.0,  # 10 second connection timeout
    )

    # Create file manager
    file_manager = ByteBlasterFileManager(options=options)
    file_manager.subscribe(file_saver.save_file)

    # Setup signal handler for graceful shutdown
    shutdown_event = asyncio.Event()

    def signal_handler() -> None:
        print("\nShutdown signal received...")
        shutdown_event.set()

    # Register signal handlers
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda _s, _f: signal_handler())

    try:
        # Start the file manager
        await file_manager.start()

        print(f"Client started with {file_manager.client.server_count} servers")
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
        await file_manager.stop(timeout=10.0)
        print("Client stopped")
        print(f"Completed files saved: {file_saver.completed_files_count}")
        print(f"Total bytes received: {file_saver.total_bytes_received}")


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
