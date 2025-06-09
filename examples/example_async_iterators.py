#!/usr/bin/env python3
"""Enhanced example demonstrating async iterator patterns with ByteBlaster.

This script shows how to use both callback-based and async iterator approaches
for processing ByteBlaster data streams, highlighting modern Python 3.12+ patterns
with structured concurrency.
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import builtins

from byteblaster import (
    ByteBlasterClient,
    ByteBlasterClientOptions,
    ByteBlasterFileManager,
    CompletedFile,
    QBTSegment,
)

logger = logging.getLogger(__name__)


class AsyncFileProcessor:
    """Example async file processor using modern patterns."""

    def __init__(self, output_dir: str = "async_weather_data") -> None:
        """Initialize processor with output directory."""
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.processed_count = 0
        self.total_bytes = 0

    async def process_file_stream(self, file_manager: ByteBlasterFileManager) -> None:
        """Process files using async iterator pattern with structured concurrency."""
        logger.info("🔄 Starting async iterator file processing...")

        async with file_manager.stream_files(max_queue_size=50) as files:
            async for completed_file in files:
                await self._process_single_file(completed_file)

    async def _process_single_file(self, file: CompletedFile) -> None:
        """Process a single completed file with async I/O."""
        output_path = self.output_dir / file.filename
        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            # Simulate async processing (validation, transformation, etc.)
            await asyncio.sleep(0.01)

            # Write file asynchronously
            output_path.write_bytes(file.data)

            self.processed_count += 1
            self.total_bytes += len(file.data)

            if self.processed_count % 10 == 0:
                logger.info(
                    "📁 Async processor: %d files, %.1f KB total",
                    self.processed_count,
                    self.total_bytes / 1024,
                )

        except Exception:
            logger.exception("Error processing file %s", file.filename)


class SegmentAnalyzer:
    """Example segment analyzer using async iterator pattern."""

    def __init__(self) -> None:
        """Initialize analyzer."""
        self.segment_count = 0
        self.file_types: dict[str, int] = {}
        self.large_files: list[str] = []

    async def analyze_segments(self, client: ByteBlasterClient) -> None:
        """Analyze segments using async iterator with filtering and batching."""
        logger.info("🔍 Starting async iterator segment analysis...")

        async with client.stream_segments(max_queue_size=200) as segments:
            batch: list[QBTSegment] = []
            async for segment in segments:
                # Filter out filler data
                if segment.filename == "FILLFILE.TXT":
                    continue

                batch.append(segment)
                self.segment_count += 1

                # Process in batches for efficiency
                if len(batch) >= 20:
                    await self._analyze_batch(batch)
                    batch.clear()

            # Process remaining segments
            if batch:
                await self._analyze_batch(batch)

    async def _analyze_batch(self, segments: list[QBTSegment]) -> None:
        """Analyze a batch of segments concurrently."""
        async with asyncio.TaskGroup() as tg:
            for segment in segments:
                tg.create_task(self._analyze_segment(segment))

    async def _analyze_segment(self, segment: QBTSegment) -> None:
        """Analyze individual segment."""
        # Simulate async analysis
        await asyncio.sleep(0.001)

        # Track file types
        file_ext = Path(segment.filename).suffix.lower() or "no_ext"
        self.file_types[file_ext] = self.file_types.get(file_ext, 0) + 1

        # Track large files (estimate from first segment)
        if segment.block_number == 1:
            estimated_size = len(segment.content) * segment.total_blocks
            if estimated_size > 100_000:  # 100KB threshold
                self.large_files.append(segment.filename)

        if self.segment_count % 100 == 0:
            logger.info("🔬 Analyzed %d segments", self.segment_count)


class ConcurrentPatternDemo:
    """Demonstrates concurrent processing with different patterns."""

    async def run_callback_vs_iterator_demo(self, file_manager: ByteBlasterFileManager) -> None:
        """Compare callback vs iterator patterns running concurrently."""
        logger.info("🚀 Running concurrent callback vs iterator demo...")

        # Callback-based handlers
        callback_saver = CallbackFileSaver("callback_files")
        callback_validator = CallbackFileValidator()

        # Subscribe callback handlers
        file_manager.subscribe(callback_saver.save_file)
        file_manager.subscribe(callback_validator.validate_file)

        # Async iterator processor
        iterator_processor = AsyncFileProcessor("iterator_files")

        # Run both patterns concurrently
        async with asyncio.TaskGroup() as tg:
            # Iterator-based processing
            tg.create_task(iterator_processor.process_file_stream(file_manager))

            # Segment analysis using iterators
            analyzer = SegmentAnalyzer()
            tg.create_task(analyzer.analyze_segments(file_manager.client))

            # Monitor and report stats
            tg.create_task(self._monitor_progress(callback_saver, iterator_processor, analyzer))

    async def _monitor_progress(
        self,
        callback_saver: "CallbackFileSaver",
        iterator_processor: "AsyncFileProcessor",
        analyzer: "SegmentAnalyzer",
    ) -> None:
        """Monitor and report progress from both patterns."""
        while True:
            await asyncio.sleep(10)  # Report every 10 seconds
            logger.info("\n📊 Progress Report:")
            logger.info("  Callback files saved: %d", callback_saver.saved_count)
            logger.info("  Iterator files processed: %d", iterator_processor.processed_count)
            logger.info("  Segments analyzed: %d", analyzer.segment_count)
            if analyzer.file_types:
                msg = f"  File types seen: {dict(list(analyzer.file_types.items())[:5])}"
                logger.info(msg)


class CallbackFileSaver:
    """Traditional callback-based file saver for comparison."""

    def __init__(self, output_dir: str) -> None:
        """Initialize callback saver."""
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.saved_count = 0

    async def save_file(self, file: CompletedFile) -> None:
        """Save file using callback pattern."""
        output_path = self.output_dir / file.filename
        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            output_path.write_bytes(file.data)
            self.saved_count += 1
        except Exception:
            logger.exception("Callback saver error")


class CallbackFileValidator:
    """Traditional callback-based validator for comparison."""

    def __init__(self) -> None:
        """Initialize callback validator."""
        self.validated_count = 0

    async def validate_file(self, file: CompletedFile) -> None:
        """Validate file using callback pattern."""
        await asyncio.sleep(0.005)  # Simulate validation

        # Simple validation
        if len(file.data) > 0:
            self.validated_count += 1


async def demonstrate_reactive_patterns(client: ByteBlasterClient) -> None:
    """Demonstrate reactive programming patterns with async iterators."""
    logger.info("🌊 Demonstrating reactive patterns...")

    async with asyncio.TaskGroup() as tg:
        # Pattern 1: Filter and transform
        tg.create_task(filter_and_transform_segments(client))

        # Pattern 2: Batch processing
        tg.create_task(batch_process_segments(client))

        # Pattern 3: Concurrent stream processing
        tg.create_task(concurrent_stream_processing(client))


async def filter_and_transform_segments(client: ByteBlasterClient) -> None:
    """Filter and transform segment streams."""
    logger.info("🔧 Pattern 1: Filter and transform...")

    async with client.stream_segments() as segments:
        # Create a filtered stream of only text files
        text_segments: list[QBTSegment] = []
        async for segment in segments:
            if segment.filename.endswith((".txt", ".TXT")):
                text_segments.append(segment)

                # Process when we have 5 text segments
                if len(text_segments) >= 5:
                    await process_text_batch(text_segments)
                    text_segments.clear()


async def batch_process_segments(client: ByteBlasterClient) -> None:
    """Batch process segments with timeouts."""
    logger.info("⏱️  Pattern 2: Batch processing with timeout...")

    async with client.stream_segments() as segments:
        batch: list[QBTSegment] = []

        async for segment in segments:
            batch.append(segment)

            # Process batch when full or after timeout
            if len(batch) >= 10:
                await process_batch_with_timeout(batch)
                batch.clear()


async def concurrent_stream_processing(client: ByteBlasterClient) -> None:
    """Process multiple streams concurrently."""
    logger.info("🔀 Pattern 3: Concurrent stream processing...")

    # Create multiple concurrent stream processors
    async with asyncio.TaskGroup() as tg:
        # Stream 1: Priority segments (alerts, warnings)
        tg.create_task(process_priority_segments(client))

        # Stream 2: Regular data segments
        tg.create_task(process_regular_segments(client))


async def process_priority_segments(client: ByteBlasterClient) -> None:
    """Process high-priority segments."""
    async with client.stream_segments(max_queue_size=50) as segments:
        async for segment in segments:
            if any(
                keyword in segment.filename.upper() for keyword in ["ALERT", "WARNING", "URGENT"]
            ):
                logger.info("🚨 Priority: %s", segment.filename)
                await asyncio.sleep(0.001)  # Quick processing


async def process_regular_segments(client: ByteBlasterClient) -> None:
    """Process regular segments."""
    count = 0
    async with client.stream_segments(max_queue_size=100) as segments:
        async for segment in segments:
            if not any(
                keyword in segment.filename.upper() for keyword in ["ALERT", "WARNING", "URGENT"]
            ):
                count += 1
                if count % 50 == 0:
                    logger.info("📄 Processed %d regular segments", count)


async def process_text_batch(segments: list[QBTSegment]) -> None:
    """Process a batch of text segments."""
    logger.info("📝 Processing %d text segments...", len(segments))
    await asyncio.sleep(0.01)


async def process_batch_with_timeout(batch: list[QBTSegment]) -> None:
    """Process batch with timeout."""
    try:
        async with asyncio.timeout(1.0):  # 1 second timeout
            logger.info("⚡ Processing batch of %d segments...", len(batch))
            await asyncio.sleep(0.05)
    except builtins.TimeoutError:
        logger.warning("⏰ Batch processing timed out")


async def main() -> None:
    """Run the enhanced ByteBlaster example with async iterators."""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler()],
    )

    email = "jb@nrgup.net"

    logger.info("🚀 ByteBlaster Async Iterator Demo")
    logger.info("📧 Email: %s", email)
    logger.info("Press Ctrl+C to stop")

    # Create client options
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
        # Start the file manager
        await file_manager.start()
        logger.info("✅ Client started with %d servers", file_manager.client.server_count)

        # Create demo coordinator
        demo = ConcurrentPatternDemo()

        # Run different patterns concurrently
        async with asyncio.TaskGroup() as tg:
            # Main demo task
            tg.create_task(demo.run_callback_vs_iterator_demo(file_manager))

            # Reactive patterns demo
            tg.create_task(demonstrate_reactive_patterns(file_manager.client))

            # Wait for shutdown
            tg.create_task(shutdown_event.wait())

    except* KeyboardInterrupt:
        logger.info("⌨️  Keyboard interrupt received")
    except* Exception:
        logger.exception("Main loop error")
    finally:
        logger.info("🔄 Stopping client...")
        await file_manager.stop(shutdown_timeout=5.0)
        logger.info("✅ Client stopped gracefully")


def run_example() -> None:
    """Run the example using asyncio."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Exiting...")
    except Exception as e:  # noqa: BLE001
        logger.critical("💥 Fatal error: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    run_example()
