#!/usr/bin/env python3
"""Release management script for byte-blaster.

This script helps manage releases by:
- Validating version numbers
- Updating pyproject.toml
- Creating git tags
- Generating changelogs
- Running pre-release checks
"""

import argparse
import logging
import re
import subprocess
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import NamedTuple

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


class Version(NamedTuple):
    """Semantic version representation."""

    major: int
    minor: int
    patch: int
    prerelease: str = ""

    @classmethod
    def parse(cls, version_str: str) -> "Version":
        """Parse a version string into components.

        Args:
            version_str: Version string to parse

        Returns:
            Parsed version object

        Raises:
            ValueError: If version format is invalid

        """
        pattern = r"^(\d+)\.(\d+)\.(\d+)(?:-(.+))?$"
        match = re.match(pattern, version_str)
        if not match:
            msg = f"Invalid version format: {version_str}"
            raise ValueError(msg)

        major, minor, patch, prerelease = match.groups()
        return cls(
            major=int(major),
            minor=int(minor),
            patch=int(patch),
            prerelease=prerelease or "",
        )

    def __str__(self) -> str:
        """Convert version back to string."""
        version = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            version += f"-{self.prerelease}"
        return version

    def bump(self, part: str) -> "Version":
        """Bump version by the specified part.

        Args:
            part: Version part to bump (major, minor, or patch)

        Returns:
            New version with bumped part

        Raises:
            ValueError: If part is invalid

        """
        if part == "major":
            return Version(self.major + 1, 0, 0)
        if part == "minor":
            return Version(self.major, self.minor + 1, 0)
        if part == "patch":
            return Version(self.major, self.minor, self.patch + 1)

        msg = f"Invalid version part: {part}"
        raise ValueError(msg)


class CommandResult(NamedTuple):
    """Result of running a command."""

    exit_code: int
    stdout: str
    stderr: str


def run_command(cmd: Sequence[str], *, check: bool = True) -> CommandResult:
    """Run a command and return exit code, stdout, stderr.

    Args:
        cmd: Command and arguments to run
        check: Whether to raise exception on non-zero exit code

    Returns:
        Command result with exit code, stdout, and stderr

    """
    try:
        result = subprocess.run(  # noqa: S603
            cmd,
            capture_output=True,
            text=True,
            check=check,
            timeout=300,  # 5 minute timeout
        )
        return CommandResult(result.returncode, result.stdout.strip(), result.stderr.strip())
    except subprocess.CalledProcessError as e:
        return CommandResult(e.returncode, e.stdout.strip(), e.stderr.strip())
    except subprocess.TimeoutExpired:
        return CommandResult(1, "", "Command timed out")


def get_current_version() -> Version:
    """Get current version from pyproject.toml.

    Returns:
        Current version

    Raises:
        FileNotFoundError: If pyproject.toml not found
        ValueError: If version not found in file

    """
    pyproject_path = Path("pyproject.toml")
    if not pyproject_path.exists():
        msg = "pyproject.toml not found"
        raise FileNotFoundError(msg)

    content = pyproject_path.read_text(encoding="utf-8")
    match = re.search(r'version = "([^"]+)"', content)
    if not match:
        msg = "Version not found in pyproject.toml"
        raise ValueError(msg)

    return Version.parse(match.group(1))


def update_version_in_pyproject(new_version: Version) -> None:
    """Update version in pyproject.toml.

    Args:
        new_version: New version to set

    """
    pyproject_path = Path("pyproject.toml")
    content = pyproject_path.read_text(encoding="utf-8")

    # Update version
    new_content = re.sub(r'version = "[^"]+"', f'version = "{new_version}"', content)

    pyproject_path.write_text(new_content, encoding="utf-8")
    logger.info("✅ Updated pyproject.toml version to %s", new_version)


def update_version_in_init(new_version: Version) -> None:
    """Update version in __init__.py.

    Args:
        new_version: New version to set

    """
    init_path = Path("src/byteblaster/__init__.py")
    if not init_path.exists():
        return

    content = init_path.read_text(encoding="utf-8")
    new_content = re.sub(r'__version__ = "[^"]+"', f'__version__ = "{new_version}"', content)

    if new_content != content:
        init_path.write_text(new_content, encoding="utf-8")
        logger.info("✅ Updated __init__.py version to %s", new_version)


