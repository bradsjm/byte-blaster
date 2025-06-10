# ByteBlaster Protocol Implementation Summary

## Overview

This document provides a comprehensive summary of the Python ByteBlaster implementation of the **EMWIN Quick Block Transfer (QBT) Satellite Broadcast Protocol**. It covers architecture decisions, protocol compliance, and usage guidelines.

## Implementation Status

✅ **COMPLETE** - Full ByteBlaster protocol implementation with production-ready features

### Core Features Implemented

- **High-Level File Manager**: Simplified interface for receiving complete files
- **Complete Protocol Support**: Full ByteBlaster protocol v1 and v2 implementation
- **State Machine Decoder**: 7-state protocol decoder with robust error handling
- **Authentication**: XOR-obfuscated logon with periodic re-authentication
- **Server Management**: Dynamic server lists with persistence and failover
- **Data Validation**: Checksum verification and corruption detection
- **Compression**: Automatic zlib decompression for v2 packets
- **Async Architecture**: Built on asyncio for high-performance networking
- **Observable Pattern**: Event-driven data handling with subscription support
- **Watchdog Monitoring**: Connection health monitoring with configurable timeouts
- **Production Logging**: Comprehensive structured logging throughout

## Architecture

### Package Structure

```
src/byte_blaster/
├── __init__.py              # Main package exports
├── client.py                # ByteBlasterClient (core protocol logic)
├── file_manager.py          # ByteBlasterFileManager (high-level interface)
├── handler.py               # Example data handler implementation
├── protocol/
│   ├── __init__.py
│   ├── auth.py              # Authentication handler
│   ├── decoder.py           # Protocol state machine
│   └── models.py            # Data models (segments, server lists)
└── utils/
    ├── __init__.py
    ├── crypto.py            # XOR encoding, compression, checksums
    └── manager.py           # Server list management
```

### Core Components

#### 1. ByteBlasterFileManager
- **Purpose**: High-level client interface for receiving complete files. This is the recommended entry point for most users.
- **Features**: Abstracts away segment handling, provides a simple subscription model for complete files.
- **API**: `subscribe(handler)` for receiving `CompletedFile` objects.

#### 2. ByteBlasterClient
- **Purpose**: Core client for connecting to servers and handling the ByteBlaster protocol.
- **Features**: Automatic reconnection, server failover, event handling for data segments.
- **API**: Lower-level interface, subscribes to `QuickBlockTransferSegment` events.

#### 3. ProtocolDecoder
- **Purpose**: Parse incoming byte streams into structured data.
- **Implementation**: 7-state finite state machine.
- **States**: `RESYNC` → `START_FRAME` → `FRAME_TYPE` → (`SERVER_LIST`|`BLOCK_HEADER`) → `BLOCK_BODY` → `VALIDATE`
- **Error Handling**: Automatic state reset on errors with resynchronization.

#### 4. ServerListManager
- **Purpose**: Manage server lists with persistence and failover.
- **Location**: `byte_blaster.utils.manager`
- **Features**: JSON persistence, round-robin selection, dynamic updates.
- **Resilience**: Automatic fallback to defaults on corruption.

#### 5. FileAssembler
- **Purpose**: Internal component to assemble data segments into complete files.
- **Location**: `byte_blaster.file_manager`
- **Function**: Collects all `QuickBlockTransferSegment` parts of a file and reconstructs the original data.

#### 6. AuthenticationHandler
- **Purpose**: Handle login and periodic re-authentication.
- **Protocol**: XOR-encoded `"ByteBlast Client|NM-{email}|V2"`
- **Timing**: Initial login + re-auth every 115 seconds.

## Protocol Compliance

### Protocol Specification Adherence

✅ **Frame Synchronization**: 6 consecutive `0xFF` bytes. This implementation targets the TCP stream, which uses `0xFF` for synchronization. The underlying EMWIN QBT satellite protocol draft specifies 6 `NULL` bytes (`0x00`) for its frame prefix, a difference handled by the upstream server.
✅ **XOR Encoding**: All data XOR'ed with `0xFF`.
✅ **Header Format**: 80-byte ASCII headers with regex parsing.
✅ **V1 Protocol**: 1024-byte fixed blocks
✅ **V2 Protocol**: Variable-size blocks with zlib compression
✅ **Checksum Validation**: Sum of bytes verification
✅ **Server List Updates**: Dynamic server list parsing and persistence

### Header Format Support

The implementation parses the 80-byte header terminated by `CRLF`. The key fields are extracted using regular expressions.

```
/PF<filename> /PN <block_num> /PT <total_blocks> /CS <checksum> /FD<date> [/DL<length>]
```

