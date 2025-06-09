# Repository Setup and Configuration

This document outlines the required GitHub repository configuration for the `byte-blaster` project to ensure proper CI/CD, security, and release management.

## Branch Protection Rules

Configure the following branch protection rules for the `main` branch:

### Main Branch Protection

Navigate to: **Settings → Branches → Add rule**

**Branch name pattern**: `main`

#### Protection Settings

- ✅ **Require a pull request before merging**
  - ✅ Require approvals: `1`
  - ✅ Dismiss stale PR approvals when new commits are pushed
  - ✅ Require review from code owners
  - ✅ Restrict pushes that create files that change the code owners file

- ✅ **Require status checks to pass before merging**
  - ✅ Require branches to be up to date before merging
  - **Required status checks:**
    - `Lint and Format`
    - `Type Check`
    - `Test Python 3.12 on ubuntu-latest`
    - `Test Python 3.12 on windows-latest`
    - `Test Python 3.12 on macos-latest`
    - `Security Scan`
    - `Build Distribution`
    - `Validate Installation`

- ✅ **Require conversation resolution before merging**

- ✅ **Restrict pushes to matching branches**
  - **Who can push**: Repository administrators only

- ✅ **Force push**: Not allowed

- ✅ **Allow deletions**: Not allowed

### Develop Branch Protection (Optional)

If using a develop branch for integration:

**Branch name pattern**: `develop`

- ✅ **Require a pull request before merging**
  - ✅ Require approvals: `1`
- ✅ **Require status checks to pass before merging**
  - Same status checks as main branch

## Repository Secrets

Configure the following secrets in **Settings → Secrets and variables → Actions**:

### Required Secrets

#### PyPI Publishing
- `PYPI_API_TOKEN`: Your PyPI API token for publishing releases
  - Generate at: https://pypi.org/manage/account/token/
  - Scope: Entire account (or project-specific)

#### Optional Secrets
- `CODECOV_TOKEN`: For code coverage reporting (if using Codecov)
  - Generate at: https://codecov.io/

### Environment Configuration

Create a `pypi` environment in **Settings → Environments**:

#### PyPI Environment
- **Environment name**: `pypi`
- **Deployment protection rules**:
  - ✅ Required reviewers: Add repository administrators
  - ✅ Wait timer: 0 minutes (or desired delay)
- **Environment secrets**:
  - `PYPI_API_TOKEN`: Your PyPI API token

## Repository Settings

### General Settings

Navigate to **Settings → General**:

#### Features
- ✅ **Wikis**: Enabled (for additional documentation)
- ✅ **Issues**: Enabled
- ✅ **Sponsorships**: Enabled (if desired)
- ✅ **Preserve this repository**: Enabled
- ✅ **Discussions**: Enabled (for community interaction)

#### Pull Requests
- ✅ **Allow merge commits**: Disabled
- ✅ **Allow squash merging**: Enabled (recommended)
- ✅ **Allow rebase merging**: Enabled
- ✅ **Always suggest updating pull request branches**: Enabled
- ✅ **Allow auto-merge**: Enabled
- ✅ **Automatically delete head branches**: Enabled

#### Archives
- ✅ **Include Git LFS objects in archives**: Enabled

### Security Settings

Navigate to **Settings → Security**:

#### Security & Analysis
- ✅ **Dependency graph**: Enabled
- ✅ **Dependabot alerts**: Enabled
- ✅ **Dependabot security updates**: Enabled
- ✅ **Dependabot version updates**: Enabled (see dependabot.yml)
- ✅ **Code scanning**: Enabled
- ✅ **Secret scanning**: Enabled
- ✅ **Secret scanning push protection**: Enabled

## Dependabot Configuration

Create `.github/dependabot.yml`:

```yaml
version: 2
updates:
  # Python dependencies
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "weekly"
      day: "monday"
      time: "09:00"
    open-pull-requests-limit: 10
    labels:
      - "dependencies"
      - "python"
    commit-message:
      prefix: "chore"
      include: "scope"

  # GitHub Actions
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
      day: "monday"
      time: "09:00"
    open-pull-requests-limit: 5
    labels:
      - "dependencies"
      - "github-actions"
    commit-message:
      prefix: "chore"
      include: "scope"
```

## Code Owners

Create `.github/CODEOWNERS`:

```
# Global owners
* @bradsjm

# Python source code
src/ @bradsjm
tests/ @bradsjm

# CI/CD and automation
.github/ @bradsjm
scripts/ @bradsjm

# Documentation
docs/ @bradsjm
*.md @bradsjm

# Package configuration
pyproject.toml @bradsjm
requirements.txt @bradsjm
uv.lock @bradsjm
```

## Issue Templates

Create issue templates in `.github/ISSUE_TEMPLATE/`:

### Bug Report Template

`.github/ISSUE_TEMPLATE/bug_report.yml`:

