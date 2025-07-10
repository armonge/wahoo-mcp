# Wahoo MCP Server - Development Notes

## Project Overview
This is a Model Context Protocol (MCP) server that provides access to Wahoo Cloud API for retrieving workout data.

## Requirements
- Python 3.13+ (strictly enforced)
- uv package manager (recommended) or pip
- Wahoo API credentials (Client ID and Secret)
- Active Wahoo account with workout data

## Quick Start
```bash
# Install dependencies
uv sync

# Run authentication to get tokens
make auth

# Run the MCP server
uv run python -m src.server

# Run tests
pytest -v

# Run code quality checks
pre-commit run --all-files
```

## Key Commands

### Testing
```bash
# Run basic tests
make test

# Run tests with coverage
make test-cov
```

### Code Quality
```bash
# Run all pre-commit hooks
pre-commit run --all-files

# Run ruff linting
make lint

# Run ruff formatting
make format

# Run all checks (lint + format + test)
make check

# Run complete CI workflow
make ci
```

**IMPORTANT**: Always run `make check` or `ruff check .` after making any code updates to ensure code quality standards are met.

### Development Setup
```bash
# Install dependencies (including dev dependencies)
uv sync

# Activate virtual environment
source .venv/bin/activate

# Install pre-commit hooks
pre-commit install
```

## Architecture

### Main Components
- **WahooAPIClient**: HTTP client for Wahoo Cloud API
- **MCP Server**: Provides 8 tools for workouts, routes, plans, and power zones
- **Authentication**: Uses token file specified by `WAHOO_TOKEN_FILE` environment variable

### API Endpoints
- `GET /v1/workouts` - List workouts with pagination and date filters
- `GET /v1/workouts/{id}` - Get detailed workout information
- `GET /v1/routes` - List routes with optional external_id filter
- `GET /v1/routes/{id}` - Get detailed route information
- `GET /v1/plans` - List plans with optional external_id filter
- `GET /v1/plans/{id}` - Get detailed plan information
- `GET /v1/power_zones` - List power zones for the user
- `GET /v1/power_zones/{id}` - Get detailed power zone information

### MCP Tools
1. **list_workouts**: List workouts with optional filters (page, per_page, start_date, end_date)
2. **get_workout**: Get detailed workout information by ID
3. **list_routes**: List routes with optional external_id filter
4. **get_route**: Get detailed route information by ID
5. **list_plans**: List plans with optional external_id filter
6. **get_plan**: Get detailed plan information by ID
7. **list_power_zones**: List power zones for the user
8. **get_power_zone**: Get detailed power zone information by ID

## Testing Strategy

### Test Structure
- **TestWahooAPIClient**: Unit tests for HTTP client functionality
- **TestMCPTools**: Integration tests for MCP tool handlers

### Mock Strategy
- Uses `MagicMock` for HTTP responses to avoid `raise_for_status()` issues
- Patches `WahooAPIClient` methods for MCP tool testing
- Environment variable mocking for token authentication

## Code Quality Setup

### Pre-commit Hooks
- **trailing-whitespace**: Removes trailing whitespace
- **end-of-file-fixer**: Ensures files end with newline
- **check-yaml**: Validates YAML syntax
- **check-added-large-files**: Prevents large file commits
- **ruff**: Linting with auto-fix
- **ruff-format**: Code formatting

### Development Workflow
1. Make changes
2. Run tests: `make test`
3. Run code quality checks: `make check`
4. Pre-commit hooks run automatically on commit
5. All checks must pass before commit

### CI/CD Pipeline
The project uses GitHub Actions for automated testing and quality checks:

- **Pull Requests**: Runs full test suite, linting, and formatting checks
- **Main Branch**: Additional build step after tests pass
- **Security**: Integrated ruff security checks (flake8-bandit rules)
- **Coverage**: Automatic coverage reporting to Codecov

Key features:
- Uses Makefile commands for consistency between local and CI
- Tests on Python 3.13 only (matching project requirements)
- Automatic dependency updates via Dependabot

