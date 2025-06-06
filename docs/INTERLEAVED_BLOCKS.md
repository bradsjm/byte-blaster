# Interleaved Block Handling in ByteBlaster

## Overview

The ByteBlaster protocol implements the **Quick Block Transfer** protocol, which is specifically designed to handle interleaved blocks from multiple files. This capability is crucial for weather data systems where high-priority alerts (severe weather warnings) need to interrupt lower-priority data transmissions (routine weather reports).

## How Interleaved Blocks Work

### Core Principle

The Quick Block Transfer protocol divides large files into small blocks that can be transmitted independently. This allows:

1. **Priority-based transmission**: High-priority files can interrupt ongoing low-priority transfers
2. **Efficient bandwidth usage**: Multiple files can share the same data stream
3. **Resilient delivery**: Missing blocks from one file don't block other files

### Block Identification

Each block is uniquely identified by:

```python
# From QuickBlockTransferSegment
@property
def key(self) -> str:
    """Get unique key for this segment (filename + timestamp)."""
    return f"{self.filename}_{self.timestamp.isoformat()}"
```

This key combines:
- **Filename**: The original file name
- **Timestamp**: When the file transmission started (ISO format)

This ensures that even files with identical names are treated as separate transfers if they have different timestamps.

## Implementation Details

### Segment Grouping

The protocol groups blocks by their unique key, not just filename:

```python
# From example.py WeatherDataHandler
def handle_segment(self, segment: QuickBlockTransferSegment) -> None:
    # Group segments by file key (filename + timestamp)
    file_key = segment.key
    if file_key not in self.file_segments:
        self.file_segments[file_key] = []
    
    self.file_segments[file_key].append(segment)
    
    # Check if we have all segments for this file
    segments = self.file_segments[file_key]
    if len(segments) == segment.total_blocks:
        await self._reconstruct_file(file_key, segments)
```

### File Reconstruction

Files are reconstructed when all blocks are received:

1. **Block sorting**: Blocks are sorted by `block_number` before reconstruction
2. **Content joining**: Block contents are concatenated in order
3. **Memory cleanup**: Completed file segments are removed from memory

## Example Interleaved Scenario

Consider this transmission sequence:

```
Time  Block             Priority   Status
----  ---------------   --------   ------------------
001   weather.txt:1/4   Low        Started transmission
002   weather.txt:2/4   Low        Continuing...
003   alert.txt:1/2     HIGH       🚨 INTERRUPTS! 🚨
004   alert.txt:2/2     HIGH       Alert complete ✓
005   forecast.txt:1/3  Medium     New file starts
006   weather.txt:3/4   Low        Resumes transmission
007   forecast.txt:2/3  Medium     Continuing...
008   forecast.txt:3/3  Medium     Forecast complete ✓
009   weather.txt:4/4   Low        Weather complete ✓
```

### Results

- **alert.txt** completes first (2 blocks) - highest priority
- **forecast.txt** completes second (3 blocks) - medium priority  
- **weather.txt** completes last (4 blocks) - lowest priority

The protocol correctly handles all three files simultaneously without data loss or corruption.

## Verification Test Results

Our comprehensive test suite (`test_interleaved_blocks.py`) verifies:

### ✅ Interleaved Block Handling
- Multiple files can transmit blocks simultaneously
- Files complete when all their blocks arrive (regardless of order)
- No interference between different file transfers

### ✅ Priority Interruption
- High-priority files can start transmission mid-stream
- Lower-priority transfers resume after high-priority completion
- Completion order reflects priority, not start order

### ✅ Unique File Identification
- Files with same name but different timestamps are separate
- Each file maintains its own block collection
- No cross-contamination between file transfers

### ✅ Out-of-Order Block Handling
- Blocks can arrive in any order within a file
- Reconstruction sorts blocks correctly by block number
- File integrity is maintained regardless of receive order

## Technical Benefits

### 1. **Real-time Weather Alerts**
```
🌪️ Tornado Warning can interrupt routine forecast transmission
⚡ Flash Flood Alert takes precedence over hourly updates
🌨️ Blizzard Warning bypasses standard weather data
```

### 2. **Efficient Bandwidth Usage**
- No need to wait for large files to complete
- Multiple data sources can share the same connection
- Optimal use of available transmission capacity

### 3. **Fault Tolerance**
- Corrupted blocks in one file don't affect others
- Missing blocks can be retransmitted without blocking other files
- Graceful degradation under poor network conditions

## Protocol Specification Compliance

The implementation follows the Quick Block Transfer protocol specification:

> *"The Quick Block Transfer protocol divides messages into small pieces to allow interruption of large, low priority messages by messages of a more immediate nature. This ensures timely notification of impending severe weather events."*

This design ensures that critical weather alerts reach users as quickly as possible, even when the system is busy transmitting routine data.

## Code Example

Here's how to implement a handler that properly manages interleaved blocks:

```python
class WeatherDataHandler:
    def __init__(self):
        # Group segments by unique file key (filename + timestamp)
        self.file_segments: dict[str, list[QuickBlockTransferSegment]] = {}
    
    async def handle_segment(self, segment: QuickBlockTransferSegment) -> None:
        # Skip filler data
        if segment.filename == "FILLFILE.TXT":
            return
            
        # Use segment.key to group blocks from the same file
        file_key = segment.key
        if file_key not in self.file_segments:
            self.file_segments[file_key] = []
        
        self.file_segments[file_key].append(segment)
        
        # Check if file is complete
        segments = self.file_segments[file_key]
        if len(segments) == segment.total_blocks:
            await self._reconstruct_file(file_key, segments)
    
    async def _reconstruct_file(self, file_key: str, segments: list[QuickBlockTransferSegment]) -> None:
        # Sort by block number to ensure correct order
        segments.sort(key=lambda s: s.block_number)
        
        # Combine content
        complete_data = b"".join(segment.content for segment in segments)
        
        # Save file
        filename = segments[0].filename
        # ... save complete_data to filename ...
        
        # Clean up memory
        del self.file_segments[file_key]
```

## Summary

The ByteBlaster protocol's interleaved block handling is a sophisticated feature that enables:

- **Priority-based data transmission** for time-critical weather alerts
- **Concurrent file transfers** without interference
- **Robust data integrity** through unique file identification
- **Efficient bandwidth utilization** across multiple data streams

This capability is essential for weather data systems where timely delivery of severe weather warnings can save lives and property.