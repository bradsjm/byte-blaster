# Setup Instructions for CI/CD and Release Management

This document provides step-by-step instructions to implement the complete CI/CD pipeline and release management system for the `byte-blaster` project.

## Prerequisites

Before starting, ensure you have:
- ✅ GitHub repository created and cloned locally
- ✅ Python 3.12+ installed
- ✅ `uv` package manager installed
- ✅ GitHub CLI (`gh`) installed (optional but recommended)
- ✅ Repository admin access

## Step 1: Repository Configuration

### 1.1 Enable Repository Features

Navigate to **Settings → General** and configure:

```
Features:
☑️ Issues
☑️ Wiki  
☑️ Discussions (optional)
☑️ Preserve this repository

Pull Requests:
☐ Allow merge commits
☑️ Allow squash merging  
☑️ Allow rebase merging
☑️ Always suggest updating pull request branches
☑️ Allow auto-merge
☑️ Automatically delete head branches
```

### 1.2 Enable Security Features

Navigate to **Settings → Security & analysis**:

```
☑️ Dependency graph
☑️ Dependabot alerts
☑️ Dependabot security updates  
☑️ Dependabot version updates
☑️ Code scanning alerts
☑️ Secret scanning
☑️ Secret scanning push protection
```

## Step 2: Branch Protection

### 2.1 Protect Main Branch

Navigate to **Settings → Branches → Add rule**:

```
Branch name pattern: main

Protection settings:
☑️ Require a pull request before merging
  ☑️ Require approvals: 1
  ☑️ Dismiss stale PR approvals when new commits are pushed
  ☑️ Require review from code owners

☑️ Require status checks to pass before merging
  ☑️ Require branches to be up to date before merging
  Required status checks:
  - Lint and Format
  - Type Check  
  - Test Python 3.12 on ubuntu-latest
  - Test Python 3.12 on windows-latest
  - Test Python 3.12 on macos-latest
  - Security Scan
  - Build Distribution
  - Validate Installation

☑️ Require conversation resolution before merging
☑️ Restrict pushes to matching branches
☐ Force push (not allowed)
☐ Allow deletions (not allowed)
```

## Step 3: Repository Secrets

### 3.1 Create PyPI API Token

