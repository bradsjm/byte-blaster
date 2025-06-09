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
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from byteblaster import (
    ByteBlasterClientOptions,
    ByteBlasterFileManager,
    CompletedFile,
)

logger = logging.getLogger(__name__)


class FileSaver:
    """Example handler for saving completed files with async processing."""

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
        """Handle a completed file with async I/O."""
        output_path = self.output_dir / file.filename

        # Ensure parent directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Simulate async file processing (could be database writes, API calls, etc.)
        await asyncio.sleep(0.01)  # Simulate small processing delay

        # Write file
        try:
            output_path.write_bytes(file.data)
            self.completed_files_count += 1
            self.total_bytes_received += len(file.data)
            logger.info("✓ Saved complete file: %s (%d bytes)", output_path, len(file.data))
            if self.completed_files_count % 10 == 0:
                logger.info(
                    "Total files saved: %d, Total bytes: %.2f KB",
                    self.completed_files_count,
                    self.total_bytes_received / 1024,
                )
        except OSError:
            logger.exception("✗ Failed to save %s", output_path)


class FileValidator:
    """Example handler for validating file content concurrently."""

    def __init__(self) -> None:
        """Initialize validator."""
        self.validated_count = 0

    async def validate_file(self, file: CompletedFile) -> None:
        """Validate file content asynchronously."""
        # Simulate async validation (checksum verification, format validation, etc.)
        await asyncio.sleep(0.005)  # Simulate validation processing

        try:
            # Example validation: check if file is not empty and has reasonable size
            if len(file.data) == 0:
                logger.warning("⚠ Warning: Empty file detected: %s", file.filename)
                return

            if len(file.data) > 50 * 1024 * 1024:  # 50MB threshold
                logger.warning(
                    "⚠ Warning: Large file detected: %s (%d bytes)",
                    file.filename,
                    len(file.data),
                )

            self.validated_count += 1
            if self.validated_count % 25 == 0:
                logger.info("📋 Validated %d files", self.validated_count)

        except (OSError, ValueError):
            logger.exception("✗ Validation error for %s", file.filename)


class FileStats:
    """Example handler for collecting file statistics concurrently."""

    def __init__(self) -> None:
        """Initialize stats collector."""
        self.file_types: dict[str, int] = {}
        self.total_files = 0

    async def collect_stats(self, file: CompletedFile) -> None:
        """Collect file statistics asynchronously."""
        # Simulate async stats processing
        await asyncio.sleep(0.002)

        try:
            # Extract file extension
            file_ext = Path(file.filename).suffix.lower() or "no_ext"
            self.file_types[file_ext] = self.file_types.get(file_ext, 0) + 1
            self.total_files += 1

            # Print stats every 50 files
            if self.total_files % 50 == 0:
                logger.info("📊 File type stats: %s", dict(sorted(self.file_types.items())))

        except (OSError, ValueError):
            logger.exception("✗ Stats collection error for %s", file.filename)


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

    logger.info("ByteBlaster Example Client")
    logger.info("Email: %s", email)
    logger.info("Press Ctrl+C to stop")

    # Create multiple concurrent file handlers to demonstrate TaskGroup benefits
    file_saver = FileSaver("weather_data")
    file_validator = FileValidator()
    file_stats = FileStats()

    logger.info("Handlers configured:")
    logger.info("  - File Saver: Saves files to disk")
    logger.info("  - File Validator: Validates file content")
    logger.info("  - File Stats: Collects file statistics")
    logger.info("All handlers will process files concurrently using asyncio.TaskGroup")

    # Create client options
    options = ByteBlasterClientOptions(
        email=email,
        server_list_path="servers.json",
        watchdog_timeout=30.0,  # 30 second timeout
        reconnect_delay=5.0,  # 5 second reconnect delay
        connection_timeout=10.0,  # 10 second connection timeout
    )

    # Create file manager and subscribe multiple handlers
    # These will all execute concurrently using asyncio.TaskGroup
    file_manager = ByteBlasterFileManager(options=options)
    file_manager.subscribe(file_saver.save_file)
    file_manager.subscribe(file_validator.validate_file)
    file_manager.subscribe(file_stats.collect_stats)

    logger.info("Note: This example uses the callback-based approach.")
    logger.info("For async iterator examples, see example_async_iterators.py")

    # Setup signal handler for graceful shutdown
    shutdown_event = asyncio.Event()

    def signal_handler() -> None:
        logger.info("Shutdown signal received...")
        shutdown_event.set()

    # Register signal handlers
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda _s, _f: signal_handler())

    try:
        # Start the file manager
        await file_manager.start()

        logger.info("Client started with %d servers", file_manager.client.server_count)
        logger.info("Waiting for connection and data...")

        # Wait for shutdown signal
        await shutdown_event.wait()

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception:
        logger.exception("Error: Main loop exception")
        logger.exception("Main loop error")
    finally:
        # Stop client
        logger.info("Stopping client...")
        await file_manager.stop(shutdown_timeout=10)
        logger.info("Client stopped")
        logger.info("Final Statistics:")
        logger.info("  Files saved: %d", file_saver.completed_files_count)
        logger.info("  Files validated: %d", file_validator.validated_count)
        logger.info("  Total files processed: %d", file_stats.total_files)
        logger.info(
            "  Total bytes received: %.2f KB",
            file_saver.total_bytes_received / 1024,
        )
        logger.info("  File types: %s", dict(sorted(file_stats.file_types.items())))


def run_example() -> None:
    """Run the example using asyncio."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Exiting...")
    except Exception as e:  # noqa: BLE001
        logger.critical("Fatal error: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    run_example()
