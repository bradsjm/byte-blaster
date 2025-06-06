# ByteBlaster Python Client

A comprehensive Python implementation of the EMWIN (Emergency Managers Weather Information Network) ByteBlaster protocol for receiving real-time weather data from the National Weather Service.

## Overview

The ByteBlaster protocol uses Quick Block Transfer (QBT) to efficiently deliver weather data, forecasts, warnings, and satellite imagery. This Python client provides a robust, asynchronous implementation with automatic reconnection, server failover, and comprehensive error handling.

## Features

- **Complete Protocol Implementation**: Full support for ByteBlaster protocol v1 and v2
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
from byte_blaster import ByteBlasterClient

async def handle_data(segment):
    print(f"Received: {segment.filename} block {segment.block_number}/{segment.total_blocks}")

async def main():
    # Create client with your email
    client = ByteBlasterClient("your-email@example.com")
    
    # Subscribe to data events
    client.subscribe(handle_data)
    
    # Start receiving data
    await client.start()
    
    # Keep running (use Ctrl+C to stop)
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await client.stop()

if __name__ == "__main__":
    asyncio.run(main())
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

### ByteBlasterClient

Main client class for connecting to ByteBlaster servers.

```python
client = ByteBlasterClient(
    email="user@example.com",
    server_list_path="servers.json",    # Server persistence file
    watchdog_timeout=20.0,              # Connection timeout
    max_exceptions=10,                  # Max errors before reconnect
    reconnect_delay=5.0,               # Delay between reconnects
)
```

#### Methods

- `subscribe(handler)`: Subscribe to data segment events
- `unsubscribe(handler)`: Remove event subscription
- `start()`: Start the client (async)
- `stop(timeout=5.0)`: Stop the client (async)

#### Properties

- `is_connected`: Connection status
- `is_running`: Client running status
- `server_count`: Number of available servers
- `email`: Authentication email

### QuickBlockTransferSegment

Data structure representing a single data block.

```python
@dataclass
class QuickBlockTransferSegment:
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

The client automatically manages server lists:

```python
# Get current server list
server_list = client.get_server_list()

# Server lists are automatically updated from the protocol
# and persisted to disk for resilience
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

- **Frame Sync**: 6 consecutive 0xFF bytes
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
pytest --cov=byte_blaster

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