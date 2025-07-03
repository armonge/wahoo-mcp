# Wahoo MCP Server

[![CI](https://github.com/armonge/wahoo-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/armonge/wahoo-mcp/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/armonge/wahoo-mcp/graph/badge.svg?token=CODECOV_TOKEN)](https://codecov.io/gh/armonge/wahoo-mcp)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

A Model Context Protocol (MCP) server for interacting with the Wahoo Cloud API, focusing on reading workout information.

## Features

- **Workouts**: List workouts with pagination and date filtering, get detailed workout information
- **Routes**: List and retrieve saved cycling/running routes
- **Training Plans**: Access training plans from your Wahoo account
- **Power Zones**: View power zone configurations for different workout types
- **OAuth 2.0 Authentication**: Secure authentication with automatic token refresh
- **Comprehensive workout type support**: 72 different workout types with location and family categorization
- **Async/await implementation**: High-performance async operations using httpx
- **Automatic token management**: Tokens are refreshed automatically when they expire

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

**Configuration file location:**
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- Linux: `~/.config/Claude/claude_desktop_config.json`

**Example configuration:**

```json
{
  "mcpServers": {
    "wahoo": {
      "type": "stdio",
      "command": "/path/to/uv",
      "args": [
        "--project",
        "/path/to/wahoo-mcp",
        "run",
        "python",
        "-m",
        "src.server"
      ],
      "env": {
        "WAHOO_TOKEN_FILE": "/path/to/wahoo-mcp/token.json"
      }
    }
  }
}
```

Make sure to replace `/path/to/` with your actual paths.

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

#### list_routes
List routes from your Wahoo account.

Parameters:
- `external_id` (optional): Filter routes by external ID

Example:
```
Use the list_routes tool to show my saved routes
```

#### get_route
Get detailed information about a specific route.

Parameters:
- `route_id` (required): The ID of the route to retrieve

Example:
```
Use the get_route tool to get details for route ID 456
```

#### list_plans
List training plans from your Wahoo account.

Parameters:
- `external_id` (optional): Filter plans by external ID

Example:
```
Use the list_plans tool to show my training plans
```

#### get_plan
Get detailed information about a specific plan.

Parameters:
- `plan_id` (required): The ID of the plan to retrieve

Example:
```
Use the get_plan tool to get details for plan ID 789
```

#### list_power_zones
List power zones from your Wahoo account.

Parameters: None

Example:
```
Use the list_power_zones tool to show my power zones
```

#### get_power_zone
Get detailed information about a specific power zone.

Parameters:
- `power_zone_id` (required): The ID of the power zone to retrieve

Example:
```
Use the get_power_zone tool to get details for power zone ID 321
```

#### generate_workout_visualizations
Generate interactive HTML visualizations for workouts with FIT file data (GPS, heart rate, power, etc.).

Parameters:
- `workout_id` (required): The ID of the workout to visualize
- `include_route_map` (optional): Generate interactive route map with elevation coloring (default: true)
- `include_elevation_chart` (optional): Generate elevation profile and heart rate chart (default: true)

Example:
```
Use the generate_workout_visualizations tool to create maps and charts for workout ID 12345
```

**Note**: This tool requires workouts that have FIT files with GPS data. The generated HTML can be saved to files and opened in a web browser for interactive viewing.

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
│   ├── token_store.py  # Token storage and refresh logic
│   └── models.py       # Pydantic models for API data structures
├── tests/
│   ├── __init__.py
│   ├── test_server.py  # Server test suite
│   └── test_token_store.py  # Token store tests
├── pyproject.toml      # Project configuration
└── README.md          # This file
```

## API Reference

The server implements the following Wahoo Cloud API endpoints:

**Workouts:**
- `GET /v1/workouts` - List workouts with pagination and date filtering
- `GET /v1/workouts/{id}` - Get detailed workout information

**Routes:**
- `GET /v1/routes` - List saved routes
- `GET /v1/routes/{id}` - Get route details including GPS data

**Training Plans:**
- `GET /v1/plans` - List training plans
- `GET /v1/plans/{id}` - Get plan details

**Power Zones:**
- `GET /v1/power_zones` - List power zone configurations
- `GET /v1/power_zones/{id}` - Get specific power zone details

For full API documentation, see [Wahoo Cloud API](https://cloud-api.wahooligan.com/).

## License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.
