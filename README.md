# EMWIN QBT Client (ByteBlaster)

A comprehensive Python implementation of the **EMWIN Quick Block Transfer (QBT)** protocol for receiving real-time weather data from the National Weather Service. This protocol is also commonly known as **ByteBlaster**.

## Requirements

- **Python 3.12+** (Python 3.13 recommended for best performance)
- Zero runtime dependencies - pure Python implementation

## Overview

The EMWIN QBT protocol uses Quick Block Transfer (QBT) to efficiently deliver weather data, forecasts, warnings, and satellite imagery. This Python client provides a robust, asynchronous implementation with automatic reconnection, server failover, and comprehensive error handling.

## Features

- **Complete Protocol Implementation**: Full support for EMWIN QBT protocol (v1 and v2)
- **High-Level File Manager**: Simplified interface for receiving complete, reconstructed files, abstracting away low-level data segments.
- **Async Iterator Support**: Modern async/await patterns with `stream_files()` and `stream_segments()` methods
- **Automatic Reconnection**: Intelligent failover across multiple servers
- **Server List Management**: Dynamic server list updates with persistence
- **Async/Await Support**: Built on asyncio for high performance
- **Data Validation**: Checksum verification and error detection
- **Compression Support**: Automatic handling of zlib-compressed v2 data
- **Watchdog Monitoring**: Connection health monitoring with configurable timeouts
- **Observable Pattern**: Easy subscription to data events
- **Production Ready**: Comprehensive logging, error handling, and type hints

## Installation

### From PyPI (Recommended)

The package is available on PyPI and works with all modern Python package managers:

#### Using pip
```bash
# Install latest version
pip install byte-blaster

# Install with optional dependencies
pip install byte-blaster[dev,test]
```

#### Using UV (Fastest)
```bash
# Install in current environment
uv pip install byte-blaster

# Create new project with byte-blaster
uv init my-weather-app
cd my-weather-app
uv add byte-blaster

# Install with dependency groups
uv sync --group dev --group test
```

#### Using Poetry
```bash
# Add to existing project
poetry add byte-blaster

# Add development dependencies
poetry add --group dev byte-blaster[dev]
poetry add --group test byte-blaster[test]
```

#### Using PDM
```bash
# Add to project
pdm add byte-blaster

# Add with dependency groups
pdm add -dG dev byte-blaster[dev]
pdm add -dG test byte-blaster[test]
```

#### Using Conda/Mamba
```bash
# Install from conda-forge (if available) or pip
conda install byte-blaster
# or
conda install pip && pip install byte-blaster
```

### From Source (Development)

```bash
# Clone the repository
git clone <repository-url>
cd byte-blaster

# Using UV (recommended for development)
uv sync --group dev --group test
source .venv/bin/activate  # or `.venv\Scripts\activate` on Windows

# Using pip
pip install -e .
pip install -e ".[dev,test]"

# Using Poetry
poetry install --with dev,test

# Using PDM
pdm install -dG dev -dG test
```

### Verify Installation

```bash
# Run comprehensive verification script
python scripts/verify_installation.py

# Test basic import
python -c "from byteblaster import ByteBlasterClient; print('✅ Installation successful')"

# Run examples
python examples/example.py
```

### Package Manager Compatibility

This project uses modern Python packaging standards and is compatible with:

| Package Manager | Version | Installation Command | Dependency Groups |
|-----------------|---------|---------------------|-------------------|
| **pip** | 21.3+ | `pip install byte-blaster` | `pip install byte-blaster[dev,test]` |
| **UV** | 0.1.0+ | `uv add byte-blaster` | `uv sync --group dev --group test` |
| **Poetry** | 1.2+ | `poetry add byte-blaster` | `poetry install --with dev,test` |
| **PDM** | 2.0+ | `pdm add byte-blaster` | `pdm install -dG dev -dG test` |
| **Conda** | Any | `pip install byte-blaster` | Via pip in conda env |
| **Pipenv** | Any | `pipenv install byte-blaster` | `pipenv install --dev` |

**Requirements:**
- Python 3.12+ (Python 3.13 recommended)
- Modern package manager supporting PEP 621 (pyproject.toml)
- No system dependencies required

