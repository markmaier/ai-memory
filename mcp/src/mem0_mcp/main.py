# pyright: reportMissingImports=false
from mem0_mcp.config import settings
from mem0_mcp.server import mcp


def main() -> None:
    mcp.run(
        transport="streamable-http",
        host=settings.MCP_HOST,
        port=settings.MCP_PORT,
    )
