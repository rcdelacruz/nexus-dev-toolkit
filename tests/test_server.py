from mcp.server.fastmcp import FastMCP

from tools.epav import register_epav_tools


def test_epav_tools_register():
    mcp = FastMCP("test")
    register_epav_tools(mcp)
    tool_names = {t.name for t in mcp._tool_manager.list_tools()}
    assert "ingest_architecture_doc" in tool_names
    assert "load_task" in tool_names
    assert "generate_project_rules" in tool_names
    assert "resolve_package_versions" in tool_names


def test_epav_tools_register_idempotent():
    mcp = FastMCP("test")
    register_epav_tools(mcp)
    register_epav_tools(mcp)
    tool_names = [t.name for t in mcp._tool_manager.list_tools()]
    assert tool_names.count("load_task") == 1
