# EMWIN QBT Client (ByteBlaster)

A comprehensive Python implementation of the **EMWIN Quick Block Transfer (QBT)** protocol for receiving real-time weather data from the National Weather Service. This protocol is also commonly known as **ByteBlaster**.

## Requirements

- **Python 3.12+** (Python 3.13 recommended for best performance)
- No external dependencies required for core functionality

## Overview

The EMWIN QBT protocol uses Quick Block Transfer (QBT) to efficiently deliver weather data, forecasts, warnings, and satellite imagery. This Python client provides a robust, asynchronous implementation with automatic reconnection, server failover, and comprehensive error handling.

## Features

- **Complete Protocol Implementation**: Full support for EMWIN QBT protocol (v1 and v2)
- **High-Level File Manager**: Simplified interface for receiving complete, reconstructed files, abstracting away low-level data segments.
- **Automatic Reconnection**: Intelligent failover across multiple servers
- **Server List Management**: Dynamic server list updates with persistence
- **Async/Await Support**: Built on asyncio for high performance
- **Data Validation**: Checksum verification and error detection
- **Compression Support**: Automatic handling of zlib-compressed v2 data
- **Watchdog Monitoring**: Connection health monitoring with configurable timeouts
- **Observable Pattern**: Easy subscription to data events
- **Production Ready**: Comprehensive logging, error handling, and type hints

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd byte_blaster

# Install in development mode
pip install -e .

# Or install with development dependencies
pip install -e ".[dev,test]"
```

## Quick Start

```python
import asyncio
from byteblaster import ByteBlasterFileManager, CompletedFile

async def handle_file(file: CompletedFile):
    """Handler for completed files."""
    print(f"Received file: {file.filename}, Size: {len(file.data)} bytes")

