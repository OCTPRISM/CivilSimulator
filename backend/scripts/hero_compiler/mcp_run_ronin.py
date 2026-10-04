#!/usr/bin/env python3
"""Send blender_ronin_swordsman.py to Blender MCP addon (localhost:9876)."""
from __future__ import annotations

import json
import socket
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "blender_ronin_swordsman.py"
HOST = "127.0.0.1"
PORT = 9876
TIMEOUT = 300


def main() -> int:
    code = SCRIPT.read_text(encoding="utf-8") + "\n\nmain()\n"
    payload = json.dumps({"type": "execute_code", "params": {"code": code}}).encode()

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(TIMEOUT)
    try:
        s.connect((HOST, PORT))
    except OSError as e:
        print(f"Cannot connect to Blender MCP at {HOST}:{PORT} — is Blender open with MCP addon connected?\n{e}")
        return 1

    print(f"Sending ronin build script ({len(code)} chars) …")
    s.sendall(payload)
    chunks: list[bytes] = []
    while True:
        try:
            part = s.recv(262144)
            if not part:
                break
            chunks.append(part)
            joined = b"".join(chunks)
            if b'"status"' in joined and joined.strip().endswith(b"}"):
                break
        except socket.timeout:
            print("Timed out waiting for Blender response (check Blender UI for progress).")
            break
    s.close()

    raw = b"".join(chunks).decode("utf-8", errors="replace")
    print(raw)
    try:
        resp = json.loads(raw)
        return 0 if resp.get("status") == "success" else 1
    except json.JSONDecodeError:
        return 1 if not raw else 0


if __name__ == "__main__":
    sys.exit(main())