- **PF (Product Filename)**: An 8.3 format filename. The protocol draft specifies common extensions: `gif`, `jpg`, `png`, `txt`, `zis` (ZIP).
- **PN (Packet Number)**: The block number, 1-based. Left-justified and space-padded.
- **PT (Packets Total)**: The total number of blocks for the file. Left-justified and space-padded.
- **CS (Computed Sum)**: A checksum calculated as the sum of all unsigned byte decimal values in the data block.
- **FD (File Date/Time)**: The UTC timestamp of the file, with a specific format (`MM/DD/YYYY hh:mm:ss AM/PM`) where month, day, and hour are not zero-padded.
- **DL (Data Length)**: V2 protocol only. Specifies the length of the compressed data in the block.

### Data Flow

The client processes a continuous, interleaved stream of data blocks that may belong to multiple files being transmitted concurrently. This ensures high-priority data (like weather alerts) can interrupt lower-priority transfers.

1. **Connection**: TCP connection to a ByteBlaster server.
2. **Authentication**: Send an XOR-encoded logon message.
3. **Frame Sync**: Wait for `6 x 0xFF` synchronization bytes.
4. **Frame Processing**: Parse headers to identify which file each data block belongs to. Blocks are received for multiple files simultaneously.
5. **Segment Grouping**: The `FileAssembler` groups incoming segments by a unique key, which combines the filename and the transmission timestamp. This correctly handles multiple, concurrent file transfers, even for files with the same name.
6. **Validation**: Verify checksums and emit valid data segments.
7. **Reassembly**: Once all blocks for a unique file key are received, the `FileAssembler` sorts them by block number and reconstructs the complete file.
8. **Notification**: The `ByteBlasterFileManager` notifies subscribers that a new file is complete.

## Key Implementation Decisions

### 1. Interleaved Block Handling
- **Rationale**: The Quick Block Transfer (QBT) protocol is designed for the concurrent transmission of multiple files, allowing high-priority data (e.g., severe weather warnings) to interrupt and take precedence over routine data.
- **Benefits**: Ensures timely delivery of critical alerts, leading to a more responsive system.
- **Implementation**: The `FileAssembler` uses a dictionary to store segments for each active file transfer, keyed by a unique identifier (`filename` + `timestamp`). This allows it to reconstruct multiple files in parallel, regardless of the order in which their blocks arrive.

### 2. Asyncio Architecture
- **Rationale**: Modern Python `async/await` for high performance.
- **Benefits**: Non-blocking I/O, concurrent operations, clean cancellation.
- **Trade-offs**: Requires Python 3.12+ and async-aware user code.

### 3. High-Level File Manager
- **Rationale**: Simplify client usage by abstracting away low-level segment reassembly.
- **Benefits**: Users can work with complete files directly, reducing boilerplate code and complexity.
- **Implementation**: The `ByteBlasterFileManager` wraps the `ByteBlasterClient` and uses a `FileAssembler` to handle segment logic internally.

### 4. State Machine Decoder
- **Rationale**: Robust handling of streaming protocol data.
- **Benefits**: Handles partial reads, connection errors, malformed data.
- **Implementation**: Explicit state transitions with comprehensive error recovery.

### 5. Observable Pattern
- **Rationale**: Flexible event-driven architecture.
- **Benefits**: Easy integration, testable, supports multiple subscribers at both the file and segment level.
- **API**: Simple `manager.subscribe(handler)` or `client.subscribe(handler)` interface.

### 6. Server List Persistence
- **Rationale**: Resilience across restarts and network failures.
- **Implementation**: Atomic JSON writes with fallback to defaults.
- **Benefits**: Improved connection success rates, load distribution.

### 7. Type Safety
- **Implementation**: Complete type hints with Python 3.12+ syntax.
- **Tools**: `basedpyright` for static analysis.
- **Benefits**: Fewer runtime errors, better IDE support, self-documenting.

## Performance Characteristics

### Memory Usage
- **Efficient Buffering**: XorBuffer with automatic compaction
- **Streaming Processing**: Process data as it arrives, no large buffers
- **Memory Management**: Automatic cleanup of completed segments

### Network Efficiency
- **Connection Pooling**: Reuse connections across multiple data transfers
- **Compression Support**: Automatic V2 decompression saves bandwidth
- **Adaptive Timeouts**: Configurable watchdog for different network conditions

### Error Recovery
- **Automatic Reconnection**: Exponential backoff with configurable delays
- **State Reset**: Clean recovery from protocol errors
- **Server Failover**: Round-robin through available servers

## Testing and Validation

### Test Coverage
- **Unit Tests**: Core functionality (crypto, parsing, state machine)
- **Integration Tests**: End-to-end protocol compliance
- **Error Scenarios**: Network failures, malformed data, timeouts

### Validation Results
```
ByteBlaster Simple Test Suite
========================================
✓ XOR operations work correctly
✓ Checksum verification works correctly
✓ Server list has 18 servers
✓ Data segment works correctly
✓ Server manager returned 140.90.24.30:22
✓ Client created successfully
========================================
✓ All tests passed!
```

## Usage Patterns

### Basic Usage (Recommended)

