from fastapi import FastAPI, HTTPException
import uvicorn
from python_on_whales import DockerClient
import requests
import time
import json
import os
import subprocess
import socket

app = FastAPI()

# =========================
# CONFIG
# =========================

VM_MANAGER = "http://localhost:8001"
REGISTRY_FILE = "./application.json"

# mapping logique -> host suivi par vm_manager
VM_ALIAS_TO_HOST = {
    "AlpineV": "10.144.208.124",
    "AlpineV2": "10.144.208.122",
    "AlpineV3": "10.144.208.123",
}

SSH_PASSWORD = "toto32**"

IMAGES = {
    "db": "postgres:15",
    "backend": "aminetou01/backend:1.0",
    "frontend": "aminetou01/frontend:1.0",
}

DB_INIT_SQL_PATH = "/root/Hackathon--Project/database/init.sql"
DB_DATA_PATH = "/root/Hackathon--Project/database/data"

# =========================
# VM SYNC & RESOLUTION
# =========================

def get_vm_status():
    status = requests.get(f"{VM_MANAGER}/vm/status", timeout=360).json()
    if not status:
        raise Exception("Could not get vm_manager status. Is vm_manager running on 8001?")
    return status


def resolve_host_alias(vm_name: str) -> str:
    host = VM_ALIAS_TO_HOST.get(vm_name)
    if not host:
        raise Exception(f"Unknown VM alias: {vm_name}")
    return host


def get_vm_entry(vm_name: str):
    """
    vm_manager renvoie tracked_vms par host, pas par nom.
    On mappe donc AlpineV/AlpineV2/AlpineV3 -> host.
    """
    status = get_vm_status()
    tracked = status.get("tracked_vms", {})
    host = resolve_host_alias(vm_name)
    return tracked.get(host)


def get_vm_ip(vm_name):
    vm_entry = get_vm_entry(vm_name)
    if not vm_entry:
        raise Exception(f"Could not resolve VM entry for {vm_name}. Is it deployed?")

    vm_ip = vm_entry.get("ip_address")
    if vm_ip and vm_ip != "N/A":
        return vm_ip

    raise Exception(f"Could not resolve IP for VM: {vm_name}. Is it powered on?")


def get_vm_power_state(vm_name):
    vm_entry = get_vm_entry(vm_name)
    if not vm_entry:
        return None
    return vm_entry.get("state")


def wait_vm_state(expected_fn, timeout=360):
    start = time.time()
    while time.time() - start < timeout:
        state = get_vm_status()
        if expected_fn(state):
            return state
        time.sleep(5)
    raise Exception("VM transition timed out")


def ensure_vm_up():
    print("Triggering VM Scale UP...")
    requests.post(f"{VM_MANAGER}/vm/up", timeout=360)

    def ready(state):
        # on considère stable si vm_manager répond et les tracked_vms existent
        return "tracked_vms" in state

    wait_vm_state(ready)


def ensure_vm_down():
    print("Triggering VM Scale DOWN...")
    requests.post(f"{VM_MANAGER}/vm/down", timeout=360)

    def ready(state):
        return "tracked_vms" in state

    wait_vm_state(ready)


# =========================
# DOCKER & SSH
# =========================

def ensure_ssh_access(vm_ip, password=SSH_PASSWORD):
    key_path = os.path.expanduser("~/.ssh/id_rsa_Hackathon")

    if not os.path.exists(key_path):
        print("Generating new SSH key...")
        subprocess.run(
            f'ssh-keygen -t ed25519 -N "" -f {key_path}',
            shell=True,
            check=False
        )

    test_cmd = f'ssh -o BatchMode=yes -o StrictHostKeyChecking=no root@{vm_ip} "exit"'
    result = subprocess.run(test_cmd, shell=True, capture_output=True)

    if result.returncode == 0:
        return True

    print(f"Key not found on {vm_ip}. Deploying via sshpass...")
    copy_cmd = (
        f'sshpass -p "{password}" ssh-copy-id -o StrictHostKeyChecking=no '
        f'-i {key_path}.pub root@{vm_ip}'
    )
    copy_result = subprocess.run(copy_cmd, shell=True, capture_output=True)

    return copy_result.returncode == 0


