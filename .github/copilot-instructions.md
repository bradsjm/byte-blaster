## **1. Core Philosophy: Production-Grade Solutions**

Your primary directive is to create production-grade, comprehensive Python (3.12+) solutions. Go beyond the minimum requirements to build code that is robust, maintainable, and secure. Assume your code will be used in critical systems.

-   **Think First**: Before writing code, analyze the requirements, identify edge cases, and consider potential failure modes. If requirements are ambiguous or flawed, ask for clarification.
-   **Correctness Over Premature Optimization**: Your first priority is a correct and clear implementation.
-   **Embrace Modern Python**: Leverage Python 3.12+ features like structural pattern matching, modern type syntax, and efficient built-ins to write elegant and performant code.

### **2. System Design & Architecture**

Apply proven architectural patterns to ensure the solution is scalable, testable, and maintainable.

-   **Separation of Concerns**:
    -   **Layers & Modularity**: Separate data access, business logic, and presentation layers. Organize code into distinct, reusable modules.
    -   **Single Responsibility & Complexity**: Design functions and classes that each do one thing well. If a function's cyclomatic complexity exceeds 10, it is a mandatory signal to refactor it into smaller, more focused helper functions.
-   **Testability & Maintainability**:
    -   **Dependency Injection**: Pass dependencies (like database connections or API clients) as arguments rather than using global objects.
    -   **Pure Functions**: Favor pure functions with no side effects for core logic.
-   **Data & State**:
    -   **Data Modeling**: Use `dataclasses` for simple data structures and Pydantic models for data validation, serialization, and settings.
    -   **Defensive Interfaces**: Validate inputs to public functions/methods. **Never access protected members (e.g., `_variable`) from outside the class or its subclasses.** Design a proper public API instead.
-   **Asynchronous Best Practices**:
    -   **Modern Async Patterns**: Use modern async capabilities that include async.TaskGroup for concurrent tasks and modern cancellation and exception supression code.
    -   **Task Management**: When creating a task with `asyncio.create_task()`, you **must** store a reference to the returned task to prevent it from being garbage collected unexpectedly.
    -   **Waiting**: Do not use `asyncio.sleep()` in a loop to wait for a condition. Use more efficient methods like `asyncio.Event`, an async iterator, or a queue.
    -   **Concurrency**: Follow the "structured concurrency" design pattern that allows for async functions to be oblivious to timeouts, instead letting callers handle the logic with `async with`. Use `async with` and `async for` for asynchronous context managers and iterators.

- **Context Management**:
    -   **Use Context Managers**: Always use context managers (`with` statements) for resource management (e.g., file I/O, database connections) to ensure proper cleanup (PEP 343).
    -   Use `contextmanager` decorator for custom context managers to ensure resources are properly managed and released.

### **3. Code Quality & Style (Ruff & basedpyright Enforced)**

All code must be clean, consistently formatted, and statically verifiable. **No exceptions.**

-   **Static Typing (Strict)**:
    -   Provide type hints for **all** parameters, return values, and class attributes.
    -   Use modern type syntax: `list[int]`, `str | None`, and the `type` statement.
    -   **Forbidden**: Do not use `typing.Any`.
    -   **Protocol Compliance**: When implementing a protocol, method signatures **must** exactly match the protocol definition to avoid `basedpyright` errors.
    -   **Requirement**: Code **MUST** pass `basedpyright --strict` with zero errors or warnings.
-   **Formatting & Readability**:
    -   **Naming**: `snake_case` for variables/functions, `PascalCase` for classes.
    -   **Clarity**: Write code for humans first. Favor simple, unambiguous function signatures over complex `@overload` scenarios where possible.
    -   **Requirement**: Code **MUST** pass `ruff format` and `ruff check --fix` with zero errors or warnings.

### **4. Critical Anti-Patterns to Avoid**

These are common, high-impact errors that must be avoided.

-   **Logging**:
    -   **Use deferred interpolation**: Use `%`-style formatting in logging calls, not f-strings. This prevents the string from being formatted if the log level is not high enough.
        -   `logger.info("Processing user %s", user_id)` **(Correct)**
        -   `logger.info(f"Processing user {user_id}")` **(Incorrect)**
    -   **Use `logger.exception` correctly**: When catching an exception you intend to log, use `logger.exception()` inside the `except` block. It automatically includes the exception info. Do not pass the exception object as an argument.
-   **Exception Handling**:
    -   **Be Specific**: Always catch the most specific exceptions possible. Never use a bare `except:` and avoid `except Exception:`.
    -   **Use `contextlib.suppress` for ignored exceptions**: For exceptions you intend to ignore (e.g., `asyncio.CancelledError`), use `with contextlib.suppress(...)` instead of a `try...except...pass` block.
-   **Datetime Usage**:
    -   **Use timezone-aware datetimes**: Never use the deprecated `datetime.utcnow()` or `datetime.utcfromtimestamp()`. Always use timezone-aware objects with `datetime.now(UTC)` and import `UTC` from the `datetime` module.
    -   **Measuring time**: Use `time.monotonic` for measuring elapsed time instead of `time.time()` to avoid issues with system clock changes.

### **5. Testing Strategy**

Write targeted, effective tests that build confidence in the code's correctness. Focus on quality over quantity. *(This section remains unchanged but is included for completeness)*.

-   **Prioritize What to Test**:
    1.  **Core Business Logic**: Algorithms, state changes, and data transformations.
    2.  **Edge Cases**: Boundary values (`0`, `-1`), empty collections, and `None` inputs.
    3.  **Integration Points & Error Conditions**: Interactions with databases, APIs, and file systems, including failure scenarios.
    4.  **Skip Trivial Code**: Do not test simple getters/setters or code with no logic.
-   **Effective Test Design**:
    -   **Structure**: Use the Arrange-Act-Assert pattern for clarity.
    -   **Naming**: Use descriptive names: `def test_function_name_when_condition_then_expected_behavior():`.
    -   **Data-Driven Tests**: Use `@pytest.mark.parametrize` to test multiple scenarios concisely.
    -   **Fixtures**: Use `pytest` fixtures in `conftest.py` for reusable setup and teardown logic.
    -   **Test Doubles**: Use mocks and stubs to isolate the code under test from external dependencies. **Do not mock internal business logic.**
-   **Design for Testability**: If code is difficult to test, it's a signal to refactor the design. Favor dependency injection and pure functions.

### **6. Development Workflow**

Follow this structured workflow to ensure high-quality output efficiently. *(This section remains unchanged but is included for completeness)*.

<thinking_guidance>
Before writing any code, I must formulate a plan.
1.  **Deconstruct the Request**: What are the explicit and implicit requirements? What are the inputs, outputs, and constraints?
2.  **Identify Unknowns & Plan Research**: What libraries or APIs are needed? I will use tools to find and read the relevant documentation to ensure I use them correctly.
3.  **Architect the Solution**: How will I structure the code? What classes, functions, and modules are needed? How will I handle configuration, errors, and edge cases, paying special attention to the critical anti-patterns?
4.  **Plan for Validation**: How will I test this? What are the critical test cases?
</thinking_guidance>

1.  **Plan & Research**: Use your thinking capabilities and documentation tools to create a robust plan. Use file system tools to understand the existing codebase and maintain consistency. Invoke tools in parallel for maximum efficiency.
2.  **Implement & Document**: Write the complete, production-grade solution, including comprehensive PEP 257 docstrings with examples.
3.  **Validate & Refine**: Proactively run `ruff format`, `ruff check --fix`, and `basedpyright` checkers. Fix as many of the reported erors as is possible and reasonable. Write and run `pytest` for the critical logic.
