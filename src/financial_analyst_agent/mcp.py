"""MCP tool discovery and curation."""

from langchain_mcp_adapters.client import MultiServerMCPClient

from .config import ALLOWED_TOOLS, SERVERS


async def load_tools(list_only: bool = False, list_allowed_tools: bool = False) -> list:
    """Discover MCP tools and return only the tools this agent may use."""
    client = MultiServerMCPClient(SERVERS)

    if list_only:
        tools = []
        for server_name in SERVERS:
            server_tools = await client.get_tools(server_name=server_name)
            tools.extend(server_tools)
            print(f"[{server_name}]")
            for tool in server_tools:
                print(f"  {tool.name}: {(tool.description or '')[:90]}")

        return []

    if list_allowed_tools: 
        tools = []
        for server_name in SERVERS:
            server_tools = await client.get_tools(server_name=server_name)
            tools.extend(server_tools)

        allowed = [
            tool
            for tool in tools
            if any(keyword in tool.name.lower() for keyword in ALLOWED_TOOLS)
        ]
        print(f"\n[allowed_tools] ({len(allowed)}/{len(tools)} pass the ALLOWED_TOOLS filter)")
        for tool in allowed:
            print(f"  {tool.name}")
        return []
    
    tools = await client.get_tools()

    curated_tools = [
        tool
        for tool in tools
        if any(keyword in tool.name.lower() for keyword in ALLOWED_TOOLS)
    ]
    print(
        f"Discovered {len(tools)} tools; curated to {len(curated_tools)}: "
        f"{[tool.name for tool in curated_tools]}\n"
    )
    return curated_tools