## Environment Variables
- `WAHOO_TOKEN_FILE`: Required - path to file for persistent token storage
- `WAHOO_CLIENT_ID`: Required for authentication
- `WAHOO_CLIENT_SECRET`: Required for token refresh (confidential clients)

## OAuth Token Management

### Token Expiration
- Access tokens expire after **2 hours**
- Refresh tokens should be used to obtain new access tokens without re-authentication

### Refresh Token Endpoints

#### PKCE Flow (Used by this app)
```
POST https://api.wahooligan.com/oauth/token
Parameters:
- client_id: Your client ID
- grant_type: refresh_token
- refresh_token: Your refresh token
- code_verifier: The PKCE code verifier from initial auth
```

#### Standard OAuth Flow (For confidential apps)
```
POST https://api.wahooligan.com/oauth/token
Parameters:
- client_id: Your client ID
- client_secret: Your client secret
- grant_type: refresh_token
- refresh_token: Your refresh token
```

### Important Notes
- Once a refreshed access token is used, previous tokens are revoked
- Store the new refresh token returned with each refresh
- The code_verifier must be the same one used during initial authentication

## File Structure
```
src/
├── server.py          # Main MCP server implementation
├── models.py          # Pydantic models for all API data structures
├── auth.py            # OAuth authentication helper script
├── token_store.py     # Token storage and refresh management
└── __init__.py

tests/
├── test_server.py     # Server and API client tests
├── test_token_store.py # Token storage tests
└── __init__.py
```

## Common Development Tasks

### Adding a New MCP Tool
1. Add tool definition in `list_tools()` in server.py
2. Add tool implementation in `call_tool()`
3. Add corresponding method in `WahooAPIClient`
4. Write tests for the new functionality
5. Update README.md with usage examples

### Debugging Tips
- Enable debug logging: `export LOG_LEVEL=DEBUG`
- Test token refresh: Set `expires_at` to past time in tests
- Simulate 401 errors: Mock httpx responses with status_code=401
- Check token file permissions: Should be 0600 (owner read/write only)

### Running Specific Tests
```bash
# Run a specific test class
pytest tests/test_server.py::TestRefreshToken -v

# Run tests matching a pattern
pytest -k "refresh" -v

# Run with coverage
pytest --cov=src --cov-report=html
```

## API Integration Details

### Wahoo API Response Format
```json
// List workouts response
{
  "workouts": [
    {
      "id": 12345,
      "name": "Morning Run",
      "starts": "2024-01-15T07:00:00.000Z",
      "minutes": 45,
      "workout_type_id": 1,
      "created_at": "2024-01-15T08:00:00.000Z",
      "updated_at": "2024-01-15T08:00:00.000Z"
    }
  ]
}

// Token response
{
  "access_token": "...",
  "refresh_token": "...",
  "expires_in": 7200,
  "token_type": "Bearer",
  "scope": "user_read workouts_read routes_read plans_read power_zones_read"
}
```

### Error Handling
- **401 Unauthorized**: Automatically attempts token refresh
- **429 Rate Limited**: Consider implementing exponential backoff
- **500 Server Error**: Log and return user-friendly error message

## Security Best Practices

### Token Storage
1. Never commit tokens to version control
2. Use environment variables for CI/CD
3. Token files are created with 0600 permissions (owner read/write only)
4. Consider using system keychain for production deployments

### PKCE Implementation
- Code verifier: 43-128 characters, URL-safe
- Code challenge: SHA256(code_verifier), base64url encoded
- Store code_verifier with tokens for refresh

## Troubleshooting Guide

### Common Issues

1. **"No refresh token received"**
   - Ensure app has correct OAuth scopes
   - Check if app is configured as public (PKCE) or confidential
   - Verify redirect URI matches exactly

2. **"Token refresh failed"**
   - Verify code_verifier is the same as initial auth
   - Check CLIENT_ID is set in environment
   - Ensure refresh_token hasn't been revoked
   - Check token hasn't expired (some refresh tokens expire)

3. **"401 Unauthorized" (even after refresh)**
   - Token may be revoked - re-authenticate
   - Check Authorization header format: `Bearer <token>`
   - Verify API endpoint URL is correct