def get_docker(vm_name):
    try:
        current_state = str(get_vm_power_state(vm_name) or "").lower()

        if current_state not in ["running", "poweredon", "up", "poweredonstate", "poweredon"]:
            print(f"[{vm_name}] is {current_state}. Skipping Docker connection.")
            return None

        vm_ip = get_vm_ip(vm_name)

        if not ensure_ssh_access(vm_ip):
            return None

        client = DockerClient(host=f"ssh://root@{vm_ip}")
        client.system.info()
        return client

    except Exception as e:
        print(f"Hardware check failed for {vm_name}: {e}")
        return None


def get_container_status(vm, name):
    client = get_docker(vm)
    if not client:
        return "missing"

    existing = client.container.list(all=True, filters={"name": f"^{name}$"})
    if not existing:
        return "missing"

    container = existing[0]
    return "running" if container.state.running else "stopped"


def wait_container(vm, name, timeout=360):
    start = time.time()
    while time.time() - start < timeout:
        if get_container_status(vm, name) == "running":
            return True
        time.sleep(2)
    raise Exception(f"Timeout waiting for {name} to reach 'running' state")


def run_container(vm, name, comp_type, port, env_vars=None):
    if env_vars is None:
        env_vars = {}

    client = get_docker(vm)
    if client is None:
        raise Exception(f"No Docker client available for {vm}")

    command = None
    volumes = []
    tmpfs = []
    shm_size = None

    if comp_type == "db":
        image = IMAGES["db"]
        internal_port = 5432
        env_vars.update({
            "POSTGRES_DB": "environmental_db",
            "POSTGRES_USER": "postgres",
            "POSTGRES_PASSWORD": "1234",
        })
        volumes = [
            (DB_INIT_SQL_PATH, "/docker-entrypoint-initdb.d/init.sql", "ro"),
            (DB_DATA_PATH, "/data", "ro"),
        ]
        tmpfs = ["/var/lib/postgresql/data:size=1g"]
        shm_size = "256m"

    elif comp_type == "backend":
        image = IMAGES["backend"]
        internal_port = 5000
        env_vars = {
            "DB_HOST": env_vars["DB_HOST"],
            "DB_NAME": "environmental_db",
            "DB_USER": "app_readonly",
            "DB_PASSWORD": "1234",
            "DB_PORT": str(env_vars["DB_PORT"]),
        }

    elif comp_type == "frontend":
        image = IMAGES["frontend"]
        internal_port = 80
        env_vars = {
            "BACKEND_URL": env_vars["BACKEND_URL"]
        }

    else:
        raise ValueError(f"Unknown component type: {comp_type}")

    print(f"[{vm}] Deploying {name} ({image}) on port {port}...")

    kwargs = {
        "image": image,
        "name": name,
        "detach": True,
        "publish": [(port, internal_port)],
        "envs": env_vars,
        "restart": "always"
    }

    if command:
        kwargs["command"] = command
    if volumes:
        kwargs["volumes"] = volumes
    if tmpfs:
        kwargs["tmpfs"] = tmpfs
    if shm_size:
        kwargs["shm_size"] = shm_size

    client.run(**kwargs)
    wait_container(vm, name)


# =========================
# HEALTH CHECK
# =========================

def check_tcp(ip, port):
    try:
        with socket.create_connection((ip, port), timeout=2):
            return True
    except Exception:
        return False


def wait_health(ip, port, timeout=360):
    start = time.time()
    while time.time() - start < timeout:
        if check_tcp(ip, port):
            return True
        time.sleep(2)
    raise Exception(f"Service at {ip}:{port} failed to become healthy.")


# =========================
# REGISTRY & APP CONTROL
# =========================

def load_registry():
    with open(REGISTRY_FILE) as f:
        return json.load(f)


def validate_registry():
    registry = load_registry()
    for app_name, conf in registry.items():
        if conf["backend"]["vm"] != conf["db"]["vm"]:
            raise Exception(f"{app_name}: backend and db must be on the same VM")


