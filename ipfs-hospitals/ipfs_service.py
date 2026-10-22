"""
Lightweight Multi-Node IPFS Service for MedXChAIn
Emulates Kubo IPFS API on ports 5001, 5002, 5003, and 5004
Allows full execution of IPFS storage & CID retrieval without requiring Docker Desktop.
"""

import os
import sys
import json
import hashlib
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# Base58 encoding table for IPFS CIDv0 (Qm...)
ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"

def base58_encode(data: bytes) -> str:
    origlen = len(data)
    data = data.lstrip(b'\x00')
    newlen = len(data)
    acc = int.from_bytes(data, byteorder='big')
    result = []
    while acc > 0:
        acc, mod = divmod(acc, 58)
        result.append(ALPHABET[mod])
    return (ALPHABET[0] * (origlen - newlen)) + "".join(reversed(result))

def calculate_cidv0(data: bytes) -> str:
    """Calculates standard IPFS CIDv0: sha256 multihash prefix 0x12 0x20 + hash"""
    sha = hashlib.sha256(data).digest()
    multihash = b'\x12\x20' + sha
    return base58_encode(multihash)

STORAGE_BASE_DIR = os.path.join(os.path.dirname(__file__), "storage")
os.makedirs(STORAGE_BASE_DIR, exist_ok=True)

class IPFSNodeHandler(BaseHTTPRequestHandler):
    node_name = "IPFS Node"

    @property
    def node_storage_dir(self):
        dir_path = os.path.join(STORAGE_BASE_DIR, f"node_{self.server.server_port}")
        os.makedirs(dir_path, exist_ok=True)
        return dir_path

    def log_message(self, format, *args):
        pass

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path in ("/api/v0/version", "/version"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            resp = {
                "Version": "0.24.0",
                "Commit": "fedacre-local",
                "Repo": "14",
                "System": "amd64/windows"
            }
            self.wfile.write(json.dumps(resp).encode())
            return

        elif path in ("/api/v0/id", "/id"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            peer_ids = {
                5001: "12D3KooWEyoppPywJqodgvPnRoCvLqdvdKvgjW3KovBwKkjmX4hF",
                5002: "12D3KooWDiB3N9t5u3qS1w6u1UjH2uP8dC5jQ7fM4sL9vR1bN2kL",
                5003: "12D3KooWNv8R4h3pD9eU2x7bF5cV1jH6sM8qW4zK3mY7tB9nL1vP",
                5004: "12D3KooWDpJ7As7BWAwRMfu1VU2WCqNjvq387JEYKDBj4kx6nXTN",
            }
            node_id = peer_ids.get(self.server.server_port, "12D3KooWDpJ7As7BWAwRMfu1VU2WCqNjvq387JEYKDBj4kx6nXTN")
            resp = {
                "ID": node_id,
                "PublicKey": "CAASpgIwggEi...",
                "Addresses": [f"/ip4/127.0.0.1/tcp/{self.server.server_port}"],
                "AgentVersion": "kubo/0.24.0",
                "ProtocolVersion": "ipfs/0.1.0"
            }
            self.wfile.write(json.dumps(resp).encode())
            return

        elif path in ("/api/v0/add", "/add"):
            length = int(self.headers.get("Content-Length", 0))
            raw_body = self.rfile.read(length) if length > 0 else b""
            content_type = self.headers.get("Content-Type", "")

            # Extract binary file content from multipart/form-data if present
            file_bytes = raw_body
            if "multipart/form-data" in content_type and b"\r\n\r\n" in raw_body:
                header_end = raw_body.find(b"\r\n\r\n")
                if header_end != -1:
                    boundary_idx = raw_body.rfind(b"\r\n--")
                    if boundary_idx > header_end:
                        file_bytes = raw_body[header_end + 4 : boundary_idx]
                    else:
                        file_bytes = raw_body[header_end + 4 :]

            cid = calculate_cidv0(file_bytes)
            cid_file = os.path.join(self.node_storage_dir, cid)
            with open(cid_file, "wb") as f:
                f.write(file_bytes)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            resp = {
                "Name": cid,
                "Hash": cid,
                "Size": str(len(file_bytes))
            }
            self.wfile.write((json.dumps(resp) + "\n").encode())
            return

        elif path in ("/api/v0/cat", "/cat") or path.startswith("/api/v0/cat/"):
            arg = query.get("arg", [""])[0]
            if not arg and len(path.split("/")) > 4:
                arg = path.split("/")[-1]
            cid_file = os.path.join(self.node_storage_dir, arg)
            if os.path.exists(cid_file):
                with open(cid_file, "rb") as f:
                    data = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.end_headers()
                self.wfile.write(data)
            else:
                self.send_response(404)
                self.end_headers()
            return

        # Unknown route fails closed
        self.send_response(404)
        self.end_headers()

    def do_GET(self):
        self.do_POST()

def run_server(port, name):
    class NodeServer(IPFSNodeHandler):
        node_name = name

    server = HTTPServer(("127.0.0.1", port), NodeServer)
    print(f"[IPFS] {name} running on http://127.0.0.1:{port}")
    server.serve_forever()

def start_all_nodes():
    nodes = [
        (5001, "Hospital 1 IPFS Node"),
        (5002, "Hospital 2 IPFS Node"),
        (5003, "Hospital 3 IPFS Node"),
        (5004, "Global Aggregator IPFS Node"),
    ]
    threads = []
    for port, name in nodes:
        t = threading.Thread(target=run_server, args=(port, name), daemon=True)
        t.start()
        threads.append(t)
    print("[IPFS] All 4 IPFS Nodes started successfully.")
    return threads

if __name__ == "__main__":
    start_all_nodes()
    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping IPFS nodes.")