```yaml
name: Bug Report
description: File a bug report
title: "[Bug]: "
labels: ["bug", "triage"]
body:
  - type: markdown
    attributes:
      value: |
        Thanks for taking the time to fill out this bug report!
  
  - type: input
    id: version
    attributes:
      label: Version
      description: What version of byte-blaster are you running?
      placeholder: "1.0.0"
    validations:
      required: true

  - type: input
    id: python-version
    attributes:
      label: Python Version
      description: What version of Python are you using?
      placeholder: "3.12.0"
    validations:
      required: true

  - type: textarea
    id: what-happened
    attributes:
      label: What happened?
      description: Also tell us, what did you expect to happen?
      placeholder: Tell us what you see!
    validations:
      required: true

  - type: textarea
    id: reproduction
    attributes:
      label: Steps to Reproduce
      description: How can we reproduce this issue?
      placeholder: |
        1. Import byteblaster
        2. Create client with options...
        3. See error
    validations:
      required: true

  - type: textarea
    id: logs
    attributes:
      label: Relevant log output
      description: Please copy and paste any relevant log output.
      render: shell
```

### Feature Request Template

`.github/ISSUE_TEMPLATE/feature_request.yml`:

```yaml
name: Feature Request
description: Suggest an idea for this project
title: "[Feature]: "
labels: ["enhancement", "triage"]
body:
  - type: markdown
    attributes:
      value: |
        Thanks for suggesting a new feature!

  - type: textarea
    id: problem
    attributes:
      label: Is your feature request related to a problem?
      description: A clear and concise description of what the problem is.
      placeholder: I'm always frustrated when...
    validations:
      required: true

  - type: textarea
    id: solution
    attributes:
      label: Describe the solution you'd like
      description: A clear and concise description of what you want to happen.
    validations:
      required: true

  - type: textarea
    id: alternatives
    attributes:
      label: Describe alternatives you've considered
      description: A clear and concise description of any alternative solutions or features you've considered.

  - type: textarea
    id: additional-context
    attributes:
      label: Additional context
      description: Add any other context or screenshots about the feature request here.
```

## Pull Request Template

Create `.github/pull_request_template.md`:

```markdown
## Description

Brief description of the changes in this PR.

## Type of Change

- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update
- [ ] Performance improvement
- [ ] Code refactoring
- [ ] Dependency update

## How Has This Been Tested?

- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Manual testing performed
- [ ] Type checking passes
- [ ] Linting passes

## Checklist

- [ ] My code follows the project's style guidelines
- [ ] I have performed a self-review of my own code
- [ ] I have commented my code, particularly in hard-to-understand areas
- [ ] I have made corresponding changes to the documentation
- [ ] My changes generate no new warnings
- [ ] I have added tests that prove my fix is effective or that my feature works
- [ ] New and existing unit tests pass locally with my changes
- [ ] Any dependent changes have been merged and published

## Breaking Changes

If this PR introduces breaking changes, describe them here and update the version appropriately.

## Additional Notes

Any additional information that reviewers should know about this PR.
```

## Repository Labels

Configure the following labels in **Issues → Labels**:

### Priority Labels
- `priority: low` - Low priority (color: #0E8A16)
- `priority: medium` - Medium priority (color: #FBCA04)
- `priority: high` - High priority (color: #D93F0B)
- `priority: critical` - Critical priority (color: #B60205)

### Type Labels
- `type: bug` - Something isn't working (color: #D73A4A)
- `type: enhancement` - New feature or request (color: #A2EEEF)
- `type: documentation` - Improvements or additions to documentation (color: #0075CA)
- `type: question` - Further information is requested (color: #D876E3)

### Status Labels
- `status: triage` - Needs triage (color: #FBCA04)
- `status: in-progress` - Currently being worked on (color: #0E8A16)
- `status: blocked` - Blocked by external dependency (color: #B60205)
- `status: waiting-for-feedback` - Waiting for feedback (color: #FBCA04)

### Component Labels
- `component: ci` - CI/CD related (color: #1D76DB)
- `component: typing` - Type checking related (color: #5319E7)
- `component: security` - Security related (color: #D93F0B)
- `component: dependencies` - Dependencies (color: #0366D6)

## Automated Setup Script

For easier setup, you can use the GitHub CLI:

```bash
#!/bin/bash
# setup-repo.sh - Automated repository setup

# Set branch protection for main
gh api repos/:owner/:repo/branches/main/protection \
  --method PUT \
  --field required_status_checks='{"strict":true,"contexts":["Lint and Format","Type Check","Test Python 3.12 on ubuntu-latest","Security Scan","Build Distribution"]}' \
  --field enforce_admins=true \
  --field required_pull_request_reviews='{"required_approving_review_count":1,"dismiss_stale_reviews":true}' \
  --field restrictions=null

# Enable security features
gh api repos/:owner/:repo --method PATCH \
  --field has_vulnerability_alerts=true \
  --field has_dependabot_alerts=true \
  --field has_dependabot_security_updates=true

echo "Repository configured successfully!"
```

## Monitoring and Maintenance

### Weekly Tasks
- Review Dependabot PRs
- Check security alerts
- Review failed workflow runs

### Monthly Tasks
- Review and update branch protection rules
- Audit repository access permissions
- Update documentation as needed

### Quarterly Tasks
- Review and update CI/CD workflows
- Security audit of dependencies
- Performance review of build times

## Troubleshooting

### Common Issues

#### CI Fails on First Run
- Ensure all required secrets are configured
- Check that branch protection rules match workflow job names
- Verify Python version compatibility

#### Type Checking Failures
- Ensure basedpyright is properly installed in CI
- Check that py.typed file is included in package
- Validate typing configuration

#### PyPI Publishing Failures
- Verify PYPI_API_TOKEN is correctly configured
- Check that package name is available on PyPI
- Ensure version number follows semantic versioning

For additional help, check the workflow logs in the Actions tab or create an issue.