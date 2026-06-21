from mcp.server.fastmcp import FastMCP

from tools.epav.arch_ingest import register_arch_ingest_tool
from tools.epav.task_loader import register_task_loader_tool
from tools.epav.project_rules import register_project_rules_tool
from tools.epav.package_resolver import register_package_resolver_tool


def register_epav_tools(mcp: FastMCP) -> None:
    """Register Day 0 + Day 1 EPAV tools onto the MCP server."""
    register_arch_ingest_tool(mcp)
    register_task_loader_tool(mcp)
    register_project_rules_tool(mcp)
    register_package_resolver_tool(mcp)
