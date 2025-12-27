# Running Tests

This guide explains how to run the test suite for the KenPom Client project.

## Prerequisites

Ensure you have the project dependencies installed:

```bash
# Install dependencies using uv
uv sync

# Or if uv is not available, use pip (not recommended)
pip install -e ".[dev]"
```

## Running Tests

### Using uv (Recommended)

```bash
# Run all tests
uv run pytest

# Run with verbose output
uv run pytest -v

# Run specific test file
uv run pytest tests/test_matchup_features.py

# Run with coverage
uv run pytest --cov=src/kenpom_client --cov-report=html
```

### Using pytest directly

If you have pytest installed in your environment:

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test
pytest tests/test_matchup_features.py -v
```

## Test Files

The project includes the following test files:

- `tests/test_effort.py` - Tests for effort calculations
- `tests/test_matchup_features.py` - Tests for matchup feature engineering
- `tests/test_prediction.py` - Tests for game predictions
- `tests/test_smoke_client.py` - Smoke tests for API client
- `tests/test_snapshot_enrichment.py` - Tests for snapshot enrichment

## Running Specific Tests

### Run tests matching a pattern

```bash
# Run all matchup tests
uv run pytest -k matchup

# Run all prediction tests
uv run pytest -k prediction
```

### Run tests with markers

```bash
# Run only fast tests (if markers are defined)
uv run pytest -m fast

# Skip slow tests
uv run pytest -m "not slow"
```

## Test Output

### Verbose Output

```bash
uv run pytest -v
```

Shows:
- Test file names
- Individual test names
- Pass/fail status
- Duration

### Detailed Failure Information

```bash
uv run pytest -v --tb=short
```

Shows:
- Short traceback for failures
- Assertion details
- Error messages

### Full Traceback

```bash
uv run pytest -v --tb=long
```

Shows:
- Complete traceback
- All local variables
- Full context

## Continuous Integration

Tests are automatically run in GitHub Actions when:
- Pull requests are created
- Code is pushed to main branch
- Workflow is manually triggered

## Troubleshooting

### Import Errors

If you see import errors:
```bash
# Ensure you're in the project root
cd /path/to/kenpom-client

# Install in development mode
uv sync
```

### Missing Dependencies

If tests fail due to missing packages:
```bash
# Sync all dependencies including dev
uv sync --dev
```

### Test Data Issues

Some tests may require:
- API credentials (for integration tests)
- Test data files
- Network access (for API tests)

Check test files for required setup.

## Expected Test Results

A healthy test suite should show:
- ✅ All tests passing
- ✅ No warnings (or minimal warnings)
- ✅ Reasonable execution time (< 30 seconds for full suite)

## Next Steps

After running tests:
1. Review any failures
2. Fix broken tests
3. Add new tests for new features
4. Update tests when refactoring

---

**Note**: Some tests may require API credentials or network access. Check individual test files for requirements.
