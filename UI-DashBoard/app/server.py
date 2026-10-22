"""
MedXChAIn Interactive Web Dashboard Backend
Serves live data with verifiable provenance from Hardhat EVM, IPFS Nodes, and genuine PyTorch Federated Learning Model.
"""

import os
import sys
import json
import time
import hashlib
import urllib.request
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse
from datetime import datetime, timezone

import numpy as np
import torch
import torch.nn as nn

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FL_DIR = os.path.join(BASE_DIR, "FL")
BLOCKCHAIN_DIR = os.path.join(BASE_DIR, "Blockchain")
WEB_DIR = os.path.join(BASE_DIR, "UI-DashBoard", "app")

# ----------------- Model Architecture & Embeddings -----------------

VOCAB_SIZE = 768

def symptom_to_embedding(text: str, dim: int = VOCAB_SIZE) -> torch.Tensor:
    """Deterministic token hashing projection to fixed dimensional embedding."""
    vec = np.zeros(dim, dtype=np.float32)
    tokens = [w.strip() for w in text.lower().replace(",", " ").replace(".", " ").split() if len(w) > 2]
    if not tokens:
        return torch.from_numpy(vec)
    for tok in tokens:
        idx = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16) % dim
        vec[idx] += 1.0
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return torch.from_numpy(vec)

class MedCPTClassifier(nn.Module):
    def __init__(self, num_labels=793, input_dim=VOCAB_SIZE):
        super().__init__()
        self.feature_extractor = nn.Linear(input_dim, 256)
        self.relu = nn.ReLU()
        self.dropout = nn.Dropout(0.1)
        self.classifier = nn.Linear(256, num_labels)

    def forward(self, x):
        h = self.relu(self.feature_extractor(x))
        h = self.dropout(h)
        return self.classifier(h)

# ----------------- Configuration & Provenance Helpers -----------------

