# Async Iterator Usage Guide

This guide demonstrates how to use the async iterator interface with ByteBlaster, showcasing modern Python 3.12+ patterns for event-driven programming.

## Overview

ByteBlaster now supports both callback-based and async iterator patterns for processing data streams:

- **Callback Pattern**: Traditional event handlers (existing functionality)
- **Async Iterator Pattern**: Modern structured concurrency with `async with` and `async for`

## Basic Usage

### 1. File Stream Processing

```python
import asyncio
from pathlib import Path
from byteblaster import ByteBlasterFileManager, ByteBlasterClientOptions

async def process_files():
    options = ByteBlasterClientOptions(email="your@email.com")
    file_manager = ByteBlasterFileManager(options)
    
    await file_manager.start()
    
    # Process files using async iterator
    async with file_manager.stream_files() as files:
        async for completed_file in files:
            print(f"Received: {completed_file.filename}")
            # Process file here
            await save_file(completed_file)

async def save_file(file):
    output_dir = Path("weather_data")
    output_dir.mkdir(exist_ok=True)
    (output_dir / file.filename).write_bytes(file.data)
```

### 2. Segment Stream Processing

```python
async def process_segments():
    options = ByteBlasterClientOptions(email="your@email.com")
    file_manager = ByteBlasterFileManager(options)
    
    await file_manager.start()
    
    # Process raw segments using async iterator
    async with file_manager.client.stream_segments() as segments:
        async for segment in segments:
            if segment.filename != "FILLFILE.TXT":
                print(f"Segment: {segment.filename} ({segment.block_number}/{segment.total_blocks})")
```

## Advanced Patterns

### 1. Concurrent Processing with TaskGroup

```python
async def concurrent_processing():
    options = ByteBlasterClientOptions(email="your@email.com")
    file_manager = ByteBlasterFileManager(options)
    
    await file_manager.start()
    
    # Run multiple processors concurrently
    async with asyncio.TaskGroup() as tg:
        tg.create_task(process_text_files(file_manager))
        tg.create_task(process_image_files(file_manager))
        tg.create_task(analyze_segments(file_manager.client))

async def process_text_files(file_manager):
    async with file_manager.stream_files() as files:
        async for file in files:
            if file.filename.endswith(('.txt', '.TXT')):
                await process_text_content(file)

async def process_image_files(file_manager):
    async with file_manager.stream_files() as files:
        async for file in files:
            if file.filename.endswith(('.png', '.jpg', '.gif')):
                await process_image_content(file)
```

### 2. Filtering and Batching

```python
async def filtered_batch_processing():
    options = ByteBlasterClientOptions(email="your@email.com")
    file_manager = ByteBlasterFileManager(options)
    
    await file_manager.start()
    
    async with file_manager.stream_files() as files:
        batch = []
        async for file in files:
            # Filter for weather alerts
            if "ALERT" in file.filename.upper():
                batch.append(file)
                
                # Process in batches of 5
                if len(batch) >= 5:
                    await process_alert_batch(batch)
                    batch.clear()

async def process_alert_batch(alert_files):
    """Process high-priority alerts together."""
    print(f"Processing {len(alert_files)} alerts")
    async with asyncio.TaskGroup() as tg:
        for alert in alert_files:
            tg.create_task(send_alert_notification(alert))
```

### 3. Backpressure Handling

```python
async def backpressure_example():
    options = ByteBlasterClientOptions(email="your@email.com")
    file_manager = ByteBlasterFileManager(options)
    
    await file_manager.start()
    
    # Small queue for natural backpressure
    async with file_manager.stream_files(max_queue_size=10) as files:
        async for file in files:
            # Slow processing will naturally limit throughput
            await slow_file_processing(file)
            await asyncio.sleep(1.0)  # Simulate slow processing

async def slow_file_processing(file):
    """Simulate time-consuming file processing."""
    print(f"Processing {file.filename}...")
    await asyncio.sleep(2.0)  # Simulate heavy processing
```

### 4. Error Handling and Recovery

```python
async def robust_processing():
    options = ByteBlasterClientOptions(email="your@email.com")
    file_manager = ByteBlasterFileManager(options)
    
    await file_manager.start()
    
    try:
        async with file_manager.stream_files() as files:
            async for file in files:
                try:
                    await process_file_safely(file)
                except ProcessingError as e:
                    logger.warning("File processing failed: %s", e)
                    await handle_processing_error(file, e)
                except Exception:
                    logger.exception("Unexpected error processing file: %s", file.filename)
    except asyncio.CancelledError:
        logger.info("File processing cancelled")
        raise
    finally:
        await file_manager.stop()
```

