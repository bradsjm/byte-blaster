# Release Process

This document outlines the complete release process for the `byte-blaster` library, from development to publication.

## Overview

The release process is designed to ensure:
- 📋 **Quality**: All code is thoroughly tested and reviewed
- 🔒 **Security**: Dependencies are scanned and vulnerabilities addressed
- 📖 **Documentation**: Changes are properly documented
- 🏷️ **Versioning**: Semantic versioning is followed
- 🚀 **Automation**: Manual steps are minimized through CI/CD

## Release Types

### Semantic Versioning

We follow [Semantic Versioning 2.0.0](https://semver.org/):

- **MAJOR** (`X.0.0`): Breaking changes that require user code updates
- **MINOR** (`1.X.0`): New features that are backward compatible
- **PATCH** (`1.0.X`): Backward compatible bug fixes

### Pre-release Versions

- **Alpha** (`1.0.0-alpha.1`): Early development, unstable
- **Beta** (`1.0.0-beta.1`): Feature complete, testing phase
- **Release Candidate** (`1.0.0-rc.1`): Final testing before stable release

## Development Workflow

### 1. Feature Development

```bash
# Create feature branch
git checkout main
git pull origin main
git checkout -b feature/your-feature-name

# Develop and commit changes
git add .
git commit -m "feat: add new feature"

# Push and create PR
git push origin feature/your-feature-name
```

### 2. Pull Request Process

1. **Create PR** with descriptive title and complete template
2. **Automated Checks** run (CI pipeline)
3. **Code Review** by maintainers
4. **Address Feedback** and update PR
5. **Final Approval** and merge to main

### 3. Quality Gates

All PRs must pass:
- ✅ Code formatting (`ruff format`)
- ✅ Linting (`ruff check`)
- ✅ Type checking (`basedpyright`)
- ✅ Unit tests (`pytest`)
- ✅ Security scan (`bandit`, `safety`)
- ✅ Typing validation
- ✅ Build verification

## Release Preparation

### 1. Pre-release Checklist

Before starting a release, ensure:

- [ ] All planned features/fixes are merged to `main`
- [ ] All tests pass on supported Python versions (3.12+)
- [ ] Documentation is up to date
- [ ] No known security vulnerabilities
- [ ] Dependencies are up to date
- [ ] Breaking changes are documented

### 2. Version Planning

Determine the appropriate version bump:

```bash
# Check current version
python -c "from byteblaster import __version__; print(__version__)"

# Or from pyproject.toml
grep "version =" pyproject.toml
```

**Version Bump Guidelines:**
- 🔴 **Major**: API changes, removed features, breaking changes
- 🟡 **Minor**: New features, significant improvements
- 🟢 **Patch**: Bug fixes, documentation updates, minor improvements

### 3. Release Branch (for Major/Minor releases)

For significant releases, create a release branch:

```bash
git checkout main
git pull origin main
git checkout -b release/v1.2.0
```

## Release Execution

### Method 1: Automated Release (Recommended)

#### Using the Release Script

```bash
# Check readiness
python scripts/release.py check

# For patch releases
python scripts/release.py bump --part patch

# For minor releases  
python scripts/release.py bump --part minor

# For major releases
python scripts/release.py bump --part major

# Create release with specific version
python scripts/release.py release --version "1.2.0"
```

#### Using GitHub UI

1. **Navigate** to GitHub repository
2. **Click** "Releases" → "Create a new release"
3. **Choose** tag version (e.g., `v1.2.0`)
4. **Set** release title and description
5. **Select** "Publish release"

This triggers the automated release workflow.

### Method 2: Manual Release

#### Step 1: Update Version

```bash
# Update pyproject.toml
sed -i 's/version = ".*"/version = "1.2.0"/' pyproject.toml

# Update __init__.py
sed -i 's/__version__ = ".*"/__version__ = "1.2.0"/' src/byteblaster/__init__.py
```

#### Step 2: Update Changelog

Add entry to `CHANGELOG.md`:

```markdown
## [1.2.0] - 2024-01-15

### Added
- New feature X
- Enhanced Y functionality

### Changed
- Improved Z performance

### Fixed
- Bug in A component
- Issue with B behavior

### Security
- Updated dependency C to address CVE-XXXX-XXXX
```

#### Step 3: Commit and Tag

```bash
# Commit changes
git add pyproject.toml src/byteblaster/__init__.py CHANGELOG.md
git commit -m "release: version 1.2.0"

# Create and push tag
git tag -a v1.2.0 -m "Release 1.2.0"
git push origin main
git push origin v1.2.0
```

## Automated Release Pipeline

When a tag is pushed, the release workflow automatically:

### 1. Validation Phase
- ✅ Validates tag format
- ✅ Runs full test suite
- ✅ Performs security scan
- ✅ Validates typing configuration

### 2. Build Phase
- 📦 Updates version in pyproject.toml
- 📦 Builds wheel and source distribution
- 📦 Validates package contents
- 📦 Checks package metadata

### 3. Security Phase
- 🔒 Scans built package for vulnerabilities
- 🔒 Verifies no malicious code
- 🔒 Checks dependency security

### 4. Publishing Phase
- 🚀 Publishes to PyPI using trusted publishing
- 🚀 Creates GitHub release with artifacts
- 🚀 Generates release notes

### 5. Notification Phase
- 📧 Notifies maintainers of success/failure
- 📧 Updates status badges
- 📧 Triggers downstream notifications

## Post-release Tasks

### 1. Verification

```bash
# Install from PyPI
pip install byte-blaster==1.2.0

# Verify installation
python -c "import byteblaster; print(byteblaster.__version__)"

# Test basic functionality
python -c "from byteblaster import ByteBlasterClient; print('✅ Import successful')"
```

### 2. Documentation Updates

- [ ] Update README badges
- [ ] Update documentation website
- [ ] Update examples if needed
- [ ] Announce on relevant channels

### 3. Monitoring

Monitor for 24-48 hours after release:
- 📊 PyPI download statistics
- 🐛 Issue reports
- 📱 Social media mentions
- 📈 Dependency scanning results

## Hotfix Process

For critical bug fixes that need immediate release:

### 1. Create Hotfix Branch

```bash
git checkout v1.2.0  # Latest release tag
git checkout -b hotfix/critical-fix
```

### 2. Apply Fix

```bash
# Make minimal changes to fix the issue
git add .
git commit -m "fix: critical security issue"
```

### 3. Release Hotfix

```bash
# Bump patch version
python scripts/release.py release --version "1.2.1"

# Or manually
git tag -a v1.2.1 -m "Hotfix 1.2.1"
git push origin v1.2.1
```

### 4. Merge Back

```bash
# Merge hotfix back to main
git checkout main
git merge hotfix/critical-fix
git push origin main
```

## Release Rollback

If a release has critical issues:

### 1. Immediate Actions

```bash
# Mark release as pre-release on GitHub
# (This hides it from latest release)

# Or delete the release entirely
gh release delete v1.2.0
```

### 2. PyPI Actions

```bash
# Yank the release (makes it unavailable for new installs)
# This requires PyPI permissions and should be done via web interface
```

### 3. Communication

- 📢 Update release notes with warning
- 📢 Notify users via appropriate channels
- 📢 Document known issues
- 📢 Provide workaround instructions

## Troubleshooting

### Common Issues

#### Release Workflow Fails

**Symptoms**: GitHub Actions workflow fails during release

**Solutions**:
1. Check workflow logs for specific errors
2. Verify all secrets are configured correctly
3. Ensure PyPI token has correct permissions
4. Check for network/service outages

#### Type Checking Failures

**Symptoms**: `basedpyright` reports errors in CI

**Solutions**:
1. Run locally: `uv run basedpyright src/byteblaster`
2. Check `pyrightconfig.json` configuration
3. Verify all imports are properly typed
4. Update type annotations as needed

#### Build Failures

**Symptoms**: Package build fails

**Solutions**:
1. Check `pyproject.toml` syntax
2. Verify all files are included in MANIFEST.in
3. Test build locally: `uv run python -m build`
4. Check for missing dependencies

#### PyPI Upload Failures

**Symptoms**: Package upload to PyPI fails

**Solutions**:
1. Verify PyPI token is valid and has upload permissions
2. Check package name isn't already taken
3. Ensure version number isn't already published
4. Verify package metadata is valid

### Getting Help

If you encounter issues not covered here:

1. **Check** the GitHub Actions logs first
2. **Search** existing issues in the repository
3. **Create** a new issue with detailed information:
   - Release version being attempted
   - Error messages
   - Steps taken
   - Environment details

## Security Considerations

### API Token Management

- 🔐 **Rotate** PyPI tokens regularly
- 🔐 **Use** environment-specific tokens when possible
- 🔐 **Monitor** token usage and permissions
- 🔐 **Revoke** tokens immediately if compromised

### Release Integrity

- ✅ **Verify** all releases are signed
- ✅ **Check** package checksums
- ✅ **Monitor** for unauthorized releases
- ✅ **Use** trusted publishing when available

### Dependency Security

- 🔍 **Scan** dependencies before each release
- 🔍 **Monitor** security advisories
- 🔍 **Update** vulnerable dependencies promptly
- 🔍 **Document** security-related changes

## Metrics and Analytics

### Release Metrics

Track the following for each release:
- 📊 Time from tag to PyPI availability
- 📊 Download counts and trends
- 📊 Issue reports within 48 hours
- 📊 Community feedback and adoption

### Quality Metrics

Monitor ongoing quality indicators:
- 📈 Test coverage percentage
- 📈 Type coverage percentage
- 📈 Security scan results
- 📈 Documentation completeness

### Performance Metrics

Track performance impact:
- ⚡ Package size changes
- ⚡ Import time measurements
- ⚡ Runtime performance benchmarks
- ⚡ Memory usage patterns

## Continuous Improvement

### Release Retrospectives

After each major release, conduct a retrospective:
- ❓ What went well?
- ❓ What could be improved?
- ❓ Any process changes needed?
- ❓ Tools or automation opportunities?

### Process Updates

Regular review and update of:
- 📝 This documentation
- 📝 GitHub Actions workflows
- 📝 Release automation scripts
- 📝 Quality gates and checks

---

## Quick Reference

### Essential Commands

```bash
# Check release readiness
python scripts/release.py check

# Bump version and create release
python scripts/release.py release --version "1.2.0"

# Manual verification
uv run python scripts/validate_typing.py
uv run pytest
uv run basedpyright src/byteblaster

# Emergency rollback
gh release delete v1.2.0
```

### Key Files

- `pyproject.toml` - Package metadata and version
- `CHANGELOG.md` - Release notes and history
- `src/byteblaster/__init__.py` - Version string
- `.github/workflows/release.yml` - Release automation
- `scripts/release.py` - Release management script

### Important Links

- [PyPI Project Page](https://pypi.org/project/byte-blaster/)
- [GitHub Releases](https://github.com/bradsjm/byte-blaster/releases)
- [Actions Dashboard](https://github.com/bradsjm/byte-blaster/actions)
- [Security Advisories](https://github.com/bradsjm/byte-blaster/security)

---

*This document is version-controlled and should be updated with any process changes.*