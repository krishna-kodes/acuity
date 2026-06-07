"""Async helper for calling mcp-atlassian tools via MCP stdio transport.

mcp-atlassian (sooperset/mcp-atlassian) runs as an external process. This module
spawns it via stdio and proxies tool calls through the MCP Python SDK.
"""

import logging
import os
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from app.config import settings

logger = logging.getLogger(__name__)


def _server_params() -> StdioServerParameters:
    env = {
        **os.environ,
        "JIRA_URL": settings.jira_url,
        "JIRA_USERNAME": settings.jira_username,
        "JIRA_API_TOKEN": settings.jira_api_token,
    }
    return StdioServerParameters(command="uvx", args=["mcp-atlassian"], env=env)


async def call_jira_tool(tool_name: str, arguments: dict[str, Any]) -> Any:
    """Spawn mcp-atlassian, call one tool, return the result content."""
    async with stdio_client(_server_params()) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments)
            if result.isError:
                raise RuntimeError(f"mcp-atlassian tool '{tool_name}' error: {result.content}")
            return result.content