def run_pre_release_checks() -> bool:
    """Run comprehensive pre-release checks.

    Returns:
        True if all checks pass, False otherwise

    """
    logger.info("🔍 Running pre-release checks...")

    checks = [
        (["uv", "run", "ruff", "format", "--check"], "Code formatting"),
        (["uv", "run", "ruff", "check"], "Linting"),
        (["uv", "run", "basedpyright", "src/byteblaster"], "Type checking"),
        (["uv", "run", "pytest"], "Tests"),
        (["uv", "run", "python", "scripts/validate_typing.py"], "Typing validation"),
        (["uv", "run", "python", "-m", "build"], "Build"),
    ]

    all_passed = True
    for cmd, description in checks:
        logger.info("  Running %s...", description)
        result = run_command(cmd, check=False)

        if result.exit_code == 0:
            logger.info("  ✅ %s passed", description)
        else:
            logger.error("  ❌ %s failed", description)
            if result.stdout:
                logger.error("     stdout: %s", result.stdout)
            if result.stderr:
                logger.error("     stderr: %s", result.stderr)
            all_passed = False

    return all_passed


def get_git_changes_since_tag(tag: str) -> list[str]:
    """Get git commit messages since the specified tag.

    Args:
        tag: Git tag to compare from

    Returns:
        List of commit messages since the tag

    """
    result = run_command(["git", "log", f"{tag}..HEAD", "--oneline", "--no-merges"], check=False)

    if result.exit_code != 0:
        return []

    return [line.strip() for line in result.stdout.split("\n") if line.strip()]


def generate_changelog_entry(version: Version) -> str:
    """Generate changelog entry for the new version.

    Args:
        version: Version to generate changelog for

    Returns:
        Formatted changelog entry

    """
    # Get the latest tag
    result = run_command(["git", "describe", "--tags", "--abbrev=0"], check=False)

    if result.exit_code == 0 and result.stdout:
        latest_tag = result.stdout.strip()
        changes = get_git_changes_since_tag(latest_tag)
    else:
        changes = []

    # Generate changelog entry
    date_str = datetime.now(UTC).strftime("%Y-%m-%d")
    entry = f"\n## [{version}] - {date_str}\n\n"

    if changes:
        entry += "### Changes\n\n"
        for change in changes:
            # Clean up commit message
            clean_change = re.sub(r"^[a-f0-9]+\s+", "", change)
            entry += f"- {clean_change}\n"
    else:
        entry += "### Changes\n\n- Initial release\n"

    return entry


def update_changelog(version: Version) -> None:
    """Update CHANGELOG.md with new version entry.

    Args:
        version: Version to add to changelog

    """
    changelog_path = Path("CHANGELOG.md")

    if not changelog_path.exists():
        # Create new changelog
        content = (
            "# Changelog\n\n"
            "All notable changes to this project will be documented in this file.\n\n"
            "The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).\n"
        )
    else:
        content = changelog_path.read_text(encoding="utf-8")

    # Generate new entry
    new_entry = generate_changelog_entry(version)

    # Insert after the header
    lines = content.split("\n")
    insert_index = 3  # After header lines
    for i, line in enumerate(lines):
        if line.startswith("## ["):
            insert_index = i
            break

    lines.insert(insert_index, new_entry.rstrip())

    changelog_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("✅ Updated CHANGELOG.md with version %s", version)


def create_git_tag(version: Version) -> None:
    """Create and push git tag for the release.

    Args:
        version: Version to tag

    """
    tag_name = f"v{version}"

    # Create tag
    result = run_command(["git", "tag", "-a", tag_name, "-m", f"Release {version}"], check=False)

    if result.exit_code != 0:
        logger.error("❌ Failed to create tag: %s", result.stderr)
        return

    logger.info("✅ Created git tag %s", tag_name)

    # Ask if we should push
    response = input(f"Push tag {tag_name} to origin? [y/N]: ")
    if response.lower() in ("y", "yes"):
        push_result = run_command(["git", "push", "origin", tag_name], check=False)

        if push_result.exit_code == 0:
            logger.info("✅ Pushed tag %s to origin", tag_name)
        else:
            logger.error("❌ Failed to push tag: %s", push_result.stderr)


