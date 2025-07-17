# Tests

This directory contains tests for the BitCraft application's modular architecture.

## Running Tests

### Simple Tests (Recommended)
```bash
poetry run python tests/test_simple.py
```

### Pytest (If Available)
```bash
poetry run pytest tests/ -v
```

### Integration Tests
```bash
poetry run python tests/test_integration.py
```

## Test Structure

- **`test_simple.py`** - Simple unit tests for modular architecture verification
- **`test_integration.py`** - More comprehensive integration tests (requires pytest)
- **`test_modules.py`** - Detailed module testing with mocks (requires pytest)
- **`conftest.py`** - Shared test fixtures and configuration

## What the Tests Verify

1. **Module Imports** - All modules can be imported without circular dependencies
2. **No Duplicate Classes** - Classes like `ClaimInventoryWindow` exist only in their proper modules
3. **Inheritance Structure** - `BitCraftMainWindow` and `BitCraftOverlay` properly inherit from `BaseWindow`
4. **Basic Functionality** - Core methods work as expected
5. **Clean Architecture** - No code duplication between `main.py` and `overlay.py`

## Expected Output

When all tests pass, you should see:
```
🎉 All tests passed! Modular architecture is working correctly.
```

This confirms that the refactoring was successful and the codebase now follows proper modular design principles.