def load_label_mapping():
    mapping_path = os.path.join(FL_DIR, "label_mapping.json")
    if os.path.exists(mapping_path):
        with open(mapping_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

label_mapping = load_label_mapping()

def load_deployment_info():
    dep_path = os.path.join(BLOCKCHAIN_DIR, "deployment_info.json")
    if os.path.exists(dep_path):
        with open(dep_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

_cached_model = None
_cached_mtime = None

def get_inference_model():
    """Lazily loads and caches the PyTorch global model weights."""
    global _cached_model, _cached_mtime
    model_path = os.path.join(FL_DIR, "global_model_weights.pt")
    if not os.path.exists(model_path):
        return None
    try:
        mtime = os.path.getmtime(model_path)
        if _cached_model is None or _cached_mtime != mtime:
            num_labels = len(label_mapping) if label_mapping else 793
            model = MedCPTClassifier(num_labels=num_labels)
            state_dict = torch.load(model_path, map_location="cpu")
            model.load_state_dict(state_dict)
            model.eval()
            _cached_model = model
            _cached_mtime = mtime
        return _cached_model
    except Exception as e:
        print(f"⚠️ Error loading PyTorch global model: {e}", file=sys.stderr)
        return None

def eth_call(to: str, data: str, rpc_url="http://127.0.0.1:8545") -> str:
    req = urllib.request.Request(
        rpc_url,
        data=json.dumps({
            "jsonrpc": "2.0",
            "method": "eth_call",
            "params": [{"to": to, "data": data}, "latest"],
            "id": 1
        }).encode(),
        headers={"Content-Type": "application/json"}
    )
    res = urllib.request.urlopen(req, timeout=1.5)
    data_res = json.loads(res.read())
    return data_res.get("result", "0x")

def check_blockchain_health(rpc_url="http://127.0.0.1:8545"):
    try:
        req = urllib.request.Request(
            rpc_url,
            data=json.dumps({"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 1}).encode(),
            headers={"Content-Type": "application/json"}
        )
        res = urllib.request.urlopen(req, timeout=1.5)
        data = json.loads(res.read())
        block_num = int(data.get("result", "0x0"), 16)
        return {"status": "ok", "block_number": block_num}
    except Exception as e:
        return {"status": "degraded", "error": str(e)}

def check_ipfs_health(port=5001):
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{port}/api/v0/version", data=b"", headers={})
        res = urllib.request.urlopen(req, timeout=1.0)
        data = json.loads(res.read())
        return {"status": "ok", "version": data.get("Version", "0.24.0")}
    except Exception as e:
        return {"status": "degraded", "error": "IPFS daemon not responding on port 5001"}

def load_round_receipt():
    rec_path = os.path.join(BLOCKCHAIN_DIR, "round_receipt.json")
    if os.path.exists(rec_path):
        with open(rec_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def get_system_state():
    dep = load_deployment_info()
    receipt = load_round_receipt()
    chain_health = check_blockchain_health()
    ipfs_health = check_ipfs_health()
    
    # Check model artifact
    model_path = os.path.join(FL_DIR, "global_model_weights.pt")
    model_exists = os.path.exists(model_path)
    model_size = os.path.getsize(model_path) if model_exists else 0

    contract_addr = dep.get("address", "0x0165878A594ca255338adfa4d48449f69242Eb8F")
    configured_hospitals = dep.get("hospitals", [
        "0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
        "0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC",
        "0x90F79bf6EB2c4f870365E785982E1f101E93b906"
    ])

    current_round = receipt.get("newRound", receipt.get("round", 1))
    required_submissions = dep.get("requiredSubmissions", 3)
    active_hospital_count = len(configured_hospitals)

    # Dynamic on-chain query via eth_call
    hospitals_state = []
    if chain_health["status"] == "ok":
        try:
            # Query currentRound(): selector 0x8a19c8bc
            r_hex = eth_call(contract_addr, "0x8a19c8bc")
            if r_hex and r_hex != "0x":
                current_round = int(r_hex, 16)

            # Query requiredSubmissions(): selector 0xb9f9e304
            req_hex = eth_call(contract_addr, "0xb9f9e304")
            if req_hex and req_hex != "0x":
                required_submissions = int(req_hex, 16)

            # Query activeHospitalCount(): selector 0x15bb69b9
            act_hex = eth_call(contract_addr, "0x15bb69b9")
            if act_hex and act_hex != "0x":
                active_hospital_count = int(act_hex, 16)

            for idx, h_addr in enumerate(configured_hospitals):
                clean_addr = h_addr.lower().replace("0x", "").zfill(64)
                data = "0x3f9b9d2e" + clean_addr
                res_hex = eth_call(contract_addr, data)
                if res_hex and len(res_hex) >= 194:
                    raw = res_hex[2:]
                    is_reg = bool(int(raw[0:64], 16))
                    total_sub = int(raw[64:128], 16)
                    last_rnd = int(raw[128:192], 16)
                    status_text = "Registered" if is_reg else "Revoked"
                else:
                    is_reg = False
                    total_sub = 0
                    last_rnd = 0
                    status_text = "Unknown"

                hospitals_state.append({
                    "id": idx + 1,
                    "name": f"Federated Node {idx + 1} (Partition train_{idx + 1}.csv)",
                    "address": h_addr,
                    "isRegistered": is_reg,
                    "status": status_text,
                    "totalSubmissions": total_sub,
                    "lastRound": last_rnd
                })
        except Exception as e:
            chain_health["status"] = "degraded"
            chain_health["error"] = str(e)

    if not hospitals_state:
        for idx, h_addr in enumerate(configured_hospitals):
            hospitals_state.append({
                "id": idx + 1,
                "name": f"Federated Node {idx + 1} (Partition train_{idx + 1}.csv)",
                "address": h_addr,
                "isRegistered": False,
                "status": "Unknown (Blockchain Unreachable)",
                "totalSubmissions": 0,
                "lastRound": 0
            })

    global_info = receipt.get("globalModel", {})

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "chain": chain_health["status"],
            "ipfs": ipfs_health["status"],
            "model": "ok" if model_exists else "unavailable"
        },
        "round": {
            "currentRound": current_round,
            "requiredSubmissions": required_submissions,
            "activeHospitalCount": active_hospital_count,
            "contractAddress": contract_addr,
            "latestBlock": chain_health.get("block_number", 0),
            "globalCid": global_info.get("cid", ""),
            "globalTx": global_info.get("txHash", ""),
            "submissions": receipt.get("submissions", [])
        },
        "model": {
            "architecture": "MedCPTClassifier (768 -> 256 -> 793)",
            "parameters": 400657,
            "tunable": "classification_head",
            "artifact_exists": model_exists,
            "artifact_size_bytes": model_size,
            "verified_classes": len(label_mapping)
        },
        "hospitals": hospitals_state,
        "compliance": {
            "framework": "Academic Research Prototype — Differential Privacy (DP-SGD) with On-Chain Proofs",
            "audit_status": "Synthetic EHR Partition Schema (Non-PII Tokenized Clinical Ontology)"
        }
    }

# ----------------- HTTP Request Handler -----------------

class DashboardHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    def log_message(self, format, *args):
        sys.stdout.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {args[0]} {args[1]}\n")

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/status":
            state = get_system_state()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(state, indent=2).encode())
            return

        elif path == "/api/labels":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(label_mapping).encode())
            return

        super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length", 0))
        
        # Enforce maximum payload size (1 MB limit)
        if length > 1024 * 1024:
            self.send_response(413)
            self.end_headers()
            self.wfile.write(b'{"error": "Payload too large"}')
            return

        body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        try:
            payload = json.loads(body)
        except Exception:
            payload = {}

        if path == "/api/diagnose":
            symptoms = payload.get("symptoms", "").strip()

            # Guardrail 1: Minimum character threshold
            if len(symptoms) < 3:
                self.send_response(422)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "error": "Input too short",
                    "message": "Please enter at least 3 characters describing clinical symptoms."
                }).encode())
                return

            # Guardrail 2: Red-flag emergency detection
            red_flags = ["chest pain", "shortness of breath", "stroke", "severe bleeding", "unconscious"]
            urgent_alert = None
            for flag in red_flags:
                if flag in symptoms.lower():
                    urgent_alert = f"Urgent clinical alert: Symptom query contains '{flag}'. Immediate in-person medical evaluation recommended."
                    break

            # Neural Diagnostic Inference using true trained PyTorch Model
            model = get_inference_model()
            top_candidates = []

            if model is not None:
                emb = symptom_to_embedding(symptoms).unsqueeze(0)
                with torch.no_grad():
                    logits = model(emb)
                    probs = torch.softmax(logits, dim=1)[0]
                    top_probs, top_indices = torch.topk(probs, 3)

                for prob, idx in zip(top_probs, top_indices):
                    disease_name = label_mapping.get(str(idx.item()), f"Disease #{idx.item()}")
                    top_candidates.append({
                        "disease": disease_name.title(),
                        "confidence": round(prob.item() * 100.0, 1),
                        "label_id": idx.item()
                    })
                model_status = "Inference generated via PyTorch global model weights."
            else:
                model_status = "Global model weights not loaded. Execute run_federated_pipeline.py to train and publish weights."

            response_data = {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "query": symptoms,
                "disclaimer": "Academic research prototype. Decision support and demonstration only.",
                "urgent_care_alert": urgent_alert,
                "evidence": {
                    "matched_classes": len(top_candidates),
                    "top_differentials": top_candidates
                },
                "status": model_status
            }

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response_data, indent=2).encode())
            return

        elif path == "/api/advance-round":
            state = get_system_state()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "message": "Round advancement requires signed blockchain transaction via run_federated_pipeline.py",
                "state": state
            }, indent=2).encode())
            return

        self.send_response(404)
        self.end_headers()

def main():
    port = 3000
    server = ThreadingHTTPServer(("127.0.0.1", port), DashboardHandler)
    print(f"🚀 MedXChAIn Web Dashboard running at http://127.0.0.1:{port}")
    server.serve_forever()

if __name__ == "__main__":
    main()
