#!/usr/bin/env python3
# pyright: standard
"""Installation verification script for ByteBlaster.

This script verifies that ByteBlaster has been installed correctly and all
core functionality is accessible. It performs basic import tests, version
checks, and minimal functionality tests.

Usage:
    python scripts/verify_installation.py
    # or
    python -m scripts.verify_installation
"""

import sys
import traceback


def test_basic_imports() -> bool:
    """Test basic package imports."""
    print("🔍 Testing basic imports...")

    try:
        # Test main package import
        import byteblaster

        print(f"✅ Package import successful: byteblaster v{byteblaster.__version__}")

        # Test main classes
        from byteblaster import (
            ByteBlasterClient,
            ByteBlasterClientOptions,
            ByteBlasterFileManager,
            CompletedFile,
            QBTSegment,
        )

        print("✅ Core classes imported successfully")

        # Test protocol models
        from byteblaster.protocol.models import ByteBlasterServerList

        print("✅ Protocol models imported successfully")

        # Test utilities
        from byteblaster.utils import ServerListManager

        print("✅ Utilities imported successfully")

        return True

    except ImportError as e:
        print(f"❌ Import failed: {e}")
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"❌ Unexpected error during import: {e}")
        traceback.print_exc()
        return False


def test_class_instantiation() -> bool:
    """Test basic class instantiation."""
    print("\n🏗️  Testing class instantiation...")

    try:
        from byteblaster import ByteBlasterClientOptions, ByteBlasterFileManager

        # Test options creation
        options = ByteBlasterClientOptions(email="test@example.com")
        print(f"✅ ByteBlasterClientOptions created: {options.email}")

        # Test file manager creation (don't start it)
        manager = ByteBlasterFileManager(options)
        print("✅ ByteBlasterFileManager created successfully")

        # Test client access
        client = manager.client
        print(f"✅ ByteBlasterClient accessed: {client.email}")

        return True

    except Exception as e:
        print(f"❌ Class instantiation failed: {e}")
        traceback.print_exc()
        return False


def test_data_structures() -> bool:
    """Test data structure creation."""
    print("\n📊 Testing data structures...")

    try:
        from datetime import UTC, datetime

        from byteblaster import CompletedFile, QBTSegment
        from byteblaster.protocol.models import ByteBlasterServerList

        # Test CompletedFile
        file = CompletedFile(filename="test.txt", data=b"test data")
        print(f"✅ CompletedFile created: {file.filename} ({len(file.data)} bytes)")

        # Test QBTSegment
        segment = QBTSegment(
            filename="test.txt",
            block_number=1,
            total_blocks=1,
            content=b"test",
            timestamp=datetime.now(UTC),
        )
        print(
            f"✅ QBTSegment created: {segment.filename} (block {segment.block_number}/{segment.total_blocks})"
        )

        # Test ByteBlasterServerList
        server_list = ByteBlasterServerList()
        print(f"✅ ByteBlasterServerList created: {len(server_list)} servers")

        return True

    except Exception as e:
        print(f"❌ Data structure test failed: {e}")
        traceback.print_exc()
        return False


def test_utilities() -> bool:
    """Test utility functions."""
    print("\n🔧 Testing utilities...")

    try:
        from byteblaster.utils import ServerListManager
        from byteblaster.utils.crypto import xor_decode, xor_encode

        # Test server list manager
        manager = ServerListManager(enable_persistence=False)
        print(f"✅ ServerListManager created: {len(manager)} servers")

        # Test crypto utilities
        test_data = b"Hello, ByteBlaster!"
        encoded = xor_encode(test_data)
        decoded = xor_decode(encoded)

        if decoded == test_data:
            print("✅ Crypto utilities working correctly")
        else:
            print("❌ Crypto utilities failed: data mismatch")
            return False

        return True

    except Exception as e:
        print(f"❌ Utilities test failed: {e}")
        traceback.print_exc()
        return False


