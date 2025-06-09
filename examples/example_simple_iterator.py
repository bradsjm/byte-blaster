#!/usr/bin/env python3
"""Simple example demonstrating async iterator usage with ByteBlaster.

This example shows the basic async iterator pattern for processing ByteBlaster
data streams using modern Python 3.12+ structured concurrency patterns.
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from byteblaster import (
    ByteBlasterClient,
    ByteBlasterClientOptions,
    ByteBlasterFileManager,
    CompletedFile,
)

logger = logging.getLogger(__name__)


async def process_files_with_iterator(file_manager: ByteBlasterFileManager) -> None:
    """Process files using async iterator pattern."""
    output_dir = Path("iterator_weather_data")
    output_dir.mkdir(exist_ok=True)

    logger.info("🔄 Starting file processing with async iterator...")

    # Use async iterator pattern with structured concurrency
    async with file_manager.stream_files(max_queue_size=50) as files:
        async for completed_file in files:
            # Process each file as it arrives
            await save_file(completed_file, output_dir)


async def process_segments_with_iterator(client: ByteBlasterClient) -> None:
    """Process segments using async iterator pattern."""
    logger.info("🔍 Starting segment analysis with async iterator...")

    segment_count = 0
    file_types: dict[str, int] = {}

    # Use async iterator to process raw segments
    async with client.stream_segments(max_queue_size=100) as segments:
        async for segment in segments:
            # Skip filler data
            if segment.filename == "FILLFILE.TXT":
                continue

            segment_count += 1

            # Track file types
            file_ext = Path(segment.filename).suffix.lower() or "no_ext"
            file_types[file_ext] = file_types.get(file_ext, 0) + 1

            # Report progress
            if segment_count % 100 == 0:
                logger.info("📊 Processed %d segments", segment_count)
                logger.info("   File types: %s", dict(list(file_types.items())[:3]))


async def save_file(file: CompletedFile, output_dir: Path) -> None:
    """Save a completed file to disk."""
    output_path = output_dir / file.filename
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Simulate some async processing
        await asyncio.sleep(0.01)

        # Write file
        output_path.write_bytes(file.data)
        logger.info("✅ Saved: %s (%d bytes)", file.filename, len(file.data))

    except OSError:
        logger.exception("❌ Error saving %s", file.filename)
    except Exception:
        logger.exception("Error saving file %s", file.filename)


async def main() -> None:
    """Run the simple async iterator example."""
    # Setup logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    email = "jb@nrgup.net"

    logger.info("🚀 Simple ByteBlaster Async Iterator Example")
    logger.info("📧 Email: %s", email)
    logger.info("Press Ctrl+C to stop")

    # Create client configuration
    options = ByteBlasterClientOptions(
        email=email,
        server_list_path="servers.json",
        watchdog_timeout=30.0,
        reconnect_delay=5.0,
        connection_timeout=10.0,
    )

    # Create file manager
    file_manager = ByteBlasterFileManager(options=options)

    # Setup graceful shutdown
    shutdown_event = asyncio.Event()

    def signal_handler() -> None:
        logger.info("🛑 Shutdown signal received...")
        shutdown_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda _s, _f: signal_handler())

    try:
        # Start the client
        await file_manager.start()
        logger.info("✅ Client started with %d servers", file_manager.client.server_count)
        logger.info("📡 Waiting for data...")

        # Run async iterator processors concurrently
        async with asyncio.TaskGroup() as tg:
            # Process completed files
            tg.create_task(process_files_with_iterator(file_manager))

            # Analyze raw segments
            tg.create_task(process_segments_with_iterator(file_manager.client))

            # Wait for shutdown signal
            tg.create_task(shutdown_event.wait())

    except* KeyboardInterrupt:
        logger.info("⌨️  Keyboard interrupt received")
    except* Exception:
        logger.exception("Application error")
    finally:
        logger.info("🔄 Stopping client...")
        await file_manager.stop(shutdown_timeout=5.0)
        logger.info("✅ Client stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"💥 Fatal error: {e}")
        logger.exception("Fatal error in main")
        sys.exit(1)
