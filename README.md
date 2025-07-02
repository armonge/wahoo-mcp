# Wahoo MCP Server

A Model Context Protocol (MCP) server for interacting with the Wahoo Cloud API, focusing on reading workout information.

## Features

- List workouts with pagination and date filtering
- Get detailed workout information
- OAuth 2.0 authentication support
- Async/await implementation using httpx

## Installation

### Using uv (recommended)

First, install `uv` if you haven't already:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then install the project dependencies:
```bash
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e .
```

For development:
```bash
uv pip install -e ".[dev]"
```

### Using pip (alternative)

If you prefer using pip:
```bash
python3.13 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e .
```

For development:
```bash
pip install -e ".[dev]"
```

## Configuration

### Getting an Access Token

1. Register your application at [Wahoo's Developer Portal](https://developers.wahooligan.com/) to get a Client ID and Client Secret.

2. Create a `.env` file from the example:
   ```bash
   cp .env.example .env
   ```

   Then edit `.env` and add your credentials:
   ```env
   WAHOO_CLIENT_ID=your_client_id_here
   WAHOO_CLIENT_SECRET=your_client_secret_here
   ```

3. Set the token file path in your `.env` file:
   ```env
   WAHOO_TOKEN_FILE=token.json
   ```

4. Use the authentication helper:
   ```bash
   make auth
   # or
   uv run python src/auth.py
   ```

   This will:
   - Use credentials from `.env` (or prompt if not set)
   - Open a browser for OAuth authentication
   - Start a local server to receive the callback
   - Save your tokens to the file specified by `WAHOO_TOKEN_FILE`
   - Tokens will be automatically refreshed when needed

### Configuration Options

The auth server can be configured via environment variables:

**Server Configuration:**
- `WAHOO_AUTH_HOST`: Auth server bind address (default: `localhost`)
- `WAHOO_AUTH_PORT`: Auth server port (default: `8080`)

**Redirect URL Configuration:**
- `WAHOO_REDIRECT_HOST`: OAuth callback host (default: uses `WAHOO_AUTH_HOST`)
- `WAHOO_REDIRECT_PORT`: OAuth callback port (default: uses `WAHOO_AUTH_PORT`)
- `WAHOO_REDIRECT_SCHEME`: URL scheme - `http` or `https` (default: `http`)

**Credentials:**
- `WAHOO_CLIENT_ID`: Your Wahoo Client ID
- `WAHOO_CLIENT_SECRET`: Your Wahoo Client Secret
- `WAHOO_TOKEN_FILE`: Path to store OAuth tokens (required)

**Example Configurations:**

1. **Local Development (default):**
   ```env
   # Redirect URL will be: http://localhost:8080/callback
   ```

2. **Using ngrok:**
   ```env
   WAHOO_AUTH_HOST=localhost
   WAHOO_AUTH_PORT=8080
   WAHOO_REDIRECT_HOST=your-app.ngrok.io
   WAHOO_REDIRECT_PORT=443
   WAHOO_REDIRECT_SCHEME=https
   # Redirect URL will be: https://your-app.ngrok.io:443/callback
   ```

3. **Docker with port mapping:**
   ```env
   WAHOO_AUTH_HOST=0.0.0.0
   WAHOO_AUTH_PORT=8080
   WAHOO_REDIRECT_HOST=localhost
   WAHOO_REDIRECT_PORT=8888
   # Server binds to 0.0.0.0:8080, redirect URL is http://localhost:8888/callback
   ```

**Note**: When registering your app with Wahoo, use the redirect URL that matches your configuration.

## Usage

### Running the MCP Server

```bash
uv run python -m src.server
```

Or if you've activated the virtual environment:
```bash
python -m src.server
```

### Using with Claude Desktop

Add the following to your Claude Desktop configuration file:

```json
{
  "mcpServers": {
    "wahoo": {
      "command": "python",
      "args": ["-m", "src.server"],
      "env": {
        "WAHOO_TOKEN_FILE": "/path/to/your/token.json"
      }
    }
  }
}
```

### Available Tools

#### list_workouts
List workouts from your Wahoo account.

Parameters:
- `page` (optional): Page number (default: 1)
- `per_page` (optional): Number of items per page (default: 30)
- `start_date` (optional): Filter workouts created after this date (ISO 8601 format)
- `end_date` (optional): Filter workouts created before this date (ISO 8601 format)

Example:
```
Use the list_workouts tool to show my recent workouts
```

#### get_workout
Get detailed information about a specific workout.

Parameters:
- `workout_id` (required): The ID of the workout to retrieve

Example:
```
Use the get_workout tool to get details for workout ID 12345
```

## Development

### Running Tests

```bash
uv run pytest
```

Or if you've activated the virtual environment:
```bash
pytest
```

### Project Structure

```
wahoo-mcp/
├── src/
│   ├── __init__.py
│   ├── server.py       # Main MCP server implementation
│   ├── auth.py         # OAuth authentication helper
│   └── token_store.py  # Token storage and refresh logic
├── tests/
│   ├── __init__.py
│   ├── test_server.py  # Server test suite
│   └── test_token_store.py  # Token store tests
├── pyproject.toml      # Project configuration
└── README.md          # This file
```

## API Reference

The server implements the following Wahoo Cloud API endpoints:

- `GET /v1/workouts` - List workouts
- `GET /v1/workouts/{id}` - Get workout details

For full API documentation, see [Wahoo Cloud API](https://cloud-api.wahooligan.com/).

## License

This project is provided as-is for educational and development purposes.
