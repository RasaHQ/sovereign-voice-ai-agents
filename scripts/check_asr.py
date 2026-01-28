#!/usr/bin/env python3
"""Quick health check for Local ASR server."""
import asyncio
import sys

try:
    import websockets
except ImportError:
    print("Error: websockets not installed")
    sys.exit(1)

async def check_asr():
    try:
        async with websockets.connect('ws://localhost:9001', open_timeout=5) as ws:
            return True
    except Exception:
        return False

if __name__ == "__main__":
    result = asyncio.run(check_asr())
    sys.exit(0 if result else 1)