def test_async_features() -> bool:
    """Test async feature availability."""
    print("\n⚡ Testing async features...")

    try:
        from byteblaster import ByteBlasterClientOptions, ByteBlasterFileManager

        # Test async context manager availability
        options = ByteBlasterClientOptions(email="test@example.com")
        manager = ByteBlasterFileManager(options)

        # Check if async methods exist
        if hasattr(manager, "start") and callable(manager.start):
            print("✅ Async start method available")
        else:
            print("❌ Async start method missing")
            return False

        if hasattr(manager, "stop") and callable(manager.stop):
            print("✅ Async stop method available")
        else:
            print("❌ Async stop method missing")
            return False

        if hasattr(manager, "stream_files") and callable(manager.stream_files):
            print("✅ Async iterator (stream_files) available")
        else:
            print("❌ Async iterator (stream_files) missing")
            return False

        # Test client async features
        client = manager.client
        if hasattr(client, "stream_segments") and callable(client.stream_segments):
            print("✅ Async iterator (stream_segments) available")
        else:
            print("❌ Async iterator (stream_segments) missing")
            return False

        return True

    except Exception as e:
        print(f"❌ Async features test failed: {e}")
        traceback.print_exc()
        return False


def test_version_info() -> bool:
    """Test version and metadata information."""
    print("\n📋 Testing version and metadata...")

    try:
        import byteblaster

        # Check version
        version = getattr(byteblaster, "__version__", "unknown")
        print(f"✅ Version: {version}")

        # Check author
        author = getattr(byteblaster, "__author__", "unknown")
        print(f"✅ Author: {author}")

        # Check email
        email = getattr(byteblaster, "__email__", "unknown")
        print(f"✅ Contact: {email}")

        # Check __all__ exports
        all_exports = getattr(byteblaster, "__all__", [])
        print(f"✅ Exported symbols: {len(all_exports)} items")
        for export in all_exports[:5]:  # Show first 5
            print(f"   - {export}")
        if len(all_exports) > 5:
            print(f"   ... and {len(all_exports) - 5} more")

        return True

    except Exception as e:
        print(f"❌ Version info test failed: {e}")
        traceback.print_exc()
        return False


def check_python_version() -> bool:
    """Check Python version compatibility."""
    print("🐍 Checking Python version...")

    major, minor = sys.version_info[:2]

    if major < 3:
        print(f"❌ Python {major}.{minor} is not supported. Python 3.12+ required.")
        return False
    if major == 3 and minor < 12:
        print(f"⚠️  Python {major}.{minor} detected. Python 3.12+ recommended.")
        print("   Some features may not work correctly.")
        return True
    print(f"✅ Python {major}.{minor} detected. Version compatible.")
    return True


def main() -> int:
    """Run all verification tests."""
    print("🚀 ByteBlaster Installation Verification")
    print("=" * 50)

    tests = [
        ("Python Version", check_python_version),
        ("Basic Imports", test_basic_imports),
        ("Class Instantiation", test_class_instantiation),
        ("Data Structures", test_data_structures),
        ("Utilities", test_utilities),
        ("Async Features", test_async_features),
        ("Version Info", test_version_info),
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ {test_name} test crashed: {e}")
            failed += 1

    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed} passed, {failed} failed")

    if failed == 0:
        print("🎉 All tests passed! ByteBlaster is installed correctly.")
        print("\n📚 Next steps:")
        print("   - Run examples: python examples/example.py")
        print("   - Read documentation: README.md")
        print("   - Check out async examples: python examples/example_async_iterators.py")
        return 0
    print("❌ Some tests failed. Check the error messages above.")
    print("\n🔧 Troubleshooting:")
    print("   - Ensure Python 3.12+ is installed")
    print("   - Try reinstalling: pip install --force-reinstall byte-blaster")
    print("   - Check for dependency conflicts")
    return 1


if __name__ == "__main__":
    sys.exit(main())