4. **Import errors**
   - Ensure virtual environment is activated
   - Run `uv sync` to install dependencies
   - Check Python version (requires 3.13+)

5. **Pre-commit failures**
   - Run `pre-commit install` to set up hooks
   - Use `ruff check --fix` for auto-fixes
   - Check file endings and trailing whitespace

## Performance Considerations

### Token Refresh Strategy
- Tokens are refreshed automatically with 5-minute buffer before expiry
- Failed API calls (401) trigger immediate refresh and retry
- Consider implementing request queuing during refresh

### API Rate Limits
- Wahoo API has undocumented rate limits
- Implement caching for frequently accessed data
- Consider batching requests where possible

## Future Enhancements

### High Priority
1. **Token Refresh Lock**: Prevent concurrent refresh attempts
2. **Request Retry Logic**: Exponential backoff for failed requests
3. **Metrics Collection**: Track API call success rates

### Medium Priority
1. **Caching Layer**: Cache workout data with TTL
2. **Batch Operations**: Support bulk workout fetching
3. **Webhook Support**: Real-time workout updates

### Low Priority
1. **Export Formats**: GPX, TCX, FIT file exports
2. **Data Aggregation**: Weekly/monthly summaries
3. **Integration Tests**: End-to-end API testing

## Development Guidelines

### Code Style
- Use type hints for all function parameters and returns
- Follow PEP 8 (enforced by ruff)
- Async/await for all I/O operations
- Comprehensive docstrings for public methods

### Testing Philosophy
- Unit tests for business logic
- Integration tests for API interactions
- Mock external dependencies
- Aim for >90% code coverage

### Git Workflow
1. Create feature branch from main
2. Make atomic commits with clear messages
3. Ensure all tests pass: `make check`
4. Run pre-commit hooks
5. Create PR with description and test plan

### Security Configuration
The project uses ruff's built-in security checks (flake8-bandit) instead of separate security tools:

- **S101-S110**: Various security rule categories
- **Per-file ignores**: Test files have appropriate exceptions
- **Token storage**: Special handling for false positives in token_store.py

This approach integrates security scanning directly into the main linting workflow.

## Useful Resources

### Documentation
- [Wahoo Cloud API Docs](https://cloud-api.wahooligan.com/)
- [MCP Specification](https://modelcontextprotocol.io/)
- [OAuth 2.0 RFC 6749](https://tools.ietf.org/html/rfc6749)
- [PKCE RFC 7636](https://tools.ietf.org/html/rfc7636)

### Tools
- [httpx Documentation](https://www.python-httpx.org/)
- [pytest Documentation](https://docs.pytest.org/)
- [ruff Documentation](https://docs.astral.sh/ruff/)

### Community
- Wahoo API Support: wahooapi@wahoofitness.com
- MCP Discord: [Join the community](https://discord.gg/modelcontext)

## Known Issues & Solutions

### Test Mocking
- **Issue**: `Response.raise_for_status()` fails without request instance
- **Solution**: Use `MagicMock` instead of `httpx.Response` objects

### MCP Server Testing
- **Issue**: Cannot call MCP decorated methods directly on server instance
- **Solution**: Import and call the handler functions directly in tests

### Token Refresh Edge Cases
- **Issue**: Concurrent requests during token refresh
- **Solution**: Token refresh is atomic per client instance
- **TODO**: Consider implementing token refresh lock for production

## Post-Refactoring Testing Requirements

⚠️ **CRITICAL**: After any code refactoring, ALWAYS run these commands to ensure nothing is broken:

1. **Run all tests**: `pytest -v`
2. **Test authentication**: `make test-auth`
3. **Check code quality**: `ruff check . && ruff format .`

The `make test-auth` command tests:
- Workouts endpoint access
- Routes endpoint access
- Plans endpoint access
- Power zones endpoint access
- Token refresh functionality

This ensures that after refactoring (especially type imports/exports), all real API integrations still work correctly.

## Development Memories

### Import Guidelines
- Always add imports at the top module level
