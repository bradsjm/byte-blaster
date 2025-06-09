# Python Version Compatibility

This document outlines the Python version support strategy for the `byte-blaster` library.

## Current Support

### Minimum Required Version: Python 3.12

The `byte-blaster` library requires **Python 3.12 or newer**. This decision is based on several technical and strategic factors.

### Supported Versions

| Python Version | Support Status | Notes |
|----------------|----------------|-------|
| 3.13.x | ✅ **Fully Supported** | Latest stable, recommended |
| 3.12.x | ✅ **Fully Supported** | Minimum required version |
| 3.11.x | ❌ **Not Supported** | Missing required language features |
| 3.10.x | ❌ **Not Supported** | Missing required language features |
| ≤ 3.9.x | ❌ **Not Supported** | End of life or missing features |

## Why Python 3.12+?

### Technical Requirements

#### Modern Type Syntax
The library extensively uses Python 3.10+ type syntax:
```python
# Modern syntax (Python 3.10+)
def process_data(items: list[str]) -> dict[str, int]:
    return {item: len(item) for item in items}

# Union types (Python 3.10+)
def handle_result(value: str | None) -> bool:
    return value is not None
```

#### Enhanced Error Messages
Python 3.11+ provides significantly improved error messages, crucial for a library dealing with network protocols and binary data parsing.

#### Performance Improvements
- **Python 3.12**: 10-15% performance improvement over 3.11
- **Python 3.13**: Additional optimizations and JIT compilation improvements
- **Memory efficiency**: Better for long-running client connections

#### Typing System Maturity
- **PEP 585**: Built-in generic types (`list[str]` instead of `List[str]`)
- **PEP 604**: Union operator (`str | None` instead of `Union[str, None]`)
- **PEP 612**: Parameter specification variables
- **PEP 647**: User-defined type guards

### Strategic Considerations

#### Library Lifecycle
- **Modern codebase**: Easier maintenance and development
- **Future-proof**: Ready for upcoming Python features
- **Type safety**: Maximum benefit from static type checking
- **Developer experience**: Better IDE support and error messages

#### Target Audience
The `byte-blaster` library targets:
- **Professional developers** who can upgrade Python versions
- **Modern infrastructure** that supports recent Python releases
- **New projects** that can start with current Python versions
- **Weather/scientific applications** that benefit from performance improvements

## Version Support Policy

### Support Timeline

We follow a **rolling support window** approach:

```
Current Year: 2024
├── Python 3.13 (Oct 2024) ✅ Fully Supported
├── Python 3.12 (Oct 2023) ✅ Fully Supported  
├── Python 3.11 (Oct 2022) ❌ Not Supported
└── Python 3.10 (Oct 2021) ❌ Not Supported
```

### Support Commitment

- **Active Support**: Latest 2 Python versions (currently 3.12, 3.13)
- **Security Updates**: For supported versions only
- **New Features**: May require latest Python version
- **Bug Fixes**: Applied to all supported versions

### Version Deprecation Process

When a new Python version is released:

1. **Evaluation Period** (1-2 months): Test compatibility
2. **Beta Support** (1-2 months): Add to CI, mark as experimental
3. **Full Support** (immediately): Add official support
4. **Deprecation Notice** (with new version): Announce oldest version deprecation
5. **End of Support** (6 months later): Remove from CI and support

## Migration Guide

### For Users on Python 3.11 or Earlier

#### Option 1: Upgrade Python (Recommended)
```bash
# Using pyenv
pyenv install 3.12.0
pyenv local 3.12.0

# Using conda
conda create -n myproject python=3.12
conda activate myproject

# Using system package manager (Ubuntu/Debian)
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install python3.12
```

#### Option 2: Use Docker
```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
CMD ["python", "your_script.py"]
```

#### Option 3: Virtual Environment
```bash
# Create virtual environment with Python 3.12
python3.12 -m venv venv
source venv/bin/activate
pip install byte-blaster
```

### For Existing Projects

#### Compatibility Check
Before upgrading, check your current Python version:
```python
import sys
print(f"Current Python: {sys.version}")
print(f"Compatible with byte-blaster: {sys.version_info >= (3, 12)}")
```

#### Code Migration
Most code should work without changes, but watch for:
- **Deprecated features**: Update any deprecated syntax
- **Type annotations**: Leverage new union syntax (`|` operator)
- **Performance**: Take advantage of 3.12+ speed improvements

## Testing Strategy

### Continuous Integration

Our CI pipeline tests against:
```yaml
matrix:
  python-version: ['3.12', '3.13']
  os: [ubuntu-latest, windows-latest, macos-latest]
```

### Version-Specific Testing

#### Python 3.12 Testing
- **Core functionality**: All features work correctly
- **Type checking**: basedpyright validation
- **Performance**: Baseline performance benchmarks
- **Dependencies**: All dependencies compatible

