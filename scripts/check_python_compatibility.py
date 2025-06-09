#!/usr/bin/env python3
"""Python version compatibility checker for byte-blaster.

This script validates that the current Python environment is compatible
with byte-blaster and provides detailed compatibility information.
"""

import logging
import platform
import subprocess
import sys
from typing import NamedTuple

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


class CompatibilityResult(NamedTuple):
    """Result of compatibility check."""

    is_compatible: bool
    python_version: str
    issues: list[str]
    recommendations: list[str]
    features_available: dict[str, bool]


def get_python_info() -> dict[str, str]:
    """Get comprehensive Python environment information.

    Returns:
        Dictionary containing Python environment details

    """
    return {
        "version": platform.python_version(),
        "version_info": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "implementation": platform.python_implementation(),
        "compiler": platform.python_compiler(),
        "build": platform.python_build()[0],
        "platform": platform.platform(),
        "architecture": platform.architecture()[0],
        "executable": sys.executable,
    }


def check_minimum_version() -> tuple[bool, list[str]]:
    """Check if Python version meets minimum requirements.

    Returns:
        Tuple of (is_compatible, list_of_issues)

    """
    issues: list[str] = []
    min_version = (3, 12)
    current_version = (sys.version_info.major, sys.version_info.minor)

    if current_version < min_version:
        issues.append(
            f"Python {min_version[0]}.{min_version[1]}+ required, "
            f"but {current_version[0]}.{current_version[1]} found",
        )
        return False, issues

    return True, issues


def check_language_features() -> dict[str, bool]:
    """Check availability of language features used by byte-blaster.

    Returns:
        Dictionary mapping feature names to availability

    """
    features: dict[str, bool] = {}

    # Test PEP 604: Union operator (Python 3.10+)
    try:
        exec("x: str | None = None")  # noqa: S102
        features["union_operator"] = True
    except SyntaxError:
        features["union_operator"] = False

    # Test PEP 585: Type Hinting Generics (Python 3.9+)
    try:
        exec("x: list[str] = []")  # noqa: S102
        features["generic_types"] = True
    except (SyntaxError, TypeError):
        features["generic_types"] = False

    # Test Enhanced error messages (Python 3.11+)
    features["enhanced_errors"] = sys.version_info >= (3, 11)

    # Test Performance improvements (Python 3.12+)
    features["performance_optimizations"] = sys.version_info >= (3, 12)

    # Test asyncio improvements (Python 3.11+)
    features["asyncio_improvements"] = sys.version_info >= (3, 11)

    # Test structural pattern matching (Python 3.10+)
    try:
        exec("""  # noqa: S102
match 1:
    case 1:
        pass
""")  # noqa: S102
        features["pattern_matching"] = True
    except SyntaxError:
        features["pattern_matching"] = False

    return features


def check_typing_support() -> tuple[bool, list[str]]:
    """Check typing system compatibility.

    Returns:
        Tuple of (is_compatible, list_of_issues)

    """
    issues: list[str] = []

    try:
        # Test basic typing imports
        import typing

        # Check if advanced typing features are available
        if not hasattr(typing, "get_origin"):
            issues.append("Advanced typing introspection not available")

        # Test dataclasses availability
        import dataclasses

        _ = dataclasses

        # Test pathlib availability
        from pathlib import Path

        _ = Path

    except ImportError as e:
        issues.append(f"Missing typing support: {e}")
        return False, issues

    return True, issues


def check_async_support() -> tuple[bool, list[str]]:
    """Check asyncio and async/await support.

    Returns:
        Tuple of (is_compatible, list_of_issues)

    """
    issues: list[str] = []

    try:
        import asyncio

        # Test async/await syntax
        exec("""  # noqa: S102
async def test_async():
    await asyncio.sleep(0)
""")  # noqa: S102

        # Test asyncio.run (Python 3.7+)
        if not hasattr(asyncio, "run"):
            issues.append("asyncio.run() not available")

        # Test TaskGroup (Python 3.11+)
        try:
            from asyncio import TaskGroup

            _ = TaskGroup
        except ImportError:
            issues.append("asyncio.TaskGroup not available")

    except (ImportError, SyntaxError) as e:
        issues.append(f"Async support issue: {e}")
        return False, issues

    return True, issues