def handle_check_action() -> None:
    """Handle the check action."""
    logger.info("\n🔍 Running release checks...")
    if run_pre_release_checks():
        logger.info("\n✅ All checks passed! Ready for release.")
        sys.exit(0)
    else:
        logger.error("\n❌ Some checks failed. Please fix issues before releasing.")
        sys.exit(1)


def handle_bump_action(args: argparse.Namespace, current_version: Version) -> None:
    """Handle the bump action.

    Args:
        args: Parsed command line arguments
        current_version: Current version

    """
    if not args.part:
        logger.error("❌ --part is required for bump action")
        sys.exit(1)

    new_version = current_version.bump(args.part)
    logger.info("New version: %s", new_version)

    if args.dry_run:
        logger.info("🔍 Dry run - no changes made")
        return

    # Update version files
    update_version_in_pyproject(new_version)
    update_version_in_init(new_version)

    # Commit changes
    add_result = run_command(
        ["git", "add", "pyproject.toml", "src/byteblaster/__init__.py"], check=False
    )

    if add_result.exit_code == 0:
        commit_result = run_command(
            [
                "git",
                "commit",
                "-m",
                f"bump: version {current_version} → {new_version}",
            ],
            check=False,
        )
        if commit_result.exit_code == 0:
            logger.info("✅ Committed version bump")
        else:
            logger.error("❌ Failed to commit: %s", commit_result.stderr)


def handle_release_action(args: argparse.Namespace) -> None:
    """Handle the release action.

    Args:
        args: Parsed command line arguments

    """
    if not args.version:
        logger.error("❌ --version is required for release action")
        sys.exit(1)

    new_version = Version.parse(args.version)
    logger.info("Releasing version: %s", new_version)

    if args.dry_run:
        logger.info("🔍 Dry run - no changes made")
        return

    # Run pre-release checks
    if not args.skip_checks and not run_pre_release_checks():
        logger.error("❌ Pre-release checks failed")
        sys.exit(1)

    # Update version
    update_version_in_pyproject(new_version)
    update_version_in_init(new_version)

    # Update changelog
    update_changelog(new_version)

    # Commit changes
    files_to_commit = [
        "pyproject.toml",
        "src/byteblaster/__init__.py",
        "CHANGELOG.md",
    ]
    add_result = run_command(["git", "add", *files_to_commit], check=False)
    if add_result.exit_code == 0:
        commit_result = run_command(
            ["git", "commit", "-m", f"release: version {new_version}"], check=False
        )
        if commit_result.exit_code == 0:
            logger.info("✅ Committed release changes")

    # Create tag
    create_git_tag(new_version)

    logger.info("\n🎉 Release %s completed!", new_version)
    logger.info("   Tag created: v%s", new_version)
    logger.info("   To trigger CI release, push the tag to GitHub")


def main() -> None:
    """Execute release script actions."""
    parser = argparse.ArgumentParser(description="Release management for byte-blaster")
    parser.add_argument("action", choices=["check", "bump", "release"], help="Action to perform")
    parser.add_argument(
        "--part",
        choices=["major", "minor", "patch"],
        help="Version part to bump (for bump action)",
    )
    parser.add_argument("--version", help="Specific version to release (for release action)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    parser.add_argument("--skip-checks", action="store_true", help="Skip pre-release checks")

    args = parser.parse_args()

    try:
        current_version = get_current_version()
        logger.info("Current version: %s", current_version)

        if args.action == "check":
            handle_check_action()
        elif args.action == "bump":
            handle_bump_action(args, current_version)
        elif args.action == "release":
            handle_release_action(args)

    except (FileNotFoundError, ValueError, subprocess.SubprocessError):
        logger.exception("❌ Error occurred")
        sys.exit(1)


if __name__ == "__main__":
    main()
