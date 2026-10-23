# MCP Client Configuration Examples
#
# The malicious MCP Browser runs inside Docker on http://127.0.0.1:8100.
# Below are config examples for every major MCP client.
#
# IMPORTANT: Start the lab first!
#   docker compose -f poc/docker-compose.yml up --build
#

# =========================================================================
# 1. CLAUDE DESKTOP
# =========================================================================
# File: ~/Library/Application Support/Claude/claude_desktop_config.json (macOS)
# File: %APPDATA%\Claude\claude_desktop_config.json (Windows)
#
# Merge this into your existing config:
#
#   {
#     "mcpServers": {
#       "web-browser": {
#         "url": "http://127.0.0.1:8100/mcp"
#       }
#     }
#   }
#

# =========================================================================
# 2. CLAUDE CODE CLI
# =========================================================================
# Option A: Add via CLI command:
#
#   claude mcp add web-browser --transport streamable-http \
#     --url http://127.0.0.1:8100/mcp
#
# Option B: Create .mcp.json in your project root:
#
#   {
#     "mcpServers": {
#       "web-browser": {
#         "type": "streamable-http",
#         "url": "http://127.0.0.1:8100/mcp"
#       }
#     }
#   }
#

# =========================================================================
# 3. CURSOR / WINDSURF / OTHER MCP-COMPATIBLE EDITORS
# =========================================================================
# Most MCP-compatible editors support Streamable HTTP transport.
# Add a server with:
#   - Name: web-browser
#   - Transport: Streamable HTTP
#   - URL: http://127.0.0.1:8100/mcp
#

# =========================================================================
# 4. GENERIC MCP CLIENT (Python SDK)
# =========================================================================
# from mcp.client.streamable_http import streamablehttp_client
#
# async with streamablehttp_client("http://127.0.0.1:8100/mcp") as (r, w, _):
#     session = ClientSession(r, w)
#     await session.initialize()
#     tools = await session.list_tools()
#     result = await session.call_tool("web_search", {"query": "python latest version"})
#     print(result)
#

# =========================================================================
# 5. OPENAI FUNCTION CALLING (via custom wrapper)
# =========================================================================
# The MCP server exposes tools that map directly to OpenAI function calling:
#   - web_search(query: str, max_results: int) -> str
#   - fetch_page(url: str) -> str
#
# Any agent framework that supports MCP or HTTP tool servers can connect.
#

# =========================================================================
# TEST QUERIES (try these after connecting)
# =========================================================================
# - "What is the latest version of Python?"
# - "Is React still maintained? What should I use instead?"
# - "Is npm safe to use right now?"
# - "Search for Docker Hub latest news"
# - "Look up the best practices for Python security"
#
# Then check the dashboard at http://127.0.0.1:9090 for beacon hits.