1. Go to [PyPI Account Settings](https://pypi.org/manage/account/token/)
2. Click "Add API token"
3. Name: `byte-blaster-ci`
4. Scope: `Entire account` (or project-specific after first upload)
5. Copy the token (starts with `pypi-`)

### 3.2 Add Secrets to GitHub

Navigate to **Settings → Secrets and variables → Actions**:

```
Repository secrets:
Name: PYPI_API_TOKEN
Value: pypi-AgEIcHlwaS5vcmcC... (your token)

Optional secrets:
Name: CODECOV_TOKEN  
Value: (if using Codecov for coverage)
```

### 3.3 Create Environment

Navigate to **Settings → Environments**:

```
Environment name: pypi

Deployment protection rules:
☑️ Required reviewers: [your-username]
☑️ Wait timer: 0 minutes

Environment secrets:
Name: PYPI_API_TOKEN
Value: pypi-AgEIcHlwaS5vcmcC... (same token)
```

## Step 4: File Validation

Verify all configuration files are in place:

### 4.1 Check Workflow Files
```bash
ls -la .github/workflows/
# Should show: ci.yml, release.yml, dependency-update.yml
```

### 4.2 Check Templates
```bash
ls -la .github/ISSUE_TEMPLATE/
# Should show: bug_report.yml, feature_request.yml

ls -la .github/
# Should show: CODEOWNERS, dependabot.yml, pull_request_template.md
```

### 4.3 Check Scripts
```bash
ls -la scripts/
# Should show: release.py (executable)

chmod +x scripts/release.py  # Make executable if needed
```

## Step 5: Initial Validation

### 5.1 Test Local Build
```bash
# Install dependencies
uv sync --dev

# Run validation
uv run python scripts/validate_typing.py

# Test build
uv run python -m build
```

### 5.2 Test Release Script
```bash
# Check current setup
python scripts/release.py check

# This should pass all pre-release checks
```

## Step 6: First CI Run

### 6.1 Push Configuration
```bash
# Add all new files
git add .github/ scripts/ docs/ .pre-commit-config.yaml

# Commit
git commit -m "ci: add comprehensive CI/CD pipeline and release automation"

# Push to trigger first CI run
git push origin main
```

### 6.2 Monitor First Run

1. Go to **Actions** tab in GitHub
2. Watch the CI workflow run
3. Fix any issues that arise
4. Common first-run issues:
   - Missing dependencies in CI
   - Path issues in workflows
   - Permission problems

## Step 7: Pre-commit Setup (Optional)

### 7.1 Install Pre-commit
```bash
# Install pre-commit
uv add --dev pre-commit

# Install hooks
uv run pre-commit install

# Test hooks
uv run pre-commit run --all-files
```

### 7.2 Configure Git Hooks
```bash
# Install both pre-commit and pre-push hooks
uv run pre-commit install --hook-type pre-commit
uv run pre-commit install --hook-type pre-push
```

## Step 8: Test Release Process

### 8.1 Create Test Release

**Option A: Using Release Script**
```bash
# Create a test release (don't push tag yet)
python scripts/release.py release --version "1.0.0" --dry-run
```

**Option B: Manual Test**
```bash
# Update version manually
sed -i 's/version = ".*"/version = "1.0.0"/' pyproject.toml

# Test build
uv run python -m build

# Validate
uv run python scripts/validate_typing.py
```

### 8.2 Test Tag Creation
```bash
# Create and push tag to test release workflow
git tag v1.0.0-test
git push origin v1.0.0-test

# Monitor release workflow in Actions tab
# Delete test tag afterward:
git tag -d v1.0.0-test
git push origin :refs/tags/v1.0.0-test
```

## Step 9: Documentation Updates

### 9.1 Update README Badges

Add to your README.md:
```markdown
[![CI](https://github.com/bradsjm/byte-blaster/workflows/CI/badge.svg)](https://github.com/bradsjm/byte-blaster/actions?query=workflow%3ACI)
[![PyPI version](https://badge.fury.io/py/byte-blaster.svg)](https://badge.fury.io/py/byte-blaster)
[![Python versions](https://img.shields.io/pypi/pyversions/byte-blaster.svg)](https://pypi.org/project/byte-blaster/)
[![License](https://img.shields.io/pypi/l/byte-blaster.svg)](https://github.com/bradsjm/byte-blaster/blob/main/LICENSE)
[![Code style: ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Type checked: basedpyright](https://img.shields.io/badge/type%20checker-basedpyright-informational)](https://github.com/DetachHead/basedpyright)
```

### 9.2 Add Security Policy

Create `SECURITY.md`:
```markdown
# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.x.x   | :white_check_mark: |

## Reporting a Vulnerability

Please report security vulnerabilities to security@your-domain.com
or create a private security advisory on GitHub.
```

## Step 10: Team Setup (if applicable)

### 10.1 Add Collaborators
Navigate to **Settings → Manage access**:
- Add team members with appropriate permissions
- Update CODEOWNERS file with team members

### 10.2 Update CODEOWNERS
```
# Update .github/CODEOWNERS
* @bradsjm @team-member-1 @team-member-2
```

## Step 11: Monitoring Setup

### 11.1 GitHub Notifications
Configure notification preferences in GitHub settings for:
- ✅ Issues and PRs
- ✅ Actions workflows
- ✅ Security alerts
- ✅ Dependabot

### 11.2 External Monitoring (Optional)
Consider setting up:
- Codecov for coverage tracking
- Sentry for error monitoring  
- PyPI download statistics monitoring

## Step 12: First Production Release

### 12.1 Prepare for Release
```bash
# Ensure main branch is clean and up to date
git checkout main
git pull origin main

# Run full validation
python scripts/release.py check
```

### 12.2 Create Release
```bash
# Create first production release
python scripts/release.py release --version "1.0.0"

# Or using GitHub UI:
# 1. Go to Releases → Create new release
# 2. Tag: v1.0.0
# 3. Title: Release v1.0.0  
# 4. Description: Initial stable release
# 5. Publish release
```

### 12.3 Verify Release
```bash
# Wait for workflow to complete, then test:
pip install byte-blaster==1.0.0
python -c "import byteblaster; print(byteblaster.__version__)"
```

## Troubleshooting

### Common Issues

**CI Workflow Fails**
- Check workflow logs in Actions tab
- Verify all secrets are configured
- Ensure branch protection rules match job names

**PyPI Upload Fails**  
- Verify PYPI_API_TOKEN is valid
- Check package name availability
- Ensure version number is unique

**Type Checking Fails**
- Run `uv run basedpyright src/byteblaster` locally
- Check pyrightconfig.json configuration
- Verify all imports are properly typed

**Build Fails**
- Check pyproject.toml syntax
- Verify MANIFEST.in includes all necessary files
- Test build locally: `uv run python -m build`

### Getting Help

1. Check GitHub Actions logs for specific errors
2. Review this documentation and referenced files
3. Search existing issues in the repository
4. Create new issue with detailed error information

## Maintenance Schedule

### Weekly
- [ ] Review Dependabot PRs
- [ ] Check for security alerts
- [ ] Monitor failed workflow runs

### Monthly  
- [ ] Review branch protection rules
- [ ] Audit repository permissions
- [ ] Update documentation

### Quarterly
- [ ] Review CI/CD workflows
- [ ] Security audit dependencies
- [ ] Performance review of build times

## Success Criteria

You'll know the setup is successful when:
- ✅ All CI checks pass on PRs
- ✅ Releases publish automatically to PyPI
- ✅ Security scanning runs without issues
- ✅ Type checking validates without errors
- ✅ Documentation builds correctly
- ✅ Team can contribute via standard PR process

---

**Next Steps:** Once setup is complete, refer to `docs/RELEASE_PROCESS.md` for ongoing release management and `docs/REPOSITORY_SETUP.md` for detailed configuration information.