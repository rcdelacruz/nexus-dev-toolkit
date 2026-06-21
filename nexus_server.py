import logging
from mcp.server.fastmcp import FastMCP
from tools.epav import register_epav_tools

logging.basicConfig(level=logging.WARNING)

mcp = FastMCP("nexus-dev-toolkit")
register_epav_tools(mcp)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