def start_app(app_name, conf):
    print(f"\n--- Reconciling {app_name} ---")

    if conf["backend"]["vm"] != conf["db"]["vm"]:
        raise Exception(f"{app_name}: backend and db must be on same VM")

    ips = {
        "db": get_vm_ip(conf["db"]["vm"]),
        "backend": get_vm_ip(conf["backend"]["vm"]),
        "frontend": get_vm_ip(conf["frontend"]["vm"])
    }

    components = [
        ("db", f"{app_name}_db"),
        ("backend", f"{app_name}_backend"),
        ("frontend", f"{app_name}_frontend")
    ]

    for comp_type, name in components:
        vm_name = conf[comp_type]["vm"]
        port = conf[comp_type]["port"]

        status = get_container_status(vm_name, name)
        if status == "running":
            print(f"[{name}] already running. Skipping.")
            continue

        if status == "stopped":
            print(f"[{name}] exists but is stopped. Starting it now...")
            client = get_docker(vm_name)
            client.container.start(name)
            wait_health(ips[comp_type], port)

        elif status == "missing":
            print(f"[{name}] not found. Creating fresh instance...")
            env = {}

            if comp_type == "backend":
                env = {
                    "DB_HOST": ips["db"],
                    "DB_PORT": str(conf["db"]["port"])
                }

            elif comp_type == "frontend":
                env = {
                    "BACKEND_URL": f"http://{ips['backend']}:{conf['backend']['port']}"
                }

            run_container(vm_name, name, comp_type, port, env_vars=env)
            wait_health(ips[comp_type], port)

    print(f"--- {app_name} is synchronized and running ---\n")


def stop_app_safely(app_name, conf):
    print(f"\n--- Stopping {app_name} ---")
    for comp_type, c in conf.items():
        container_name = f"{app_name}_{comp_type}"
        vm_name = c["vm"]
        client = get_docker(vm_name)
        if not client:
            continue

        try:
            containers = client.container.list(all=True, filters={"name": f"^{container_name}$"})
            if containers and containers[0].state.running:
                print(f"Stopping {container_name} on {vm_name}...")
                containers[0].stop()
        except Exception as e:
            print(f"Error stopping {container_name}: {e}")


def delete_app_safely(app_name, conf):
    print(f"\n--- Deleting {app_name} ---")
    for comp_type, c in conf.items():
        container_name = f"{app_name}_{comp_type}"
        vm_name = c["vm"]
        client = get_docker(vm_name)
        if not client:
            continue

        try:
            containers = client.container.list(all=True, filters={"name": f"^{container_name}$"})
            if containers:
                container = containers[0]
                if not container.state.running:
                    print(f"Deleting stopped container {container_name} from {vm_name}...")
                    container.remove()
                else:
                    print(f"CANNOT DELETE {container_name}: It is still running!")
        except Exception as e:
            print(f"Error deleting {container_name}: {e}")


def create_app_buffer(app_name, conf):
    print(f"\n--- Creating Buffer for {app_name} ---")
    start_app(app_name, conf)
    stop_app_safely(app_name, conf)
    print(f"--- {app_name} is BUFFERED (Downed and Ready) ---\n")


# =========================
# STATE MACHINE CLASSES
# =========================

class SystemState:
    name = "UNKNOWN"

    def process_rpm(self, rpm: int, registry: dict):
        return self


class D0State(SystemState):
    name = "D0"

    def process_rpm(self, rpm: int, registry: dict):
        if rpm >= 2:
            print("[Transition] D0 -> D1")
            ensure_vm_up()
            start_app("app2", registry["app2"])
            create_app_buffer("app3", registry["app3"])
            return D1State()
        return self


class D1State(SystemState):
    name = "D1"

    def process_rpm(self, rpm: int, registry: dict):
        if rpm < 2:
            print("[Transition] D1 -> D0")
            delete_app_safely("app3", registry["app3"])
            stop_app_safely("app2", registry["app2"])
            ensure_vm_down()
            return D0State()
        elif rpm >= 4:
            print("[Transition] D1 -> D2")
            start_app("app3", registry["app3"])
            return D2State()
        return self


class D2State(SystemState):
    name = "D2"

    def process_rpm(self, rpm: int, registry: dict):
        if rpm < 4:
            print("[Transition] D2 -> D1")
            stop_app_safely("app3", registry["app3"])
            return D1State()
        elif rpm >= 6:
            print("[Transition] D2 -> D3")
            ensure_vm_up()
            start_app("app4", registry["app4"])
            create_app_buffer("app5", registry["app5"])
            return D3State()
        return self


class D3State(SystemState):
    name = "D3"

    def process_rpm(self, rpm: int, registry: dict):
        if rpm >= 8:
            print("[Transition] D3 -> D5")
            start_app("app5", registry["app5"])
            return D5State()
        elif rpm < 6:
            print("[Transition] D3 -> D4")
            stop_app_safely("app4", registry["app4"])
            ensure_vm_down()
            return D4State()
        return self