#### Python 3.13 Testing  
- **Forward compatibility**: Ensure new features don't break
- **Performance**: Measure performance improvements
- **New features**: Test any Python 3.13-specific optimizations
- **Deprecation warnings**: Monitor for future compatibility issues

### Local Testing

Test your application with multiple Python versions:
```bash
# Test with Python 3.12
python3.12 -m pytest tests/

# Test with Python 3.13
python3.13 -m pytest tests/

# Test installation
python3.12 -m pip install byte-blaster
python3.13 -m pip install byte-blaster
```

## Performance Considerations

### Python Version Performance

Based on Python.org benchmarks:

| Version | Performance vs 3.11 | Memory Usage | Startup Time |
|---------|---------------------|--------------|--------------|
| 3.12    | +10-15% faster      | -5% less     | 10% faster   |
| 3.13    | +15-20% faster      | -8% less     | 15% faster   |

### byte-blaster Specific Benefits

#### Network I/O Performance
- **Async improvements**: Better asyncio performance in 3.12+
- **Socket operations**: More efficient network handling
- **Memory management**: Better for long-running connections

#### Data Processing Performance
- **Binary parsing**: Faster struct operations
- **String operations**: Improved text processing
- **JSON handling**: Better performance for configuration parsing

## Future Roadmap

### Upcoming Python Versions

#### Python 3.14 (Expected October 2025)
- **Evaluation**: Will test during beta period
- **Adoption**: Likely to add support within 2-3 months of release
- **Features**: May leverage new language features for improved APIs

#### Long-term Strategy
- **Maintain 2-version support**: Always support latest 2 stable versions
- **Performance focus**: Leverage new optimizations as they become available
- **Type system evolution**: Adopt new typing features for better developer experience

### Library Evolution

#### Version 2.0 Considerations
Future major version may:
- **Require Python 3.13+**: To leverage newest features
- **Enhanced type safety**: More precise type annotations
- **Performance optimizations**: Take advantage of latest Python improvements
- **API modernization**: Use newest language constructs

## FAQ

### Why not support Python 3.11?
Python 3.11 lacks several language features we use extensively:
- Modern union syntax (`str | None`)
- Enhanced error messages crucial for debugging network protocols
- Performance improvements important for real-time data processing

### Will you backport features to older Python versions?
No. Our development philosophy prioritizes:
- **Code maintainability** over broad compatibility
- **Modern language features** over legacy support
- **Performance** over maximum reach

### What if I'm stuck on Python 3.11?
Consider:
- **Using Docker**: Run byte-blaster in a Python 3.12+ container
- **Upgrading infrastructure**: Most hosting providers support Python 3.12+
- **Alternative libraries**: Look for libraries with broader Python support
- **Virtual environments**: Use Python 3.12+ in an isolated environment

### How often do you drop Python version support?
- **Annually**: When new Python versions are released
- **6-month notice**: Before dropping support for a version
- **Security updates**: Continue for critical issues during transition period

## Resources

### Python Version Information
- [Python Release Schedule](https://peps.python.org/pep-0693/)
- [Python 3.12 What's New](https://docs.python.org/3.12/whatsnew/3.12.html)
- [Python 3.13 What's New](https://docs.python.org/3.13/whatsnew/3.13.html)

### Migration Tools
- [pyupgrade](https://github.com/asottile/pyupgrade): Automatically upgrade syntax
- [modernize](https://github.com/python-modernize/python-modernize): Modernize Python code
- [2to3](https://docs.python.org/3/library/2to3.html): Built-in Python modernization

### Version Management
- [pyenv](https://github.com/pyenv/pyenv): Python version management
- [conda](https://docs.conda.io/): Package and environment management
- [Poetry](https://python-poetry.org/): Dependency management with version constraints

## Compatibility Checker

We provide a built-in compatibility checker to validate your Python environment:

### Quick Check
```bash
python scripts/check_python_compatibility.py
```

This script will:
- ✅ Verify Python version meets requirements
- ✅ Check language feature availability
- ✅ Test typing system compatibility
- ✅ Validate async/await support
- ✅ Check package manager availability (pip/uv)
- 💡 Provide specific upgrade recommendations

### Example Output
```
🐍 Python Compatibility Check for byte-blaster
============================================================

📋 Python Environment:
  Version: 3.13.2
  Implementation: CPython
  Platform: macOS-15.0-x86_64

🎯 Compatibility Status:
  ✅ COMPATIBLE - byte-blaster will work with this Python version

🔧 Language Features:
  ✅ Union Operator
  ✅ Generic Types
  ✅ Enhanced Errors
  ✅ Performance Optimizations
  ✅ Asyncio Improvements
  ✅ Pattern Matching

💡 Recommendations:
  🚀 Excellent! You're using the latest Python version

🎉 Ready to install and use byte-blaster!
```

### Integration with CI/CD
The compatibility checker is integrated into our development workflow and can be used in your own projects to validate environments before deployment.

---

**Last Updated**: December 2024  
**Next Review**: With Python 3.14 release (October 2025)