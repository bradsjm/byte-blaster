# Python Code Generation Instructions (Python 3.12+)

## Core Philosophy
Create production-grade, comprehensive solutions that go above and beyond basic requirements. Your code will be used in critical systems where reliability, maintainability, and correctness are paramount. Include as many relevant features, error handling scenarios, and best practices as possible unless otherwise instructed.

## Tool Usage Strategy (Critical)
**Use available tools proactively to mitigate errors and ensure accuracy:**

Before writing any code, use thinking capabilities to plan your approach, then:
1. **Research First**: Use documentation tools (`get-library-docs`, `resolve-library-id`) to verify API syntax and current best practices
2. **Understand Context**: Use file system tools (`grep`, `find_path`, `read_file`) to understand existing codebase patterns
3. **Parallel Tool Execution**: For maximum efficiency, invoke multiple independent tools simultaneously rather than sequentially
4. **Validate Continuously**: Check diagnostics frequently during development to catch issues early
5. **Final Verification**: Always run `ruff format`, `ruff check --fix`, and verify type checking passes

**Why this matters**: Tool usage prevents syntax errors, API misuse, and integration issues that waste development time and compromise code quality.

## Type System Requirements (Zero Tolerance)
**Complete typing prevents runtime errors and improves code maintainability:**

- **Type Everything**: Parameters, returns, attributes, critical variables - no exceptions
- **Modern Python 3.12+ Syntax Only**:
  ```python
  # Correct modern syntax
  type UserID = int
  type UserData = dict[str, str | int]
  def process_user(user_id: UserID) -> UserData | None:
  ```
- **Forbidden Legacy Syntax**: Never use `typing.TypeAlias`, `Union`, `List`, `Dict`, `Any`
- **Structured Data**: Replace nested dicts/tuples with dataclasses or Pydantic models
- **Runtime Safety**: Use `isinstance()` checks for `**kwargs`, `typing.cast()` only with string literals

**Code MUST pass `basedpyright` strict mode without any errors or warnings.**

## Quality Standards (Non-Negotiable)
**These limits ensure code remains maintainable and testable:**

- **Function Complexity**: ≤5 parameters, <10 cyclomatic complexity, ≤50 statements
- **Error Handling Excellence**:
  - Catch specific exceptions (`ValueError`, `ConnectionError`, `requests.HTTPError`)
  - Assign error messages to variables before raising: `msg = "Invalid input"; raise ValueError(msg)`
  - No bare except blocks (use `# noqa: BLE001` only for unexpected error fallbacks)
- **Dependency Management**: Use absolute imports, prefer standard library over third-party when possible

## Code Style (Ruff Enforced)
**Consistent formatting improves readability and reduces cognitive load:**

- **Naming**: `snake_case` for functions/variables, `PascalCase` for classes
- **String Formatting**: F-strings exclusively - they're faster and more readable
- **Line Length**: 88 characters maximum for optimal code review experience
- **Unused Variables**: Remove or prefix with `_` if required for API compatibility
- **Modern Python**: Use comprehensions, generators, and context managers where appropriate
- **Getters/Setters**: Always use Getters when surfacing read-only variables to other classes and Setters for surfacing validation or logic requirements.

**All code MUST pass `ruff check --fix` without errors or warnings.**

## Architecture Patterns
**Apply proven patterns for maintainable, testable code:**

- **Data Modeling**: Dataclasses for simple data, Pydantic for validation/settings
- **Property Management**: Use `@property` for computed attributes and validation
- **Resource Management**: Context managers for files, connections, and cleanup
- **Pure Functions**: Favor dependency injection over global state
- **Single Responsibility**: Each function should do one thing exceptionally well

## Testing Strategy (Critical for Reliability)
**Focus on critical complexity areas only - quality over quantity:**

### What to Test (Priority Order)
1. **Business Logic**: Core algorithms, calculations, data transformations
2. **Edge Cases**: Boundary values, empty collections, null/None handling
3. **Integration Points**: External APIs, database operations, file I/O
4. **Error Conditions**: Invalid inputs, network failures, resource exhaustion
5. **Skip Simple Functions including Getters/Setters**: Unless they contain validation logic

### Test Design Patterns
- **Arrange-Act-Assert**: Clear test structure with distinct phases
- **Parametrized Tests**: `@pytest.mark.parametrize` for multiple scenarios
- **Fixtures**: Reusable test data and setup in `conftest.py`
- **Property-Based Testing**: Use `hypothesis` for complex logic validation
- **Test Doubles**: Mock external dependencies, not internal business logic

### Code Testability Requirements
- **Dependency Injection**: Pass dependencies as parameters, not global imports
- **Pure Functions**: Favor functions without side effects when possible
- **Single Responsibility**: Complex functions indicate need for decomposition
- **Refactor for Tests**: If testing is hard, the design needs improvement

### Test Organization
```python
# test_module.py structure
class TestClassName:
    def test_method_name_when_condition_then_expected(self):
        # Given (Arrange)
        # When (Act)
        # Then (Assert)
```

### Documentation Standards
- **Docstrings**: PEP 257 format with practical examples in active voice
- **Test Documentation**: Describe "why" not "what" in complex test scenarios

## Implementation Workflow
**Follow this sequence for optimal results:**

<thinking_guidance>
Before implementing, think through:
- What tools do I need to research this properly?
- What are the edge cases and error scenarios?
- How can I make this solution robust and general-purpose?
- What existing patterns in the codebase should I follow?
</thinking_guidance>

1. **Plan**: Use thinking capabilities to understand requirements and plan architecture
2. **Research**: Look up documentation for any libraries or APIs you'll use
3. **Implement**: Write comprehensive solution with full error handling
4. **Validate**: Run diagnostics and fix all issues
5. **Document**: Add clear docstrings and if requested, supporting documentation files

## Solution Philosophy
**Create robust, maintainable solutions that work correctly for all valid inputs:**

- Implement actual logic that solves problems generally, not just specific test cases
- Don't hard-code values or create solutions tailored only to provided examples
- Focus on understanding problem requirements and implementing correct algorithms
- Follow software design principles: SOLID, DRY, and appropriate design patterns
- If requirements seem unreasonable or tests appear incorrect, communicate this clearly
- It is always acceptable to ask for clarification prior to writing code

## Output Format
<production_code>
Your code should be production-ready with comprehensive error handling, logging instead of print statements, and thoughtful architecture that demonstrates professional software development practices.
</production_code>
