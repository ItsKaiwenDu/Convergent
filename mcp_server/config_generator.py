#!/usr/bin/env python3
"""
Convergent MCP Configuration Generator
--------------------------------------
Generates copy-paste JSON configuration snippets for integrating Convergent
into local AI clients like OpenCode, Claude Desktop, Cursor, and Zed.
"""

import sys
import os
import json

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVER_PATH = os.path.join(REPO_ROOT, "mcp_server", "server.py")
PYTHON_EXEC = sys.executable

def generate_configs():
    config = {
        "mcpServers": {
            "convergent": {
                "command": PYTHON_EXEC,
                "args": [SERVER_PATH]
            }
        }
    }
    
    print("==================================================================")
    print("        Convergent Local MCP Server Configuration Helper          ")
    print("==================================================================")
    print("\nCopy & paste following JSON snippet into your client configuration:\n")
    print(json.dumps(config, indent=2))
    print("\n------------------------------------------------------------------")
    print("Client Config Locations:")
    print(" • Claude Desktop (macOS): ~/Library/Application Support/Claude/claude_desktop_config.json")
    print(" • Claude Desktop (Windows): %APPDATA%\\Claude\\claude_desktop_config.json")
    print(" • Cursor / OpenCode: Add under MCP settings -> Add custom stdio MCP server")
    print("   Command: " + PYTHON_EXEC)
    print("   Args: " + SERVER_PATH)
    print("==================================================================\n")

if __name__ == "__main__":
    generate_configs()
