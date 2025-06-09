# Typing Support

The `byte-blaster` library is fully typed and provides comprehensive type information for all public APIs. This document explains how to use the library with type checkers and IDEs.

## Type Checker Support

This library includes a `py.typed` marker file and is configured with the `Typing :: Typed` classifier, making it compatible with:

- **basedpyright** / **Pyright** (recommended)
- **mypy**
- **PyCharm**
- **VS Code** with Python extension
- Other PEP 561 compliant type checkers

## Installation

```bash
pip install byte-blaster
```

The typing information is automatically available after installation - no additional steps required.

## Basic Usage with Type Hints

```python
from byteblaster import (
    ByteBlasterClient,
    ByteBlasterClientOptions,
    ByteBlasterFileManager,
    CompletedFile,
)

# Type checker will validate this configuration
options: ByteBlasterClientOptions = ByteBlasterClientOptions(
    email="user@example.com",
    server_host="example.com",
    server_port=2211
)

# Async callback with proper typing
async def handle_file(file: CompletedFile) -> None:
    filename: str = file.filename
    data: bytes = file.data
    print(f"Received {filename}: {len(data)} bytes")

# File manager with type safety
file_manager: ByteBlasterFileManager = ByteBlasterFileManager(options)
file_manager.subscribe(handle_file)  # Type checker validates callback signature
```

## Advanced Type Usage

### Protocol Models

```python
from byteblaster.protocol.models import QBTSegment, ByteBlasterServerList

# Segment handling with full type safety
def process_segment(segment: QBTSegment) -> None:
    block_num: int = segment.block_number
    total: int = segment.total_blocks
    content: bytes = segment.content
    filename: str = segment.filename

# Server list management
def handle_servers(server_list: ByteBlasterServerList) -> None:
    servers: list[str] = server_list.servers
    primary: str = server_list.primary_server
```

### Custom Handlers

```python
from typing import Protocol
from byteblaster import CompletedFile

class FileHandler(Protocol):
    """Protocol for file handling callbacks."""
    
    async def __call__(self, file: CompletedFile) -> None:
        """Handle a completed file."""
        ...

# Type-safe custom handler
class CustomFileHandler:
    def __init__(self, output_dir: str) -> None:
        self.output_dir = output_dir
    
    async def __call__(self, file: CompletedFile) -> None:
        # Implementation with full type safety
        path = Path(self.output_dir) / file.filename
        path.write_bytes(file.data)

# Usage
handler: FileHandler = CustomFileHandler("./downloads")
file_manager.subscribe(handler)  # Type checker validates protocol compliance
```

## Type Checker Configuration

### basedpyright/Pyright

Add to your `pyrightconfig.json` or `pyproject.toml`:

```json
{
    "typeCheckingMode": "strict",
    "reportMissingTypeStubs": true,
    "reportUnknownVariableType": true
}
```

Or in `pyproject.toml`:

```toml
[tool.basedpyright]
typeCheckingMode = "strict"
reportMissingTypeStubs = true
reportUnknownVariableType = true
```

### mypy

Add to your `mypy.ini` or `pyproject.toml`:

```ini
[mypy]
strict = true
warn_return_any = true
warn_unused_configs = true
```

Or in `pyproject.toml`:

```toml
[tool.mypy]
strict = true
warn_return_any = true
warn_unused_configs = true
```

## Common Type Patterns

### Error Handling

```python
from typing import Union
import asyncio

async def safe_file_handler(file: CompletedFile) -> None:
    try:
        # Process file with type safety
        data: bytes = file.data
        filename: str = file.filename
        
        # Your processing logic here
        
    except Exception as e:
        print(f"Error processing {file.filename}: {e}")

# Exception handling in async context
async def robust_client() -> None:
    options = ByteBlasterClientOptions(email="test@example.com")
    file_manager = ByteBlasterFileManager(options)
    
    try:
        await file_manager.start()
        # Keep running
        await asyncio.Event().wait()
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        await file_manager.stop()
```

### Generic Callbacks

```python
from typing import Callable, Awaitable

# Type alias for file callbacks
FileCallback = Callable[[CompletedFile], Awaitable[None]]

def create_filtered_handler(pattern: str) -> FileCallback:
    """Create a type-safe filtered file handler."""
    import re
    regex = re.compile(pattern)
    
    async def handler(file: CompletedFile) -> None:
        if regex.match(file.filename):
            print(f"Matched: {file.filename}")
    
    return handler

# Usage with full type safety
weather_handler: FileCallback = create_filtered_handler(r".*\.txt$")
file_manager.subscribe(weather_handler)
```

## IDE Integration

### VS Code

1. Install the Python extension
2. Enable type checking in settings:
   ```json
   {
       "python.analysis.typeCheckingMode": "strict",
       "python.analysis.autoImportCompletions": true
   }
   ```

### PyCharm

Type hints are automatically recognized. Enable stricter checking in:
- File → Settings → Editor → Inspections → Python
- Enable "Type checker compatibility" inspections

## Troubleshooting

### Missing Type Information

If your type checker reports missing type information:

1. **Verify installation**: Ensure `byte-blaster` is installed in the same environment as your type checker
2. **Check py.typed**: The package should include a `py.typed` file
3. **Update tools**: Ensure your type checker supports PEP 561

### Import Errors

```python
# ✅ Correct imports
from byteblaster import ByteBlasterClient
from byteblaster.protocol.models import QBTSegment

# ❌ Avoid internal imports
# from byteblaster.internal import ...  # May not be typed
```

### Type Stub Conflicts

If you have custom type stubs that conflict:

```bash
# Remove conflicting stubs
rm -rf typings/byteblaster*
```

## Version Compatibility

- **Python**: 3.12+
- **Type Checkers**: Any PEP 561 compliant checker
- **Typing Extensions**: No additional dependencies required

## Contributing Type Improvements

Found a typing issue? Please report it on our [GitHub Issues](https://github.com/bradsjm/byte-blaster/issues) with:

1. Your type checker and version
2. Code example that fails
3. Expected vs actual behavior

---

For more examples, see the [examples directory](../examples/) which includes fully typed usage patterns.