class D4State(SystemState):
    name = "D4"

    def process_rpm(self, rpm: int, registry: dict):
        if rpm >= 6:
            print("[Transition] D4 -> D3")
            ensure_vm_up()
            start_app("app4", registry["app4"])
            return D3State()
        elif rpm < 4:
            print("[Transition] D4 -> D1")
            ensure_vm_up()
            delete_app_safely("app4", registry["app4"])
            ensure_vm_down()
            return D1State()
        return self


class D5State(SystemState):
    name = "D5"

    def process_rpm(self, rpm: int, registry: dict):
        if rpm < 8:
            print("[Transition] D5 -> D3")
            stop_app_safely("app5", registry["app5"])
            return D3State()
        return self


# =========================
# GLOBAL ORCHESTRATOR
# =========================

CURRENT_STATE: SystemState = D0State()


def get_app_master_status(app_name, conf):
    return get_container_status(conf["frontend"]["vm"], f"{app_name}_frontend")


def sync_state_from_hardware() -> SystemState:
    vm_reality = get_vm_status()
    registry = load_registry()

    # fallback simple si vm_manager ne fournit pas state_index
    vms_idx = vm_reality.get("state_index", 0)

    a1 = get_app_master_status("app1", registry["app1"])
    a2 = get_app_master_status("app2", registry["app2"])
    a3 = get_app_master_status("app3", registry["app3"])
    a4 = get_app_master_status("app4", registry["app4"])
    a5 = get_app_master_status("app5", registry["app5"])

    if vms_idx == 0 and a1 == "running":
        return D0State()

    elif vms_idx == 1 and a1 == "running" and a2 == "running":
        if a3 == "running":
            if a4 == "stopped":
                return D4State()
            elif a4 == "missing":
                return D2State()
        else:
            return D1State()

    elif vms_idx == 2 and a1 == "running" and a2 == "running" and a3 == "running" and a4 == "running":
        if a5 == "running":
            return D5State()
        else:
            return D3State()

    raise Exception(f"Desync Error. Unmapped hardware state. VM Index: {vms_idx}. Apps: {a1},{a2},{a3},{a4},{a5}")


# =========================
# API ROUTES
# =========================

@app.post("/rpm")
def rpm_update(rpm: int):
    global CURRENT_STATE
    try:
        validate_registry()
        CURRENT_STATE = sync_state_from_hardware()
        new_state_obj = CURRENT_STATE.process_rpm(rpm, load_registry())
        CURRENT_STATE = new_state_obj

        return {
            "rpm": rpm,
            "current_state": CURRENT_STATE.name,
            "vm_state": get_vm_status()
        }

    except Exception as e:
        print(f"RPM Update Failed: {e}")
        raise HTTPException(500, str(e))


@app.get("/health")
def health():
    global CURRENT_STATE
    validate_registry()
    CURRENT_STATE = sync_state_from_hardware()
    return {"status": "ok", "state": CURRENT_STATE.name}


@app.get("/up/app/{app_id}")
def start_app_api(app_id: int):
    validate_registry()
    app_name = f"app{app_id}"
    conf = load_registry().get(app_name, None)
    if not conf:
        return {"message": "No", "details": f"{app_name} doesn't exist"}
    start_app(app_name, conf)
    return {"message": "ok", "details": f"{app_name} started."}


@app.get("/down/app/{app_id}")
def stop_app_api(app_id: int):
    validate_registry()
    app_name = f"app{app_id}"
    conf = load_registry().get(app_name)
    if not conf:
        return {"message": "error", "details": f"{app_name} not found in registry"}
    stop_app_safely(app_name, conf)
    return {"message": "ok", "details": f"{app_name} has been stopped."}


@app.get("/delete/app/{app_id}")
def delete_app_api(app_id: int):
    validate_registry()
    app_name = f"app{app_id}"
    conf = load_registry().get(app_name)
    if not conf:
        return {"message": "error", "details": f"{app_name} not found in registry"}
    delete_app_safely(app_name, conf)
    return {"message": "ok", "details": f"{app_name} files/containers removed."}


@app.get("/hello/{vm_name}")
def hello_vm(vm_name: str):
    client = get_docker(vm_name)
    if not client:
        return {"message": f"Couldn't get {vm_name} docker Connection."}
    result = client.run("hello-world")
    return {"status": "ok", "message": str(result)}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)
