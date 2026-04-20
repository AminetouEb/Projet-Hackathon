import json
import socket
import threading
from typing import Dict, List, Optional

import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse

app = FastAPI(title="Hybrid Redirect Load Balancer", version="1.0.0")

VM_MANAGER_URL = "http://localhost:8001"
REGISTRY_FILE = "./application.json"
REDIRECT_STATUS_CODE = 307
TCP_TIMEOUT_SECONDS = 2

VM_ALIAS_TO_HOST = {
    "AlpineV": "10.144.208.124",
    "AlpineV2": "10.144.208.122",
    "AlpineV3": "10.144.208.123",
}

_rr_index = 0
_rr_lock = threading.Lock()


def load_registry() -> dict:
    with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def app_sort_key(app_name: str) -> int:
    digits = "".join(ch for ch in app_name if ch.isdigit())
    return int(digits) if digits else 999999


def get_vm_status() -> dict:
    r = requests.get(f"{VM_MANAGER_URL}/vm/status", timeout=30)
    r.raise_for_status()
    return r.json()


def get_vm_entry(vm_status: dict, vm_alias: str) -> Optional[dict]:
    host = VM_ALIAS_TO_HOST.get(vm_alias)
    if not host:
        return None
    return vm_status.get("tracked_vms", {}).get(host)


def get_vm_ip(vm_status: dict, vm_alias: str) -> Optional[str]:
    entry = get_vm_entry(vm_status, vm_alias)
    if not entry or entry.get("state") != "poweredOn":
        return None

    ip = entry.get("ip_address")
    if not ip or ip == "N/A":
        return None

    return ip


def check_tcp(ip: str, port: int, timeout: int = TCP_TIMEOUT_SECONDS) -> bool:
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except Exception:
        return False


def get_reachable_frontends() -> List[Dict]:
    registry = load_registry()
    vm_status = get_vm_status()
    frontends = []

    for app_name in sorted(registry.keys(), key=app_sort_key):
        frontend = registry.get(app_name, {}).get("frontend")
        if not frontend:
            continue

        vm_alias = frontend.get("vm")
        port = frontend.get("port")
        if not vm_alias or not port:
            continue

        ip = get_vm_ip(vm_status, vm_alias)
        if not ip:
            continue

        if not check_tcp(ip, int(port)):
            continue

        frontends.append({
            "app_name": app_name,
            "vm_alias": vm_alias,
            "ip": ip,
            "port": int(port),
            "base_url": f"http://{ip}:{int(port)}"
        })

    return frontends


def choose_frontend(frontends: List[Dict]) -> Dict:
    global _rr_index

    if not frontends:
        raise HTTPException(status_code=503, detail="No reachable frontend available")

    with _rr_lock:
        idx = _rr_index % len(frontends)
        _rr_index += 1

    return frontends[idx]


def build_target_url(request: Request, frontend: Dict, full_path: str) -> str:
    path = "/" + full_path if full_path else "/"
    target = f"{frontend['base_url']}{path}"
    query = request.url.query
    if query:
        target = f"{target}?{query}"
    return target


@app.get("/health")
def health():
    return {"status": "ok", "service": "redirect-load-balancer"}


@app.get("/admin/frontends")
def admin_frontends():
    try:
        frontends = get_reachable_frontends()
        return {"count": len(frontends), "reachable_frontends": frontends}
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"vm_manager unreachable: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.api_route("/", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
@app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
def redirect_user(request: Request, full_path: str = ""):
    try:
        frontends = get_reachable_frontends()
        selected = choose_frontend(frontends)
        target_url = build_target_url(request, selected, full_path)
        return RedirectResponse(url=target_url, status_code=REDIRECT_STATUS_CODE)
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"vm_manager unreachable: {e}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