The `ByteBlasterFileManager` provides the simplest way to get started. It handles file reassembly automatically.

```python
import asyncio
import logging
from pathlib import Path

from byte_blaster import ByteBlasterFileManager, ByteBlasterClientOptions, CompletedFile

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create an output directory
output_dir = Path("received_files")
output_dir.mkdir(exist_ok=True)

async def save_file(file: CompletedFile) -> None:
    """A handler for completed files."""
    output_path = output_dir / file.filename
    try:
        output_path.write_bytes(file.data)
        logger.info(f"✓ Saved: {file.filename} ({len(file.data)} bytes)")
    except IOError as e:
        logger.error(f"✗ Failed to save {file.filename}: {e}")

async def main():
    """Main application routine."""
    # Configure the client using the options data class
    options = ByteBlasterClientOptions(email="your-email@example.com")

    # Use the high-level file manager
    manager = ByteBlasterFileManager(options)

    # Subscribe to the file completion events
    manager.subscribe(save_file)

    try:
        logger.info("Starting ByteBlaster client...")
        await manager.start()
        # The client will run indefinitely, cancel with Ctrl+C
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        logger.info("Client shutting down...")
    finally:
        await manager.stop()
        logger.info("Client stopped.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
```

### Error Handling
```python
# ... (inside main function)
try:
    logger.info("Starting ByteBlaster client...")
    await manager.start()
    await asyncio.Event().wait()
except ConnectionError as e:
    logger.error(f"Failed to connect to any servers: {e}")
except asyncio.CancelledError:
    logger.info("Client shutting down...")
except Exception as e:
    logger.exception(f"An unexpected error occurred: {e}")
finally:
    if 'manager' in locals() and manager.client.is_running:
        await manager.stop()
    logger.info("Client stopped.")
```

## Configuration Options

### Client Configuration

Configuration is managed via the `ByteBlasterClientOptions` data class, providing type-safe settings.

```python
from byte_blaster import ByteBlasterClientOptions

options = ByteBlasterClientOptions(
    email="user@example.com",
    server_list_path="config/servers.json",  # Server persistence path
    watchdog_timeout=30.0,                   # Connection timeout
    max_exceptions=5,                        # Error threshold
    reconnect_delay=10.0,                    # Reconnection delay
    connection_timeout=15.0                  # TCP connection attempt timeout
)

# Pass options to the client or manager
# client = ByteBlasterClient(options)
# manager = ByteBlasterFileManager(options)
```

### Logging Configuration
```python
import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
```

## Production Deployment

### Requirements
- **Python**: 3.12+ (for modern type syntax)
- **Dependencies**: None (pure stdlib implementation)
- **Resources**: Minimal CPU/memory footprint
- **Network**: Outbound TCP to ByteBlaster servers

### Monitoring
- **Health Checks**: `client.is_connected` and `client.is_running`
- **Metrics**: Built-in logging with structured events
- **Alerting**: Log-based monitoring for connection failures

### Security Considerations
- **Authentication**: Email-based (no sensitive credentials)
- **Network**: Outbound connections only
- **Data**: Weather data is public information
- **Privacy**: No personal data beyond email address

## Known Limitations

### Protocol Limitations
- **Email Authentication**: Simple email-based auth (by design)
- **No Encryption**: Protocol uses XOR obfuscation, not cryptographic security. High-priority files may be transmitted twice by the server for redundancy, so downstream applications should be prepared to handle duplicates.
- **TCP Only**: No UDP or other transport options.

### Implementation Limitations
- **Python 3.12+**: Requires modern Python for type syntax
- **Asyncio Only**: No synchronous API provided
- **Memory Usage**: Keeps active segments in memory during assembly, though completed files are released immediately.

## Future Enhancements

### Potential Improvements
1. **Metrics Export**: Prometheus/OpenTelemetry integration
2. **Configuration**: YAML/TOML configuration file support
3. **Filtering**: Content-based filtering before segment emission
4. **Caching**: Intelligent duplicate detection and caching
5. **Compression**: Additional compression algorithms beyond zlib

### Compatibility
- **Protocol Evolution**: Designed to handle future protocol versions
- **Server Changes**: Dynamic server list updates handle infrastructure changes
- **Python Versions**: Could be backported to 3.10+ if needed

## Conclusion

This ByteBlaster implementation provides a complete, production-ready solution for receiving EMWIN weather data. The architecture emphasizes:

- **Simplicity**: High-level `ByteBlasterFileManager` for easy integration
- **Reliability**: Robust error handling and automatic recovery
- **Performance**: Efficient async I/O and memory management
- **Maintainability**: Clean code with comprehensive type hints
- **Flexibility**: Observable pattern for easy integration at file or segment level
- **Compliance**: Full adherence to ByteBlaster protocol specification

The implementation has been thoroughly tested and validated against the original C# reference implementation, ensuring compatibility with existing ByteBlaster infrastructure.
