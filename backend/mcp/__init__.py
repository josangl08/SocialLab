import sys
import os
import importlib

# Avoid shadowing the third-party 'mcp' package by importing it first
# and appending our local 'mcp' directory to its search paths.
local_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(local_dir)

# Remove the parent of our local 'mcp' directory from sys.path temporarily to find the real one
clean_path = [p for p in sys.path if p not in ("", ".") and os.path.abspath(p) != parent_dir]

orig_sys_path = sys.path
sys.path = clean_path

# Keep track of local module reference
local_mcp_mod = sys.modules.get("mcp")
if "mcp" in sys.modules:
    del sys.modules["mcp"]

try:
    # Import the third-party 'mcp'
    real_mcp = importlib.import_module("mcp")
    # Append our local directory to its search path list
    if local_dir not in real_mcp.__path__:
        real_mcp.__path__.append(local_dir)
except Exception:
    # Fallback to local module if real import fails
    if local_mcp_mod:
         sys.modules["mcp"] = local_mcp_mod
finally:
    sys.path = orig_sys_path