**Features:**
- ✅ Pure Python (no compiled extensions)
- ✅ Type hints included (`py.typed` marker)
- ✅ Dependency groups for dev/test separation
- ✅ Wheel and source distributions available
- ✅ Cross-platform compatibility (Windows, macOS, Linux)
- ✅ PEP 621 compliant (pyproject.toml-based configuration)
- ✅ PEP 517/518 build system (setuptools backend)
- ✅ PEP 440 version scheme
- ✅ PEP 508 dependency specifications

### Troubleshooting Installation

If you encounter issues with specific package managers:

#### UV Issues
```bash
# Update UV to latest version
uv self update

# Clear cache and retry
uv cache clean
uv add byte-blaster

# Force reinstall
uv pip install --force-reinstall byte-blaster
```

#### pip Issues
```bash
# Update pip and build tools
pip install --upgrade pip setuptools wheel

# Install with verbose output for debugging
pip install -v byte-blaster

# Clear pip cache
pip cache purge
```

#### Poetry Issues
```bash
# Update Poetry
poetry self update

# Clear cache
poetry cache clear pypi --all

# Force update lock file
poetry lock --no-update
poetry install
```

#### General Issues
- **Python Version**: Ensure Python 3.12+ is installed
- **Virtual Environment**: Always use a virtual environment
- **Dependencies**: Check for conflicting packages with `pip check`
- **Permissions**: Use `--user` flag if encountering permission errors
- **Network**: Check proxy settings if behind corporate firewall

### Package Manager Summary

ByteBlaster is designed to work seamlessly with all modern Python package managers:

| Feature | Status | Notes |
|---------|--------|-------|
| **pip compatibility** | ✅ Full | Standard `pip install byte-blaster` |
| **UV compatibility** | ✅ Full | Fastest installation with `uv add byte-blaster` |
| **Poetry compatibility** | ✅ Full | `poetry add byte-blaster` |
| **PDM compatibility** | ✅ Full | `pdm add byte-blaster` |
| **Conda compatibility** | ✅ Via pip | `pip install byte-blaster` in conda env |
| **Pipenv compatibility** | ✅ Full | `pipenv install byte-blaster` |
| **Zero dependencies** | ✅ Yes | Pure Python, no runtime dependencies |
| **Type hints** | ✅ Full | Complete type annotations included |
| **Wheels available** | ✅ Yes | Fast binary installation |
| **Source builds** | ✅ Yes | `pip install` from source works |

**Recommended installation methods:**
- **For new projects**: `uv add byte-blaster` (fastest)
- **For existing pip projects**: `pip install byte-blaster`
- **For Poetry projects**: `poetry add byte-blaster`
- **For development**: `uv sync --group dev --group test` (after cloning)

## Quick Start

```python
import asyncio
from byteblaster import ByteBlasterClientOptions, ByteBlasterFileManager, CompletedFile

async def handle_file(file: CompletedFile):
    """Handler for completed files."""
    print(f"Received file: {file.filename}, Size: {len(file.data)} bytes")

async def main():
    # Create client options - email is required for authentication
    options = ByteBlasterClientOptions(email="your-email@example.com")
    
    # Use the high-level file manager, the recommended client for most use cases.
    manager = ByteBlasterFileManager(options)
    
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

## Async Iterator Patterns

The library supports modern async iterator patterns for reactive programming:

### File Streaming

```python
import asyncio
from byteblaster import ByteBlasterClientOptions, ByteBlasterFileManager

async def main():
    options = ByteBlasterClientOptions(email="your-email@example.com")
    manager = ByteBlasterFileManager(options)
    
    await manager.start()
    
    # Use async iterator pattern
    async with manager.stream_files() as files:
        async for completed_file in files:
            print(f"Processing: {completed_file.filename}")
            # Process file here
    
    await manager.stop()

asyncio.run(main())
```

### Segment Streaming

```python
import asyncio
from byteblaster import ByteBlasterClientOptions, ByteBlasterClient

async def main():
    options = ByteBlasterClientOptions(email="your-email@example.com")
    client = ByteBlasterClient(options)
    
    await client.start()
    
    # Stream individual segments
    async with client.stream_segments() as segments:
        async for segment in segments:
            print(f"Segment: {segment.filename} ({segment.block_number}/{segment.total_blocks})")
    
    await client.stop()