async def main():
    # Use the high-level file manager, the recommended client for most use cases.
    manager = ByteBlasterFileManager(email="your-email@example.com")
    
    # Subscribe to completed file events
    manager.subscribe(handle_file)
    
    # Start receiving data
    await manager.start()
    
    # Keep running (use Ctrl+C to stop)
    try:
        # Wait indefinitely until the program is interrupted
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        print("\nClient shutting down...")
    finally:
        await manager.stop()
        print("Client stopped.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
```

## Complete Example

See `example.py` for a comprehensive example that demonstrates:
- File reconstruction from multiple segments
- Data persistence to disk
- Graceful shutdown handling
- Progress monitoring

```bash
python example.py
```

## Protocol Details

### Authentication
- Uses email-based authentication with XOR obfuscation
- Automatic re-authentication every 2 minutes
- Configurable authentication parameters

### Data Flow
1. **Connection**: Client connects to ByteBlaster servers
2. **Authentication**: Sends XOR-encoded logon message
3. **Data Reception**: Receives and decodes data segments
4. **Reconstruction**: Assembles complete files from segments
5. **Validation**: Verifies checksums and data integrity

### Frame Types
- **Data Blocks**: Weather data, forecasts, imagery
- **Server Lists**: Dynamic server list updates

## API Reference

### ByteBlasterFileManager

The recommended high-level client for most use cases. It abstracts away segment handling and provides a simple interface for receiving complete files.

```python
from byteblaster import ByteBlasterFileManager, ByteBlasterClientOptions

# Configure the client with your email
options = ByteBlasterClientOptions(email="your-email@example.com")

# Create the file manager
manager = ByteBlasterFileManager(options)
```

#### Methods

- `subscribe(handler)`: Subscribe to `CompletedFile` events.
- `unsubscribe(handler)`: Remove event subscription.
- `start()`: Start the client (async).
- `stop(timeout=5.0)`: Stop the client (async).

#### Properties
- `client`: Access the underlying `ByteBlasterClient` instance.
- `assembler`: Access the `FileAssembler` instance.


### ByteBlasterClient

The low-level client for handling the EMWIN QBT protocol. Use this if you need to work directly with data segments instead of complete files.

```python
client = ByteBlasterClient(
    options=ByteBlasterClientOptions(
        email="user@example.com",
        server_list_path="servers.json",    # Server persistence file
        watchdog_timeout=20.0,              # Connection timeout
        max_exceptions=10,                  # Max errors before reconnect
        reconnect_delay=5.0,               # Delay between reconnects
    )
)
```

#### Methods

- `subscribe(handler)`: Subscribe to data segment events.
- `unsubscribe(handler)`: Remove event subscription.
- `start()`: Start the client (async).
- `stop(timeout=5.0)`: Stop the client (async).
- `get_server_list()`: Get the current list of servers.

#### Properties

- `is_connected`: Connection status.
- `is_running`: Client running status.
- `server_count`: Number of available servers.
- `email`: Authentication email.

### QBTSegment

Data structure representing a single QBT data block.

*Note: This data class was previously named `QuickBlockTransferSegment` and has been renamed to `QBTSegment` for conciseness and alignment with the official protocol name.*

```python
@dataclass
class QBTSegment:
    filename: str           # Original filename
    block_number: int       # Block sequence number
    total_blocks: int       # Total blocks in file
    content: bytes          # Block data
    checksum: int           # Block checksum
    length: int             # Block length
    version: int            # Protocol version (1 or 2)
    timestamp: datetime     # File timestamp
    received_at: datetime   # Reception timestamp
    header: str             # Raw header
    source: str             # Server address
```

### Server Management

The client automatically manages server lists. You can access the list through the client instance:

```python
# Get current server list from the file manager
server_list = manager.client.get_server_list()

# Or directly from a client instance
# server_list = client.get_server_list()
```

## Configuration

### Server List Persistence

Server lists are automatically saved to `servers.json` (configurable):

```json
{
  "servers": [
    "w2.2y.net:2211",
    "2.pool.iemwin.net:2211"
  ],
  "sat_servers": [],
  "received_at": "2024-01-01T12:00:00",
  "version": "1.0"
}
```

### Logging

Configure logging to monitor client behavior:

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
```

## Protocol Specification

Based on the EMWIN ByteBlaster protocol:

- **Frame Sync**: 6 consecutive 0xFF bytes (for TCP stream)
- **XOR Encoding**: All data XOR'ed with 0xFF
- **Header Format**: 80-byte ASCII header with metadata
- **Compression**: V2 uses zlib compression
- **Checksum**: Simple byte sum validation

### Header Format

```
/PF<filename> /PN <block_num> /PT <total_blocks> /CS <checksum> /FD<date> [/DL<length>]
```

## Error Handling

The client includes comprehensive error handling:

- **Connection Errors**: Automatic reconnection with exponential backoff
- **Protocol Errors**: State machine reset and resynchronization
- **Data Errors**: Checksum validation and corruption detection
- **Timeout Handling**: Watchdog monitoring with configurable timeouts

## Testing

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=byteblaster

# Run specific test categories
pytest -m unit          # Unit tests only
pytest -m integration   # Integration tests only
```

## Development

### Code Quality

This project follows strict code quality standards:

- **Type Hints**: Complete type annotations with Python 3.12+ syntax
- **Linting**: Ruff for code formatting and linting
- **Type Checking**: Pyright/basedpyright for static analysis
- **Testing**: Comprehensive test suite with pytest

```bash
# Format code
ruff format .

# Check code quality
ruff check --fix .

# Type checking
basedpyright
```

### Architecture

The client is built with a modular architecture:

- `client.py`: Main client implementation
- `protocol/`: Protocol implementation
  - `decoder.py`: State machine decoder
  - `models.py`: Data models
  - `auth.py`: Authentication handling
- `server/`: Server management
  - `manager.py`: Server list management
- `utils/`: Utility functions
  - `crypto.py`: XOR encoding and compression

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass
6. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## References

- [EMWIN Protocol Documentation](https://www.weather.gov/emwin/)
- [Quick Block Transfer Specification](https://www.nws.noaa.gov/emwin/winpro.htm)
- [NOAAPort and EMWIN](http://www.noaaport.net/)

## Support

For questions, issues, or contributions:

- Create an issue on GitHub
- Check the examples and documentation
- Review the comprehensive logging output

---

**Note**: Replace `your-email@example.com` with your actual email address when using the client. Some ByteBlaster servers may require registration.