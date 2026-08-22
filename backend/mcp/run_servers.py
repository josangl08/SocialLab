import sys
import argparse
import asyncio
from mcp.drive_server import mcp as drive_mcp
from mcp.supabase_server import mcp as supabase_mcp
from mcp.instagram_server import mcp as instagram_mcp
from mcp.vision_server import mcp as vision_mcp

def list_all_tools():
    print("Listing tools for all MCP servers:\n")
    
    servers = {
        "Google Drive Server": drive_mcp,
        "Supabase Database Server": supabase_mcp,
        "Instagram Publisher Server": instagram_mcp,
        "Vision Server": vision_mcp
    }
    
    for name, mcp_instance in servers.items():
        print(f"=== {name} ===")
        tools = asyncio.run(mcp_instance.list_tools())
        if not tools:
            print("  No tools registered.")
        for tool in tools:
            print(f"  - {tool.name}: {tool.description}")
        print()

def main():
    parser = argparse.ArgumentParser(description="Run or inspect SocialLab MCP servers.")
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all registered tools for all servers."
    )
    parser.add_argument(
        "--server",
        choices=["drive", "supabase", "instagram", "vision"],
        help="Run a specific MCP server on stdio."
    )
    
    args = parser.parse_args()
    
    if len(sys.argv) == 1 or args.list:
        list_all_tools()
        return

    if args.server == "drive":
        print("Starting Google Drive MCP server on stdio...")
        drive_mcp.run()
    elif args.server == "supabase":
        print("Starting Supabase Database MCP server on stdio...")
        supabase_mcp.run()
    elif args.server == "instagram":
        print("Starting Instagram Publisher MCP server on stdio...")
        instagram_mcp.run()
    elif args.server == "vision":
        print("Starting Vision MCP server on stdio...")
        vision_mcp.run()


if __name__ == "__main__":
    main()