asyncio.run(main())
```

## Complete Example

See `examples/example.py` for a comprehensive example that demonstrates:
- File reconstruction from multiple segments
- Data persistence to disk
- Graceful shutdown handling
- Progress monitoring
- Concurrent processing with multiple handlers

```bash
python examples/example.py
```

For advanced async iterator examples, see:
```bash
python examples/example_async_iterators.py
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
- `stream_files(max_queue_size=100)`: Create async iterator for streaming files.
- `start()`: Start the client (async).
- `stop(shutdown_timeout=None)`: Stop the client (async).

#### Properties
- `client`: Access the underlying `ByteBlasterClient` instance.
- `assembler`: Access the `FileAssembler` instance.

### ByteBlasterClient

The low-level client for handling the EMWIN QBT protocol. Use this if you need to work directly with data segments instead of complete files.

```python
from byteblaster import ByteBlasterClient, ByteBlasterClientOptions

client = ByteBlasterClient(
    options=ByteBlasterClientOptions(
        email="user@example.com",
        server_list_path="servers.json",      # Server persistence file
        watchdog_timeout=20.0,                # Connection timeout
        max_exceptions=10,                    # Max errors before reconnect
        reconnect_delay=5.0,                  # Delay between reconnects
        connection_timeout=10.0,              # TCP connection timeout
    )
)
```

#### Methods

- `subscribe(handler)`: Subscribe to data segment events.
- `unsubscribe(handler)`: Remove event subscription.
- `stream_segments(max_queue_size=1000)`: Create async iterator for streaming segments.
- `start()`: Start the client (async).
- `stop(shutdown_timeout=None)`: Stop the client (async).
- `get_server_list()`: Get the current `ByteBlasterServerList` instance.

#### Properties

- `is_connected`: Connection status.
- `is_running`: Client running status.
- `server_count`: Number of available servers.
- `email`: Authentication email.

### ByteBlasterClientOptions

Configuration class for client initialization.

```python
from byteblaster import ByteBlasterClientOptions

options = ByteBlasterClientOptions(
    email="user@example.com",                 # Required: Email for authentication
    server_list_path="servers.json",          # Server persistence file path
    watchdog_timeout=20.0,                    # Connection watchdog timeout
    max_exceptions=10,                        # Max errors before reconnect
    reconnect_delay=5.0,                      # Delay between reconnection attempts
    connection_timeout=10.0,                  # TCP connection establishment timeout
)
```

### QBTSegment

Data structure representing a single QBT data block.

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

### CompletedFile

Data structure representing a fully reconstructed file.

```python
class CompletedFile(NamedTuple):
    filename: str    # Original filename
    data: bytes      # Complete file content
```

### Async Iterators

The library provides async iterator classes for streaming data:

- `FileStream`: Async iterator for completed files (from `stream_files()`)
- `SegmentStream`: Async iterator for data segments (from `stream_segments()`)

Both support context manager protocol and backpressure handling.

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
- `file_manager.py`: High-level file management interface
- `protocol/`: Protocol implementation
  - `decoder.py`: State machine decoder
  - `models.py`: Data models
  - `auth.py`: Authentication handling
- `utils/`: Utility functions
  - `crypto.py`: XOR encoding and compression
  - `serverlist.py`: Server list management

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

## Acknowledgments

### AI Assistance

This project has been developed with assistance from Large Language Models (LLMs), and we acknowledge their significant contributions to both the codebase and documentation:

- **Anthropic Claude** - Contributed to code architecture, implementation patterns, documentation structure, async/await patterns, error handling strategies, and comprehensive testing approaches
- **OpenAI GPT** - Assisted with protocol implementation details, API design decisions, code optimization suggestions, and example development
- **Google Gemini** - Provided insights on Python best practices, type annotation improvements, and packaging standards compliance

The LLMs have been instrumental in:
- **Code Quality**: Implementing modern Python 3.12+ features, type hints, and async patterns
- **Documentation**: Creating comprehensive README, API documentation, and example code
- **Architecture**: Designing modular, testable, and maintainable code structure
- **Standards Compliance**: Ensuring adherence to PEP standards and modern packaging practices
- **Error Handling**: Implementing robust error recovery and logging strategies

While AI has significantly accelerated development and improved code quality, all code has been reviewed, tested, and validated by human developers. The final implementation decisions, architecture choices, and quality standards remain under human oversight.

### Human Contributors

We also acknowledge the human developers, domain experts, and community members who have contributed to the project through code review, testing, feedback, and domain expertise in weather data protocols.

---

**Note**: Replace `your-email@example.com` with your actual email address when using the client. Some ByteBlaster servers may require registration.