### 5. Priority Processing

```python
async def priority_processing():
    options = ByteBlasterClientOptions(email="your@email.com")
    file_manager = ByteBlasterFileManager(options)
    
    await file_manager.start()
    
    # Separate high and low priority queues
    high_priority_queue = asyncio.Queue(maxsize=50)
    low_priority_queue = asyncio.Queue(maxsize=200)
    
    async with asyncio.TaskGroup() as tg:
        # Classifier task
        tg.create_task(classify_files(file_manager, high_priority_queue, low_priority_queue))
        
        # Priority processors
        tg.create_task(process_high_priority(high_priority_queue))
        tg.create_task(process_low_priority(low_priority_queue))

async def classify_files(file_manager, high_queue, low_queue):
    async with file_manager.stream_files() as files:
        async for file in files:
            if any(keyword in file.filename.upper() for keyword in ["ALERT", "WARNING", "URGENT"]):
                await high_queue.put(file)
            else:
                await low_queue.put(file)

async def process_high_priority(queue):
    while True:
        file = await queue.get()
        print(f"🚨 High priority: {file.filename}")
        await urgent_file_processing(file)

async def process_low_priority(queue):
    while True:
        file = await queue.get()
        print(f"📄 Low priority: {file.filename}")
        await standard_file_processing(file)
```

## Comparison: Callbacks vs Async Iterators

### Callback Pattern (Traditional)

```python
# Simple and familiar
file_manager.subscribe(save_file_callback)
file_manager.subscribe(validate_file_callback)
file_manager.subscribe(process_file_callback)

await file_manager.start()
# Handlers are called automatically
```

**Pros:**
- Simple and straightforward
- Low overhead
- Familiar to most developers
- Good for simple event handling

**Cons:**
- No natural backpressure
- Harder to compose/chain operations
- No built-in flow control

### Async Iterator Pattern (Modern)

```python
# Structured and composable
async with file_manager.stream_files() as files:
    async for file in files:
        await save_file(file)
        await validate_file(file)
        await process_file(file)
```

**Pros:**
- Natural backpressure handling
- Easy to compose with other async iterators
- Built-in cancellation support
- Structured concurrency friendly
- Can easily filter, map, reduce streams
- Clear lifecycle management

**Cons:**
- Slightly more complex
- Requires understanding of async context managers

## Best Practices

### 1. Use Appropriate Queue Sizes

```python
# For high-throughput scenarios
async with client.stream_segments(max_queue_size=1000) as segments:
    pass

# For memory-constrained environments
async with file_manager.stream_files(max_queue_size=10) as files:
    pass
```

### 2. Handle Cancellation Gracefully

```python
async def graceful_processing():
    try:
        async with file_manager.stream_files() as files:
            async for file in files:
                await process_file(file)
    except asyncio.CancelledError:
        logger.info("Processing cancelled gracefully")
        raise  # Re-raise to propagate cancellation
```

### 3. Use TaskGroups for Concurrency

```python
# Structured concurrency with proper error handling
async with asyncio.TaskGroup() as tg:
    tg.create_task(process_files())
    tg.create_task(analyze_segments())
    tg.create_task(monitor_stats())
```

### 4. Implement Proper Error Isolation

```python
async def isolated_processing():
    async with file_manager.stream_files() as files:
        async for file in files:
            async with asyncio.TaskGroup() as tg:
                # Each file processed in isolation
                tg.create_task(save_file(file))
                tg.create_task(validate_file(file))
                # If one fails, others in this group are cancelled
```

## Migration Guide

If you're upgrading from callback-only usage:

### Before (Callback Only)
```python
async def save_file(file):
    # Save logic here
    pass

file_manager.subscribe(save_file)
await file_manager.start()
```

### After (Both Options Available)
```python
# Option 1: Keep using callbacks (no changes needed)
file_manager.subscribe(save_file)

# Option 2: Use async iterators for new code
async with file_manager.stream_files() as files:
    async for file in files:
        await save_file(file)
```

Both patterns can be used simultaneously in the same application, allowing for gradual migration and choosing the best pattern for each use case.