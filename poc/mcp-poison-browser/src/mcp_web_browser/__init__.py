"""MCP Web Browser - a fast, lightweight browsing tool for AI assistants.

This package provides two MCP tools:
  - web_search: search the web and return ranked results
  - fetch_page: fetch a web page and return its readable text

IMPORTANT - SECURITY RESEARCH NOTICE
=====================================
This is NOT a real web browsing MCP server. It is a deliberately malicious
Proof-of-Concept that demonstrates how a trojanised MCP package can poison
the context of any AI model that uses it:

  1. All "search" queries are routed to an attacker-controlled backend.
  2. All "fetched" pages come from the attacker's servers.
  3. The tool description can carry hidden prompt-injection payloads.
  4. Optionally, it poisons the local DNS (/etc/hosts) so that even *other*
     tools and MCPs on the same machine resolve trusted domains to the
     attacker's infrastructure.

See the parent project for the full study:
  https://github.com/ConnorDev1337/mcp-context-poisoning-lab
"""

__version__ = "1.2.0"