def check_dependencies() -> tuple[bool, list[str]]:
    """Check if byte-blaster can be installed with current Python.

    Returns:
        Tuple of (is_compatible, list_of_issues)

    """
    issues: list[str] = []

    # Check if we can import byte-blaster (if installed)
    try:
        import byteblaster

        # If we can import it, check version compatibility
        version = getattr(byteblaster, "__version__", "unknown")
        logger.info("✅ byte-blaster %s is already installed and working", version)
    except ImportError:
        # Not installed, which is fine for compatibility check
        pass
    except (ValueError, TypeError, AttributeError) as e:
        issues.append(f"byte-blaster import error: {e}")

    # Check package manager compatibility (pip or uv)
    has_package_manager = False

    # Check for pip
    try:
        result = subprocess.run(  # noqa: S603
            [sys.executable, "-m", "pip", "--version"],
            capture_output=True,
            check=False,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            has_package_manager = True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Check for uv
    if not has_package_manager:
        try:
            result = subprocess.run(  # noqa: S603
                ["uv", "--version"],  # noqa: S607
                capture_output=True,
                check=False,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                has_package_manager = True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    if not has_package_manager:
        issues.append("No package manager (pip or uv) available")

    return len(issues) == 0, issues


def generate_recommendations(result: CompatibilityResult) -> list[str]:
    """Generate recommendations based on compatibility check.

    Args:
        result: Compatibility check result

    Returns:
        List of recommendations

    """
    recommendations: list[str] = []

    if not result.is_compatible:
        recommendations.extend(
            [
                "🔄 Upgrade to Python 3.12 or newer",
                "🐳 Consider using Docker with Python 3.12+ image",
                "🌐 Use pyenv or conda to manage Python versions",
                "📦 Create virtual environment with compatible Python version",
            ],
        )
    else:
        current_version = sys.version_info[:2]
        if current_version == (3, 12):
            recommendations.append(
                "✅ Great! Consider upgrading to Python 3.13 for better performance",
            )
        elif current_version >= (3, 13):
            recommendations.append("🚀 Excellent! You're using the latest Python version")

    # Feature-specific recommendations
    if not result.features_available.get("union_operator", True):
        recommendations.append(
            "⚠️  Union operator (|) not available - upgrade for better type annotations",
        )

    if not result.features_available.get("performance_optimizations", True):
        recommendations.append("⚡ Upgrade to Python 3.12+ for 10-15% performance improvement")

    return recommendations


def run_compatibility_check() -> CompatibilityResult:
    """Run comprehensive compatibility check.

    Returns:
        Comprehensive compatibility result

    """
    all_issues: list[str] = []

    # Check minimum version
    version_ok, version_issues = check_minimum_version()
    all_issues.extend(version_issues)

    # Check language features
    features = check_language_features()

    # Check typing support
    typing_ok, typing_issues = check_typing_support()
    all_issues.extend(typing_issues)

    # Check async support
    async_ok, async_issues = check_async_support()
    all_issues.extend(async_issues)

    # Check dependencies
    deps_ok, deps_issues = check_dependencies()
    all_issues.extend(deps_issues)

    # Overall compatibility
    is_compatible = version_ok and typing_ok and async_ok and deps_ok

    result = CompatibilityResult(
        is_compatible=is_compatible,
        python_version=platform.python_version(),
        issues=all_issues,
        recommendations=[],
        features_available=features,
    )

    # Generate recommendations
    return result._replace(recommendations=generate_recommendations(result))


def print_detailed_report(result: CompatibilityResult) -> None:
    """Print detailed compatibility report.

    Args:
        result: Compatibility check result

    """
    python_info = get_python_info()

    logger.info("🐍 Python Compatibility Check for byte-blaster")
    logger.info("=" * 60)

    # Python environment info
    logger.info("\n📋 Python Environment:")
    logger.info("  Version: %s", python_info["version"])
    logger.info("  Implementation: %s", python_info["implementation"])
    logger.info("  Platform: %s", python_info["platform"])
    logger.info("  Architecture: %s", python_info["architecture"])
    logger.info("  Executable: %s", python_info["executable"])

    # Compatibility status
    logger.info("\n🎯 Compatibility Status:")
    if result.is_compatible:
        logger.info("  ✅ COMPATIBLE - byte-blaster will work with this Python version")
    else:
        logger.info("  ❌ INCOMPATIBLE - byte-blaster requires a newer Python version")

    # Feature availability
    logger.info("\n🔧 Language Features:")
    for feature, available in result.features_available.items():
        status = "✅" if available else "❌"
        feature_name = feature.replace("_", " ").title()
        logger.info("  %s %s", status, feature_name)

    # Issues
    if result.issues:
        logger.info("\n⚠️  Issues Found:")
        for issue in result.issues:
            logger.info("  • %s", issue)

    # Recommendations
    if result.recommendations:
        logger.info("\n💡 Recommendations:")
        for rec in result.recommendations:
            logger.info("  %s", rec)

    # Installation commands
    if not result.is_compatible:
        logger.info("\n🔧 Upgrade Options:")
        logger.info("  # Using pyenv:")
        logger.info("  pyenv install 3.12.0")
        logger.info("  pyenv local 3.12.0")
        logger.info("")
        logger.info("  # Using conda:")
        logger.info("  conda create -n byte-blaster python=3.12")
        logger.info("  conda activate byte-blaster")
        logger.info("")
        logger.info("  # Using Docker:")
        logger.info("  docker run -it python:3.12-slim python")


def main() -> None:
    """Execute compatibility checker."""
    try:
        result = run_compatibility_check()
        print_detailed_report(result)

        # Exit with appropriate code
        if result.is_compatible:
            logger.info("\n🎉 Ready to install and use byte-blaster!")
            sys.exit(0)
        else:
            logger.info("\n❌ Please upgrade Python before using byte-blaster")
            sys.exit(1)

    except (OSError, subprocess.SubprocessError):
        logger.exception("\n💥 Error during compatibility check")
        logger.info("This might indicate a Python environment issue.")
        sys.exit(2)


if __name__ == "__main__":
    main()
